import datetime

import google.generativeai as genai
import pandas as pd
import streamlit as st

from modules.data_manager import scrivi_o_aggiorna_risposta
from modules.instrumentation_logic import (
    analyze_domain_terminology,
    find_and_analyze_tags,
)
from modules.notifications import crea_notifica
from modules.shift_management import log_shift_change


@st.cache_data
def to_csv(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv(index=False).encode("utf-8")


def render_debriefing_ui(knowledge_core, matricola_utente, data_riferimento):
    task = st.session_state.debriefing_task
    section_key = task["section_key"]

    def handle_submit(report_text, stato):
        if report_text.strip():
            dati = {
                "descrizione": f"PdL {task['pdl']} - {task['attivita']}",
                "report": report_text,
                "stato": stato,
            }

            success = scrivi_o_aggiorna_risposta(
                dati, matricola_utente, data_riferimento
            )

            if success:
                completed_task_data = {**task, "report": report_text, "stato": stato}

                completed_list = st.session_state.get(
                    f"completed_tasks_{section_key}", []
                )
                completed_list = [t for t in completed_list if t["pdl"] != task["pdl"]]
                completed_list.append(completed_task_data)
                st.session_state[f"completed_tasks_{section_key}"] = completed_list

                if section_key == "yesterday":
                    if "completed_tasks_yesterday" not in st.session_state:
                        st.session_state.completed_tasks_yesterday = []
                    st.session_state.completed_tasks_yesterday.append(
                        completed_task_data
                    )

                st.success("Report inviato con successo al database!")
                del st.session_state.debriefing_task
                st.balloons()
                st.rerun()
            else:
                st.error(
                    "Si è verificato un errore durante il salvataggio del report nel database."
                )
        else:
            st.warning("Il report non può essere vuoto.")

    st.title("📝 Compila Report")
    st.subheader(f"PdL `{task['pdl']}` - {task['attivita']}")
    report_text = st.text_area(
        "Inserisci il tuo report qui:", value=task.get("report", ""), height=200
    )
    stato_options = ["TERMINATA", "SOSPESA", "IN CORSO", "NON SVOLTA"]
    stato_index = (
        stato_options.index(task.get("stato"))
        if task.get("stato") in stato_options
        else 0
    )
    stato = st.selectbox(
        "Stato Finale", stato_options, index=stato_index, key="manual_stato"
    )

    col1, col2 = st.columns(2)
    if col1.button("Invia Report", type="primary"):
        handle_submit(report_text, stato)
    if col2.button("Annulla"):
        del st.session_state.debriefing_task
        st.rerun()


from modules.db_manager import (
    add_booking,
    delete_booking,
    get_all_users,
    get_bookings_for_shift,
    get_shift_by_id,
    update_shift,
)


def render_edit_shift_form():
    """Render the form for editing an existing shift."""
    turno_id = st.session_state.get("editing_turno_id")
    if not turno_id:
        st.error("ID Turno non specificato.")
        return

    # Caricamento dati iniziali
    turno_data = get_shift_by_id(turno_id)
    if not turno_data:
        st.error("Turno non trovato.")
        del st.session_state["editing_turno_id"]
        return

    personale_nel_turno_df = get_bookings_for_shift(turno_id)
    personale_nel_turno = personale_nel_turno_df.set_index("Matricola").to_dict()[
        "RuoloOccupato"
    ]

    tutti_gli_utenti_df = get_all_users()
    utenti_validi = tutti_gli_utenti_df[tutti_gli_utenti_df["Matricola"].notna()]
    opzioni_personale = utenti_validi.set_index("Matricola")["Nome Cognome"].to_dict()

    st.subheader(f"Modifica Turno: {turno_data.get('Descrizione', 'N/A')}")

    with st.form("edit_shift_form"):
        desc_turno = st.text_input(
            "Descrizione Turno", value=turno_data.get("Descrizione", "")
        )
        tipo_turno = st.selectbox(
            "Tipologia",
            ["Reperibilità", "Ferie"],
            index=["Reperibilità", "Ferie"].index(
                turno_data.get("Tipo", "Reperibilità")
            ),
        )

        # Gestione date e ore
        data_inizio_dt = pd.to_datetime(turno_data.get("Data", datetime.date.today()))
        ora_inizio_dt = pd.to_datetime(turno_data.get("OraInizio", "00:00")).time()
        ora_fine_dt = pd.to_datetime(turno_data.get("OraFine", "00:00")).time()

        col1, col2, col3 = st.columns(3)
        with col1:
            data_inizio = st.date_input("Data", value=data_inizio_dt)
        with col2:
            ora_inizio = st.time_input("Ora Inizio", value=ora_inizio_dt)
        with col3:
            ora_fine = st.time_input("Ora Fine", value=ora_fine_dt)

        # Selezione personale
        tecnici_attuali = [m for m, r in personale_nel_turno.items() if r == "Tecnico"]
        aiutanti_attuali = [
            m for m, r in personale_nel_turno.items() if r == "Aiutante"
        ]

        tecnici_selezionati = st.multiselect(
            "Seleziona Tecnici",
            options=opzioni_personale.keys(),
            format_func=lambda matricola: opzioni_personale[matricola],
            default=tecnici_attuali,
        )
        aiutanti_selezionati = st.multiselect(
            "Seleziona Aiutanti",
            options=opzioni_personale.keys(),
            format_func=lambda matricola: opzioni_personale[matricola],
            default=aiutanti_attuali,
        )

        submitted = st.form_submit_button("Salva Modifiche")

        if submitted:
            # 1. Preparazione dei dati aggiornati per il turno
            update_data = {
                "Descrizione": desc_turno,
                "Tipo": tipo_turno,
                "Data": data_inizio.isoformat(),
                "OraInizio": ora_inizio.strftime("%H:%M"),
                "OraFine": ora_fine.strftime("%H:%M"),
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
                        log_shift_change(
                            turno_id,
                            "Rimozione",
                            matricola_originale=matricola,
                            matricola_eseguito_da=st.session_state[
                                "authenticated_user"
                            ],
                        )

                personale_aggiunto = personale_nuovo - personale_originale
                for matricola in personale_aggiunto:
                    ruolo = (
                        "Tecnico" if matricola in tecnici_selezionati else "Aiutante"
                    )
                    booking_data = {
                        "ID_Turno": turno_id,
                        "Matricola": matricola,
                        "RuoloOccupato": ruolo,
                    }
                    if add_booking(booking_data):
                        messaggio = f"Sei stato aggiunto al turno '{desc_turno}'."
                        crea_notifica(matricola, messaggio)
                        log_shift_change(
                            turno_id,
                            "Aggiunta",
                            matricola_subentrante=matricola,
                            matricola_eseguito_da=st.session_state[
                                "authenticated_user"
                            ],
                        )

                st.success("Turno aggiornato con successo!")
                log_shift_change(
                    turno_id,
                    "Modifica Dettagli",
                    matricola_eseguito_da=st.session_state["authenticated_user"],
                )
                del st.session_state["editing_turno_id"]
                st.rerun()
            else:
                st.error("Errore durante l'aggiornamento del turno.")


def revisiona_relazione_con_ia(_testo_originale, _knowledge_base):
    """
    Usa l'IA per revisionare una relazione tecnica, arricchendo la richiesta
    con analisi semantica della strumentazione basata su standard ISA S5.1.
    """
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return {"error": "La chiave API di Gemini non è configurata."}
    if not _testo_originale.strip():
        return {"info": "Il testo della relazione è vuoto."}

    # 1. Analisi semantica della strumentazione e della terminologia
    loops, _ = find_and_analyze_tags(_testo_originale)
    domain_terms = analyze_domain_terminology(_testo_originale)

    technical_summary = ""
    if loops:
        technical_summary += "Analisi del Contesto Strumentale:\n"
        for loop_id, components in loops.items():
            main_variable = components[0]["variable"]
            technical_summary += f"- Loop di Controllo {loop_id} ({main_variable}):\n"
            for comp in components:
                technical_summary += (
                    f"  - {comp['tag']}: È un {comp['type']} ({comp['description']}).\n"
                )

            controller = next(
                (c for c in components if c["type"] == "[CONTROLLORE]"), None
            )
            actuator = next(
                (c for c in components if c["type"] == "[ATUTTATORE]"), None
            )
            if controller and actuator:
                technical_summary += f"  - Relazione: Il controllore {controller['tag']} comanda l'attuatore {actuator['tag']}.\n"
        technical_summary += "\n"

    if domain_terms:
        technical_summary += "Terminologia Specifica Rilevata:\n"
        for term, definition in domain_terms.items():
            technical_summary += f"- {term.upper()}: {definition}.\n"
        technical_summary += "\n"

    # 2. Costruzione del prompt per l'IA
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-flash-latest")

        if technical_summary:
            prompt = f"""
            Sei un Direttore Tecnico di Manutenzione con profonda conoscenza della strumentazione (standard ISA S5.1) e della terminologia di impianto. Il tuo compito è riformulare la seguente relazione scritta da un tecnico, trasformandola in un report professionale, chiaro e tecnicamente consapevole.
            **INFORMAZIONI TECNICHE E TERMINOLOGICHE DA USARE (Know-How):**
            ---
            {technical_summary}
            ---
            Usa queste informazioni per interpretare correttamente le sigle (es. CTG, FCV301) e le relazioni tra i componenti. Riformula il testo per riflettere questa comprensione approfondita.
            **RELAZIONE ORIGINALE DA RIFORMULARE:**
            ---
            {_testo_originale}
            ---
            **RELAZIONE RIFORMULATA (restituisci solo il testo corretto, senza aggiungere titoli o commenti):**
            """
        else:
            prompt = f"""
            Sei un revisore esperto di relazioni tecniche in ambito industriale. Il tuo compito è revisionare e migliorare il seguente testo scritto da un tecnico, mantenendo un tono professionale, chiaro e conciso. Correggi eventuali errori grammaticali o di battitura.
            **RELAZIONE DA REVISIONARE:**
            ---
            {_testo_originale}
            ---
            **RELAZIONE REVISIONATA (restituisci solo il testo corretto, senza aggiungere titoli o commenti):**
            """

        response = model.generate_content(prompt)
        return {"success": True, "text": response.text}
    except Exception as e:
        return {"error": f"Errore durante la revisione IA: {str(e)}"}
