import streamlit as st
from modules.data_manager import carica_gestionale, salva_gestionale_async
from modules.auth import log_access_attempt
from modules.db_manager import get_reports_to_validate, delete_reports_by_ids, process_and_commit_validated_reports, get_table_names, get_table_data
import pandas as pd
import bcrypt
import datetime
from modules.notifications import crea_notifica

def render_admin_dashboard():
    pass

def render_gestione_account(gestionale_data):
    st.header("Gestione Account Utenti")
    # Logica per la gestione degli account

def render_technician_detail_view():
    pass

def render_report_validation_tab(matricola_utente):
    st.subheader("Validazione Report Attività Inviati")
    reports_to_validate_df = get_reports_to_validate()

    if reports_to_validate_df.empty:
        st.success("🎉 Nessun nuovo report da validare al momento.")
    else:
        st.info(f"Ci sono {len(reports_to_validate_df)} report da validare.")

        # Aggiungi una colonna per la selezione
        reports_to_validate_df['Seleziona'] = False

        # Mostra i report in un form
        with st.form("validation_form"):
            edited_df = st.data_editor(
                reports_to_validate_df,
                key="reports_editor",
                width='stretch',
                column_config={
                    "id_report": st.column_config.Column(disabled=True),
                    "data_compilazione": st.column_config.Column(disabled=True),
                    "testo_report": st.column_config.TextColumn(width="large"),
                    "Seleziona": st.column_config.CheckboxColumn("Seleziona", default=False)
                },
                hide_index=True,
            )

            # Bottoni per validare o eliminare
            col1, col2 = st.columns(2)
            with col1:
                submit_validation = st.form_submit_button("✅ Valida Report Selezionati", type="primary")
            with col2:
                submit_deletion = st.form_submit_button("❌ Elimina Report Selezionati")

        # Logica dopo la sottomissione del form
        if submit_validation:
            selected_reports = edited_df[edited_df['Seleziona']]
            if not selected_reports.empty:
                # Rimuovi la colonna 'Seleziona' prima di processare
                reports_to_process = selected_reports.drop(columns=['Seleziona']).to_dict('records')
                with st.spinner("Salvataggio dei report validati in corso..."):
                    if process_and_commit_validated_reports(reports_to_process):
                        st.success("Report validati e salvati con successo!")
                        st.rerun()
                    else:
                        st.error("Si è verificato un errore durante il salvataggio dei report.")
            else:
                st.warning("Nessun report selezionato per la validazione.")

        if submit_deletion:
            selected_reports = edited_df[edited_df['Seleziona']]
            if not selected_reports.empty:
                ids_to_delete = selected_reports['id_report'].tolist()
                with st.spinner("Eliminazione dei report selezionati in corso..."):
                    if delete_reports_by_ids(ids_to_delete):
                        st.success("Report eliminati con successo!")
                        st.rerun()
                    else:
                        st.error("Si è verificato un errore durante l'eliminazione dei report.")
            else:
                st.warning("Nessun report selezionato per l'eliminazione.")

def render_access_logs_tab(gestionale_data):
    st.subheader("Cronologia Accessi")
    access_logs_df = gestionale_data.get('access_logs', pd.DataFrame())
    if access_logs_df.empty:
        st.info("Nessun log di accesso registrato.")
    else:
        st.dataframe(access_logs_df.sort_values(by="Timestamp", ascending=False), width='stretch')
import streamlit as st

def render_db_admin_tab():
    st.header("Esploratore del Database")
    st.info("Seleziona una tabella per visualizzarne il contenuto.")

    table_names = get_table_names()
    if table_names:
        selected_table = st.selectbox("Seleziona una tabella", table_names)
        if selected_table:
            df = get_table_data(selected_table)
            st.dataframe(df)
    else:
        st.warning("Nessuna tabella trovata nel database.")

