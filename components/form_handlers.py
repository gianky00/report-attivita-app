import streamlit as st
import pandas as pd
import datetime
from modules.data_manager import scrivi_o_aggiorna_risposta
from modules.shift_management import log_shift_change
from modules.notifications import crea_notifica
from modules.data_manager import salva_gestionale_async

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


def render_edit_shift_form(gestionale_data):
    turno_id = st.session_state['editing_turno_id']
    df_turni = gestionale_data['turni']

    try:
        turno_data = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    except (IndexError, KeyError):
        st.error("Errore: Turno non trovato o dati corrotti.")
        if 'editing_turno_id' in st.session_state:
            del st.session_state['editing_turno_id']
        st.rerun()

    st.title(f"Modifica Turno: {turno_data.get('Descrizione', 'N/D')}")

    with st.form("edit_shift_form"):
        st.subheader("Dettagli Turno")

        tipi_turno = ["Assistenza", "Straordinario"]
        try:
            tipo_turno_index = tipi_turno.index(turno_data.get('Tipo', 'Assistenza'))
        except ValueError:
            tipo_turno_index = 0

        tipo_turno = st.selectbox("Tipo Turno", tipi_turno, index=tipo_turno_index)
        desc_turno = st.text_input("Descrizione Turno", value=turno_data.get('Descrizione', ''))

        try:
            default_date = pd.to_datetime(turno_data['Data']).date()
        except (ValueError, TypeError):
            default_date = datetime.date.today()
        data_turno = st.date_input("Data Turno", value=default_date)

        col1, col2 = st.columns(2)
        with col1:
            try:
                default_start_time = datetime.datetime.strptime(str(turno_data['OrarioInizio']), '%H:%M').time()
            except (ValueError, TypeError):
                default_start_time = datetime.time(8, 0)
            ora_inizio = st.time_input("Orario Inizio", value=default_start_time)
        with col2:
            try:
                default_end_time = datetime.datetime.strptime(str(turno_data['OrarioFine']), '%H:%M').time()
            except (ValueError, TypeError):
                default_end_time = datetime.time(17, 0)
            ora_fine = st.time_input("Orario Fine", value=default_end_time)

        col3, col4 = st.columns(2)
        with col3:
            posti_tech = st.number_input("Numero Posti Tecnico", min_value=0, step=1, value=int(turno_data.get('PostiTecnico', 0)))
        with col4:
            posti_aiut = st.number_input("Numero Posti Aiutante", min_value=0, step=1, value=int(turno_data.get('PostiAiutante', 0)))

        st.subheader("Gestione Personale")
        df_prenotazioni = gestionale_data['prenotazioni']
        df_contatti = gestionale_data['contatti']
        personale_nel_turno = df_prenotazioni[df_prenotazioni['ID_Turno'] == turno_id]
        tecnici_nel_turno = personale_nel_turno[personale_nel_turno['RuoloOccupato'] == 'Tecnico']['Matricola'].tolist()
        aiutanti_nel_turno = personale_nel_turno[personale_nel_turno['RuoloOccupato'] == 'Aiutante']['Matricola'].tolist()
        matricola_to_name = pd.Series(df_contatti['Nome Cognome'].values, index=df_contatti['Matricola']).to_dict()
        tecnici_selezionati = st.multiselect("Seleziona Tecnici Assegnati", options=df_contatti['Matricola'].tolist(), default=tecnici_nel_turno, format_func=lambda x: matricola_to_name.get(x, x), key="edit_tecnici")
        aiutanti_selezionati = st.multiselect("Seleziona Aiutanti Assegnati", options=df_contatti['Matricola'].tolist(), default=aiutanti_nel_turno, format_func=lambda x: matricola_to_name.get(x, x), key="edit_aiutanti")

        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("Salva Modifiche")
        with col_cancel:
            if st.form_submit_button("Annulla", type="secondary"):
                del st.session_state['editing_turno_id']
                st.rerun()

    if submitted:
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'Descrizione'] = desc_turno
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'Data'] = pd.to_datetime(data_turno)
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'OrarioInizio'] = ora_inizio.strftime('%H:%M')
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'OrarioFine'] = ora_fine.strftime('%H:%M')
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'PostiTecnico'] = posti_tech
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'PostiAiutante'] = posti_aiut
        df_turni.loc[df_turni['ID_Turno'] == turno_id, 'Tipo'] = tipo_turno

        personale_originale = set(personale_nel_turno['Matricola'].tolist())
        personale_nuovo = set(tecnici_selezionati + aiutanti_selezionati)
        admin_user_matricola = st.session_state.get('authenticated_user', 'N/D')

        personale_rimosso = personale_originale - personale_nuovo
        for matricola in personale_rimosso:
            log_shift_change(gestionale_data, turno_id, "Rimozione Admin", matricola_originale=matricola, matricola_eseguito_da=admin_user_matricola)

        personale_aggiunto = personale_nuovo - personale_originale
        for matricola in personale_aggiunto:
            log_shift_change(gestionale_data, turno_id, "Aggiunta Admin", matricola_subentrante=matricola, matricola_eseguito_da=admin_user_matricola)

        gestionale_data['prenotazioni'] = gestionale_data['prenotazioni'][gestionale_data['prenotazioni']['ID_Turno'] != turno_id]

        nuove_prenotazioni_list = []
        for matricola in tecnici_selezionati:
            nuove_prenotazioni_list.append({'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}_{matricola}", 'ID_Turno': turno_id, 'Matricola': matricola, 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()})
        for matricola in aiutanti_selezionati:
             nuove_prenotazioni_list.append({'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}_{matricola}", 'ID_Turno': turno_id, 'Matricola': matricola, 'RuoloOccupato': 'Aiutante', 'Timestamp': datetime.datetime.now()})

        if nuove_prenotazioni_list:
            df_nuove_prenotazioni = pd.DataFrame(nuove_prenotazioni_list)
            gestionale_data['prenotazioni'] = pd.concat([gestionale_data['prenotazioni'], df_nuove_prenotazioni], ignore_index=True)

        for matricola in personale_rimosso:
            messaggio = f"Sei stato rimosso dal turno '{desc_turno}' del {data_turno.strftime('%d/%m/%Y')} dall'amministratore."
            crea_notifica(gestionale_data, matricola, messaggio)

        if salva_gestionale_async(gestionale_data):
            st.success("Turno aggiornato con successo!")
            st.toast("Le modifiche sono state salvate.")
            del st.session_state['editing_turno_id']
            st.rerun()
        else:
            st.error("Si è verificato un errore durante il salvataggio delle modifiche.")
