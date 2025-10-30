import streamlit as st
import pandas as pd
import datetime
from modules.data_manager import scrivi_o_aggiorna_risposta
from modules.shift_management import log_shift_change
from modules.notifications import crea_notifica

@st.cache_data
def to_csv(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv(index=False).encode('utf-8')

def render_debriefing_ui(knowledge_core, matricola_utente, data_riferimento):
    task = st.session_state.debriefing_task
    section_key = task['section_key']

    def handle_submit(report_text, stato):
        if report_text.strip():
            dati = {
                'descrizione': f"PdL {task['pdl']} - {task['attivita']}",
                'report': report_text,
                'stato': stato
            }

            success = scrivi_o_aggiorna_risposta(dati, matricola_utente, data_riferimento)

            if success:
                completed_task_data = {**task, 'report': report_text, 'stato': stato}

                completed_list = st.session_state.get(f"completed_tasks_{section_key}", [])
                completed_list = [t for t in completed_list if t['pdl'] != task['pdl']]
                completed_list.append(completed_task_data)
                st.session_state[f"completed_tasks_{section_key}"] = completed_list

                if section_key == 'yesterday':
                    if 'completed_tasks_yesterday' not in st.session_state:
                        st.session_state.completed_tasks_yesterday = []
                    st.session_state.completed_tasks_yesterday.append(completed_task_data)

                st.success("Report inviato con successo al database!")
                del st.session_state.debriefing_task
                st.balloons()
                st.rerun()
            else:
                st.error("Si è verificato un errore durante il salvataggio del report nel database.")
        else:
            st.warning("Il report non può essere vuoto.")

    st.title("📝 Compila Report")
    st.subheader(f"PdL `{task['pdl']}` - {task['attivita']}")
    report_text = st.text_area("Inserisci il tuo report qui:", value=task.get('report', ''), height=200)
    stato_options = ["TERMINATA", "SOSPESA", "IN CORSO", "NON SVOLTA"]
    stato_index = stato_options.index(task.get('stato')) if task.get('stato') in stato_options else 0
    stato = st.selectbox("Stato Finale", stato_options, index=stato_index, key="manual_stato")

    col1, col2 = st.columns(2)
    if col1.button("Invia Report", type="primary"):
        handle_submit(report_text, stato)
    if col2.button("Annulla"):
        del st.session_state.debriefing_task
        st.rerun()


from modules.db_manager import get_shift_by_id, get_bookings_for_shift, get_all_users, update_shift, delete_booking, add_booking
from modules.notifications import crea_notifica
from modules.shift_management import log_shift_change


def render_edit_shift_form():
    """Render the form for editing an existing shift."""
    turno_id = st.session_state.get('editing_turno_id')
    if not turno_id:
        st.error("ID Turno non specificato.")
        return

    # Caricamento dati iniziali
    turno_data = get_shift_by_id(turno_id)
    if not turno_data:
        st.error("Turno non trovato.")
        del st.session_state['editing_turno_id']
        return

    personale_nel_turno_df = get_bookings_for_shift(turno_id)
    personale_nel_turno = personale_nel_turno_df.set_index('Matricola').to_dict()['RuoloOccupato']

    tutti_gli_utenti_df = get_all_users()
    utenti_validi = tutti_gli_utenti_df[tutti_gli_utenti_df['Matricola'].notna()]
    opzioni_personale = utenti_validi.set_index('Matricola')['Nome Cognome'].to_dict()

    st.subheader(f"Modifica Turno: {turno_data.get('Descrizione', 'N/A')}")

    with st.form("edit_shift_form"):
        desc_turno = st.text_input("Descrizione Turno", value=turno_data.get('Descrizione', ''))
        tipo_turno = st.selectbox("Tipologia", ["Reperibilità", "Ferie"], index=["Reperibilità", "Ferie"].index(turno_data.get('Tipo', 'Reperibilità')))

        # Gestione date e ore
        data_inizio_dt = pd.to_datetime(turno_data.get('Data', datetime.date.today()))
        ora_inizio_dt = pd.to_datetime(turno_data.get('OraInizio', '00:00')).time()
        ora_fine_dt = pd.to_datetime(turno_data.get('OraFine', '00:00')).time()

        col1, col2, col3 = st.columns(3)
        with col1:
            data_inizio = st.date_input("Data", value=data_inizio_dt)
        with col2:
            ora_inizio = st.time_input("Ora Inizio", value=ora_inizio_dt)
        with col3:
            ora_fine = st.time_input("Ora Fine", value=ora_fine_dt)

        # Selezione personale
        tecnici_attuali = [m for m, r in personale_nel_turno.items() if r == 'Tecnico']
        aiutanti_attuali = [m for m, r in personale_nel_turno.items() if r == 'Aiutante']

        tecnici_selezionati = st.multiselect(
            "Seleziona Tecnici",
            options=opzioni_personale.keys(),
            format_func=lambda matricola: opzioni_personale[matricola],
            default=tecnici_attuali
        )
        aiutanti_selezionati = st.multiselect(
            "Seleziona Aiutanti",
            options=opzioni_personale.keys(),
            format_func=lambda matricola: opzioni_personale[matricola],
            default=aiutanti_attuali
        )

        submitted = st.form_submit_button("Salva Modifiche")

        if submitted:
            # 1. Preparazione dei dati aggiornati per il turno
            update_data = {
                "Descrizione": desc_turno,
                "Tipo": tipo_turno,
                "Data": data_inizio.isoformat(),
                "OraInizio": ora_inizio.strftime('%H:%M'),
                "OraFine": ora_fine.strftime('%H:%M'),
            }

            # 2. Aggiornamento del turno nel database
            if update_shift(turno_id, update_data):
                # 3. Gestione delle prenotazioni (logica di aggiunta/rimozione)
                personale_originale = set(personale_nel_turno.keys())
                personale_nuovo = set(tecnici_selezionati + aiutanti_selezionati)

                personale_rimosso = personale_originale - personale_nuovo
                for matricola in personale_rimosso:
                    if delete_booking(matricola, turno_id):
                        messaggio = f"Sei stato rimosso dal turno '{desc_turno}'."
                        crea_notifica(matricola, messaggio)
                        log_shift_change(turno_id, "Rimozione", matricola_originale=matricola, matricola_eseguito_da=st.session_state['authenticated_user'])


                personale_aggiunto = personale_nuovo - personale_originale
                for matricola in personale_aggiunto:
                    ruolo = 'Tecnico' if matricola in tecnici_selezionati else 'Aiutante'
                    booking_data = {'ID_Turno': turno_id, 'Matricola': matricola, 'RuoloOccupato': ruolo}
                    if add_booking(booking_data):
                         messaggio = f"Sei stato aggiunto al turno '{desc_turno}'."
                         crea_notifica(matricola, messaggio)
                         log_shift_change(turno_id, "Aggiunta", matricola_subentrante=matricola, matricola_eseguito_da=st.session_state['authenticated_user'])


                st.success("Turno aggiornato con successo!")
                log_shift_change(turno_id, "Modifica Dettagli", matricola_eseguito_da=st.session_state['authenticated_user'])
                del st.session_state['editing_turno_id']
                st.rerun()
            else:
                st.error("Errore durante l'aggiornamento del turno.")