def render_crea_nuovo_turno_tab(gestionale_data):
    with st.form("new_shift_form", clear_on_submit=True):
        st.subheader("Dettagli Nuovo Turno")
        tipo_turno = st.selectbox("Tipo Turno", ["Assistenza", "Straordinario"])
        desc_turno = st.text_input("Descrizione Turno (es. 'Mattina', 'Straordinario Sabato')")
        data_turno = st.date_input("Data Turno")
        col1, col2 = st.columns(2)
        with col1: ora_inizio = st.time_input("Orario Inizio", datetime.time(8, 0))
        with col2: ora_fine = st.time_input("Orario Fine", datetime.time(17, 0))
        col3, col4 = st.columns(2)
        with col3: posti_tech = st.number_input("Numero Posti Tecnico", min_value=0, step=1)
        with col4: posti_aiut = st.number_input("Numero Posti Aiutante", min_value=0, step=1)
        if st.form_submit_button("Crea Turno"):
            if not desc_turno: st.error("La descrizione non può essere vuota.")
            else:
                new_id = f"T_{int(datetime.datetime.now().timestamp())}"
                nuovo_turno = pd.DataFrame([{'ID_Turno': new_id, 'Descrizione': desc_turno, 'Data': pd.to_datetime(data_turno), 'OrarioInizio': ora_inizio.strftime('%H:%M'), 'OrarioFine': ora_fine.strftime('%H:%M'), 'PostiTecnico': posti_tech, 'PostiAiutante': posti_aiut, 'Tipo': tipo_turno}])
                gestionale_data['turni'] = pd.concat([gestionale_data['turni'], nuovo_turno], ignore_index=True)
                df_contatti = gestionale_data.get('contatti')
                if df_contatti is not None:
                    utenti_da_notificare = df_contatti['Matricola'].tolist()
                    messaggio = f"📢 Nuovo turno disponibile: '{desc_turno}' il {pd.to_datetime(data_turno).strftime('%d/%m/%Y')}."
                    for matricola in utenti_da_notificare: crea_notifica(gestionale_data, matricola, messaggio)
                if salva_gestionale_async(gestionale_data):
                    st.success(f"Turno '{desc_turno}' creato con successo! Notifiche inviate.")
                    st.rerun()
                else: st.error("Errore nel salvataggio del nuovo turno.")

def render_gestione_account(gestionale_data):
    st.header("Gestione Account Utenti")
    df_contatti = gestionale_data['contatti']

    # Visualizzazione e modifica utenti
    st.subheader("Elenco Utenti")
    edited_df = st.data_editor(df_contatti, num_rows="dynamic", key="users_editor")

    if st.button("Salva Modifiche"):
        gestionale_data['contatti'] = edited_df
        if salva_gestionale_async(gestionale_data):
            st.success("Modifiche salvate con successo!")
            st.rerun()
        else:
            st.error("Errore durante il salvataggio delle modifiche.")

    st.divider()

    # Creazione nuovo utente
    st.subheader("Crea Nuovo Utente")
    with st.form("new_user_form", clear_on_submit=True):
        nuova_matricola = st.text_input("Matricola")
        nuovo_nome = st.text_input("Nome Cognome")
        nuovo_ruolo = st.selectbox("Ruolo", ["Tecnico", "Aiutante", "Amministratore"])
        nuova_password = st.text_input("Password", type="password")

        submitted = st.form_submit_button("Crea Utente")
        if submitted:
            if nuova_matricola and nuovo_nome and nuova_password:
                hashed_password = bcrypt.hashpw(nuova_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                nuovo_utente = pd.DataFrame([{'Matricola': nuova_matricola, 'Nome Cognome': nuovo_nome, 'Ruolo': nuovo_ruolo, 'PasswordHash': hashed_password, '2FA_Secret': None, 'Link Attività': ''}])
                gestionale_data['contatti'] = pd.concat([df_contatti, nuovo_utente], ignore_index=True)
                if salva_gestionale_async(gestionale_data):
                    st.success(f"Utente {nuovo_nome} creato con successo!")
                    st.rerun()
                else:
                    st.error("Errore durante la creazione dell'utente.")
            else:
                st.warning("Tutti i campi sono obbligatori.")

def render_technician_detail_view():
    st.header("Dettaglio Tecnico")
    st.info("Questa sezione è in costruzione.")
