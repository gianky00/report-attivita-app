import streamlit as st
import pandas as pd
import datetime
import bcrypt
from modules.db_manager import (
    get_technician_performance_data,
    get_interventions_for_technician,
    get_reports_to_validate,
    delete_reports_by_ids,
    process_and_commit_validated_reports,
    get_unvalidated_relazioni,
    process_and_commit_validated_relazioni,
)
from modules.data_manager import (
    carica_gestionale,
    salva_gestionale_async,
)
from modules.notifications import crea_notifica
import learning_module

# --- Funzioni di supporto ---
@st.cache_data
def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# --- Funzioni di rendering per le sotto-schede ---

def render_technician_detail_view():
    """Mostra la vista di dettaglio per un singolo tecnico."""
    technician_matricola = st.session_state['detail_technician_matricola']
    start_date = st.session_state['detail_start_date']
    end_date = st.session_state['detail_end_date']

    df_contatti = carica_gestionale()['contatti']
    technician_name = df_contatti[df_contatti['Matricola'] == technician_matricola].iloc[0]['Nome Cognome']

    st.title(f"Dettaglio Performance: {technician_name}")
    st.markdown(f"Periodo: **{start_date.strftime('%d/%m/%Y')}** - **{end_date.strftime('%d/%m/%Y')}**")

    if 'performance_results' in st.session_state:
        performance_df = st.session_state['performance_results']['df']
        if technician_name in performance_df.index:
            technician_metrics = performance_df.loc[technician_name]
            st.markdown("#### Riepilogo Metriche")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Totale Interventi", technician_metrics['Totale Interventi'])
            c2.metric("Tasso Completamento", f"{technician_metrics['Tasso Completamento (%)']}%")
            c3.metric("Ritardo Medio (gg)", technician_metrics['Ritardo Medio Compilazione (gg)'])
            c4.metric("Report Sbrigativi", technician_metrics['Report Sbrigativi'])
            st.markdown("---")

    if st.button("⬅️ Torna alla Dashboard"):
        del st.session_state['detail_technician_matricola']
        del st.session_state['detail_start_date']
        del st.session_state['detail_end_date']
        st.rerun()

    technician_interventions = get_interventions_for_technician(technician_matricola, start_date, end_date)

    if technician_interventions.empty:
        st.warning("Nessun intervento trovato per questo tecnico nel periodo selezionato.")
        return

    st.markdown("### Riepilogo Interventi")
    technician_interventions['Data'] = pd.to_datetime(technician_interventions['Data_Riferimento_dt']).dt.strftime('%d/%m/%Y')
    st.dataframe(technician_interventions[['Data', 'PdL', 'Descrizione', 'Stato', 'Report']])

    st.download_button(
        label="📥 Esporta Dettaglio CSV",
        data=to_csv(technician_interventions),
        file_name=f"dettaglio_{technician_name}.csv",
        mime='text/csv',
    )

    st.markdown("---")
    st.markdown("### Analisi Avanzata")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Ripartizione Esiti")
        status_counts = technician_interventions['Stato'].value_counts()
        if not status_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
            st.pyplot(fig)
        else:
            st.info("Nessun dato sullo stato disponibile per creare il grafico.")
    with col2:
        st.markdown("#### Andamento Attività nel Tempo")
        interventions_by_day = technician_interventions.groupby(pd.to_datetime(technician_interventions['Data_Riferimento_dt']).dt.date).size()
        interventions_by_day.index.name = 'Data'
        st.bar_chart(interventions_by_day)

    st.markdown("#### Analisi Qualitativa: Report Sbrigativi")
    rushed_reports_df = technician_interventions[technician_interventions['Report'].str.len() < 20]
    if not rushed_reports_df.empty:
        st.warning(f"Trovati {len(rushed_reports_df)} report potenzialmente sbrigativi:")
        for _, row in rushed_reports_df.iterrows():
            st.info(f"**Data:** {row['Data']} - **PdL:** {row['PdL']} - **Report:** *'{row['Report']}'*")
    else:
        st.success("Nessun report sbrigativo trovato in questo periodo.")

def render_report_validation_tab(user_matricola):
    st.subheader("Validazione Report Tecnici")
    st.info("""
    Questa sezione permette di validare i report inviati dai tecnici.
    - I report in attesa vengono caricati automaticamente.
    - Puoi modificare il **Testo Report** e lo **Stato Attività** direttamente nella tabella.
    - Seleziona uno o più report e clicca "Cancella" per rimuoverli definitivamente in caso di errore.
    - Clicca "Valida e Salva Modifiche" per processare i report, scriverli su Excel e rimuoverli da questa coda.
    """)

    reports_df = get_reports_to_validate()

    if reports_df.empty:
        st.success("🎉 Nessun nuovo report da validare al momento.")
        return

    reports_df.insert(0, "delete", False)
    st.markdown("---")
    st.markdown(f"**Ci sono {len(reports_df)} report in attesa di validazione.**")

    disabled_cols = [
        "id_report", "pdl", "descrizione_attivita", "matricola_tecnico",
        "nome_tecnico", "data_compilazione", "data_riferimento_attivita"
    ]

    edited_df = st.data_editor(
        reports_df,
        key="validation_editor",
        num_rows="dynamic",
        width='stretch',
        column_config={
            "delete": st.column_config.CheckboxColumn("Cancella", help="Seleziona per cancellare il report.", default=False),
            "id_report": None,
            "pdl": st.column_config.Column("PdL", width="small"),
            "descrizione_attivita": st.column_config.Column("Descrizione", width="medium"),
            "matricola_tecnico": None,
            "nome_tecnico": st.column_config.Column("Tecnico", width="small"),
            "stato_attivita": st.column_config.Column("Stato", width="small"),
            "testo_report": st.column_config.TextColumn("Report", width="large"),
            "data_compilazione": st.column_config.DatetimeColumn("Data Compilazione", format="DD/MM/YYYY HH:mm", width="small"),
            "data_riferimento_attivita": None,
        },
        disabled=disabled_cols
    )

    st.markdown("---")
    col1, col2, col3 = st.columns([2, 2, 5])

    with col1:
        reports_to_validate_df = edited_df[edited_df["delete"] == False]
        if not reports_to_validate_df.empty:
            if st.button("✅ Valida e Salva Modifiche", type="primary", use_container_width=True):
                reports_to_process = reports_to_validate_df.drop(columns=['delete'])
                with st.spinner("Salvataggio dei report validati in corso..."):
                    if process_and_commit_validated_reports(reports_to_process.to_dict('records')):
                        st.success("Report validati e salvati con successo!")
                        st.rerun()
                    else:
                        st.error("Si è verificato un errore durante il salvataggio dei report.")

    with col2:
        reports_to_delete_df = edited_df[edited_df["delete"] == True]
        if not reports_to_delete_df.empty:
            if st.button(f"❌ Cancella {len(reports_to_delete_df)} Report", use_container_width=True):
                ids_to_delete = reports_to_delete_df["id_report"].tolist()
                if delete_reports_by_ids(ids_to_delete):
                    st.success(f"{len(ids_to_delete)} report sono stati cancellati con successo.")
                    st.rerun()
                else:
                    st.error("Errore durante la cancellazione dei report.")

def render_gestione_account(gestionale_data):
    df_contatti = gestionale_data['contatti']
    st.subheader("Modifica Utenti Esistenti")
    search_term = st.text_input("Cerca utente per nome o matricola...", key="user_search_admin")
    if search_term:
        df_contatti = df_contatti[
            df_contatti['Nome Cognome'].str.contains(search_term, case=False, na=False) |
            df_contatti['Matricola'].astype(str).str.contains(search_term, case=False, na=False)
        ]

    if 'editing_user_matricola' not in st.session_state:
        st.session_state.editing_user_matricola = None

    if st.session_state.editing_user_matricola:
        user_to_edit_series = df_contatti[df_contatti['Matricola'] == st.session_state.editing_user_matricola]
        if not user_to_edit_series.empty:
            user_to_edit = user_to_edit_series.iloc[0]
            user_name = user_to_edit['Nome Cognome']
            with st.form(key="edit_user_form"):
                st.subheader(f"Modifica Utente: {user_name} ({st.session_state.editing_user_matricola})")
                ruoli_disponibili = ["Tecnico", "Aiutante", "Amministratore"]
                try:
                    current_role_index = ruoli_disponibili.index(user_to_edit['Ruolo'])
                except ValueError:
                    current_role_index = 0
                new_role = st.selectbox("Nuovo Ruolo", options=ruoli_disponibili, index=current_role_index)
                is_placeholder_current = pd.isna(user_to_edit.get('PasswordHash'))
                is_placeholder_new = st.checkbox("Resetta Account (forza creazione nuova password)", value=is_placeholder_current)
                new_password = ""
                if not is_placeholder_new:
                    new_password = st.text_input("Nuova Password (lasciare vuoto per non modificare)", type="password")
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Salva Modifiche", type="primary"):
                        user_idx = df_contatti[df_contatti['Matricola'] == st.session_state.editing_user_matricola].index[0]
                        df_contatti.loc[user_idx, 'Ruolo'] = new_role
                        if is_placeholder_new:
                            df_contatti.loc[user_idx, 'PasswordHash'] = None
                            st.success(f"Account di {user_name} resettato. Dovrà creare una nuova password al prossimo accesso.")
                        elif new_password:
                            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                            df_contatti.loc[user_idx, 'PasswordHash'] = hashed.decode('utf-8')
                            st.success(f"Password per {user_name} aggiornata.")
                        salva_gestionale_async(gestionale_data)
                        st.session_state.editing_user_matricola = None
                        st.toast("Modifiche salvate!")
                        st.rerun()
                with col2:
                    if st.form_submit_button("Annulla"):
                        st.session_state.editing_user_matricola = None
                        st.rerun()
        else:
            st.error("Utente non trovato. Ricaricamento...")
            st.session_state.editing_user_matricola = None
            st.rerun()
    else:
        for index, user in df_contatti.iterrows():
            user_name = user['Nome Cognome']
            user_matricola = user['Matricola']
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**{user_name}** (`{user_matricola}`)")
                with col2:
                    is_placeholder = pd.isna(user.get('PasswordHash'))
                    status = "Da Attivare (primo accesso)" if is_placeholder else "Attivo"
                    st.markdown(f"*{user['Ruolo']}* - Stato: *{status}*")
                with col3:
                    if st.button("Modifica", key=f"edit_{user_matricola}"):
                        st.session_state.editing_user_matricola = user_matricola
                        st.rerun()
                has_2fa = '2FA_Secret' in user and pd.notna(user['2FA_Secret']) and user['2FA_Secret']
                if has_2fa:
                    with col1:
                        if st.button("Resetta 2FA", key=f"reset_2fa_{user_matricola}", help="Rimuove la 2FA per questo utente. Dovrà configurarla di nuovo al prossimo accesso."):
                            user_idx = df_contatti[df_contatti['Matricola'] == user_matricola].index[0]
                            df_contatti.loc[user_idx, '2FA_Secret'] = None
                            salva_gestionale_async(gestionale_data)
                            st.success(f"2FA resettata per {user_name}.")
                            st.rerun()
    st.divider()

    with st.expander("Crea Nuovo Utente"):
        with st.form("new_user_form", clear_on_submit=True):
            st.subheader("Dati Nuovo Utente")
            c1, c2, c3 = st.columns(3)
            new_nome = c1.text_input("Nome*")
            new_cognome = c2.text_input("Cognome*")
            new_matricola = c3.text_input("Matricola*")
            new_ruolo = st.selectbox("Ruolo", ["Tecnico", "Aiutante", "Amministratore"])
            submitted_new_user = st.form_submit_button("Crea Utente")
            if submitted_new_user:
                if new_nome and new_cognome and new_matricola:
                    if str(new_matricola) in df_contatti['Matricola'].astype(str).tolist():
                        st.error(f"Errore: La matricola '{new_matricola}' esiste già.")
                    else:
                        nome_completo = f"{new_nome.strip()} {new_cognome.strip()}"
                        new_user_data = {
                            'Matricola': str(new_matricola),
                            'Nome Cognome': nome_completo,
                            'Ruolo': new_ruolo,
                            'PasswordHash': None,
                            'Link Attività': ''
                        }
                        for col in df_contatti.columns:
                            if col not in new_user_data:
                                new_user_data[col] = None
                        nuovo_utente_df = pd.DataFrame([new_user_data])
                        gestionale_data['contatti'] = pd.concat([df_contatti, nuovo_utente_df], ignore_index=True)
                        if salva_gestionale_async(gestionale_data):
                            st.success(f"Utente '{nome_completo}' creato con successo! Dovrà impostare la password al primo accesso.")
                            st.rerun()
                        else:
                            st.error("Errore durante il salvataggio del nuovo utente.")
                else:
                    st.warning("Nome, Cognome e Matricola sono obbligatori.")

def render_access_logs_tab(gestionale_data):
    st.header("Cronologia Accessi al Sistema")
    st.info("Questa sezione mostra tutti i tentativi di accesso registrati, dal più recente al più vecchio.")
    logs_df = gestionale_data.get('access_logs')
    if logs_df is None or logs_df.empty:
        st.warning("Nessun tentativo di accesso registrato.")
        return

    if 'timestamp' in logs_df.columns:
        logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
        logs_df = logs_df.sort_values(by='timestamp', ascending=False)

    st.subheader("Filtra Cronologia")
    all_users = sorted(logs_df['username'].unique().tolist())
    selected_users = st.multiselect("Filtra per Utente:", options=all_users, default=[])
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data Inizio", value=None)
    with col2:
        end_date = st.date_input("Data Fine", value=None)

    filtered_df = logs_df.copy()
    if selected_users:
        filtered_df = filtered_df[filtered_df['username'].isin(selected_users)]
    if start_date:
        filtered_df = filtered_df[filtered_df['timestamp'].dt.date >= start_date]
    if end_date:
        filtered_df = filtered_df[filtered_df['timestamp'].dt.date <= end_date]

    st.divider()
    st.subheader("Risultati")
    if filtered_df.empty:
        st.info("Nessun record trovato per i filtri selezionati.")
    else:
        display_df = filtered_df.copy()
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%d/%m/%Y %H:%M:%S')
        display_df.rename(columns={'timestamp': 'Data e Ora', 'username': 'Nome Utente/Matricola', 'status': 'Esito'}, inplace=True)
        st.dataframe(display_df[['Data e Ora', 'Nome Utente/Matricola', 'Esito']], width='stretch')

# --- Funzione principale della dashboard Admin ---

def render_admin_dashboard(gestionale_data, matricola_utente):
    st.subheader("Dashboard di Controllo")
    if st.session_state.get('detail_technician_matricola'):
        render_technician_detail_view()
    else:
        main_admin_tabs = st.tabs(["Dashboard Caposquadra", "Dashboard Tecnica"])
        with main_admin_tabs[0]:
            caposquadra_tabs = st.tabs(["Performance Team", "Crea Nuovo Turno", "Gestione Dati", "Validazione Report"])
            with caposquadra_tabs[0]:
                st.markdown("#### Seleziona Intervallo Temporale")
                if 'perf_start_date' not in st.session_state:
                    st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=30)
                if 'perf_end_date' not in st.session_state:
                    st.session_state.perf_end_date = datetime.date.today()
                c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
                if c1.button("Oggi"):
                    st.session_state.perf_start_date = st.session_state.perf_end_date = datetime.date.today()
                if c2.button("Ultimi 7 giorni"):
                    st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=7)
                    st.session_state.perf_end_date = datetime.date.today()
                if c3.button("Ultimi 30 giorni"):
                    st.session_state.perf_start_date = datetime.date.today() - datetime.timedelta(days=30)
                    st.session_state.perf_end_date = datetime.date.today()
                col1, col2 = st.columns(2)
                with col1:
                    st.date_input("Data di Inizio", key="perf_start_date", format="DD/MM/YYYY")
                with col2:
                    st.date_input("Data di Fine", key="perf_end_date", format="DD/MM/YYYY")
                start_datetime, end_datetime = st.session_state.perf_start_date, st.session_state.perf_end_date
                if st.button("📊 Calcola Performance", type="primary"):
                    with st.spinner("Calcolo delle performance in corso..."):
                        performance_df = get_technician_performance_data(start_datetime, end_datetime)
                    st.session_state['performance_results'] = {'df': performance_df, 'start_date': pd.to_datetime(start_datetime), 'end_date': pd.to_datetime(end_datetime)}
                if 'performance_results' in st.session_state:
                    results = st.session_state['performance_results']
                    performance_df = results['df']
                    if performance_df.empty:
                        st.info("Nessun dato di performance trovato per il periodo selezionato.")
                    else:
                        st.markdown("---")
                        st.markdown("### Riepilogo Performance del Team")
                        total_interventions_team = performance_df['Totale Interventi'].sum()
                        total_rushed_reports_team = performance_df['Report Sbrigativi'].sum()
                        total_completed_interventions = (performance_df['Tasso Completamento (%)'].astype(float) / 100) * performance_df['Totale Interventi']
                        avg_completion_rate_team = (total_completed_interventions.sum() / total_interventions_team) * 100 if total_interventions_team > 0 else 0
                        st.download_button(label="📥 Esporta Riepilogo CSV", data=to_csv(performance_df), file_name='performance_team.csv', mime='text/csv')
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Totale Interventi", f"{total_interventions_team}")
                        c2.metric("Tasso Completamento Medio", f"{avg_completion_rate_team:.1f}%")
                        c3.metric("Report Sbrigativi", f"{total_rushed_reports_team}")
                        st.markdown("#### Dettaglio Performance per Tecnico")
                        for index, row in performance_df.iterrows():
                            st.write(f"**Tecnico:** {index}")
                            st.dataframe(row.to_frame().T)
                            if st.button(f"Vedi Dettaglio Interventi di {index}", key=f"detail_{index}"):
                                st.session_state.update({'detail_technician_matricola': row['Matricola'], 'detail_start_date': results['start_date'], 'detail_end_date': results['end_date']})
                                st.rerun()
            with caposquadra_tabs[1]:
                with st.form("new_shift_form", clear_on_submit=True):
                    st.subheader("Dettagli Nuovo Turno")
                    tipo_turno = st.selectbox("Tipo Turno", ["Assistenza", "Straordinario"])
                    desc_turno = st.text_input("Descrizione Turno (es. 'Mattina', 'Straordinario Sabato')")
                    data_turno = st.date_input("Data Turno")
                    col1, col2 = st.columns(2)
                    with col1:
                        ora_inizio = st.time_input("Orario Inizio", datetime.time(8, 0))
                    with col2:
                        ora_fine = st.time_input("Orario Fine", datetime.time(17, 0))
                    col3, col4 = st.columns(2)
                    with col3:
                        posti_tech = st.number_input("Numero Posti Tecnico", min_value=0, step=1)
                    with col4:
                        posti_aiut = st.number_input("Numero Posti Aiutante", min_value=0, step=1)
                    if st.form_submit_button("Crea Turno"):
                        if not desc_turno:
                            st.error("La descrizione non può essere vuota.")
                        else:
                            new_id = f"T_{int(datetime.datetime.now().timestamp())}"
                            nuovo_turno = pd.DataFrame([{'ID_Turno': new_id, 'Descrizione': desc_turno, 'Data': pd.to_datetime(data_turno), 'OrarioInizio': ora_inizio.strftime('%H:%M'), 'OrarioFine': ora_fine.strftime('%H:%M'), 'PostiTecnico': posti_tech, 'PostiAiutante': posti_aiut, 'Tipo': tipo_turno}])
                            gestionale_data['turni'] = pd.concat([gestionale_data['turni'], nuovo_turno], ignore_index=True)
                            df_contatti = gestionale_data.get('contatti')
                            if df_contatti is not None:
                                utenti_da_notificare = df_contatti['Matricola'].tolist()
                                messaggio = f"📢 Nuovo turno disponibile: '{desc_turno}' il {pd.to_datetime(data_turno).strftime('%d/%m/%Y')}."
                                for matricola in utenti_da_notificare:
                                    crea_notifica(gestionale_data, matricola, messaggio)
                            if salva_gestionale_async(gestionale_data):
                                st.success(f"Turno '{desc_turno}' creato con successo! Notifiche inviate.")
                                st.rerun()
                            else:
                                st.error("Errore nel salvataggio del nuovo turno.")
            with caposquadra_tabs[2]:
                st.header("Gestione e Sincronizzazione Dati")
                st.info("Questa sezione permette di avviare la sincronizzazione bidirezionale tra il file Excel `ATTIVITA_PROGRAMMATE.xlsm` e il database interno, e di lanciare le macro di aggiornamento.")
                st.warning("**Funzionamento:**\n- La sincronizzazione aggiorna sia il database che il file Excel `ATTIVITA_PROGRAMMATE.xlsm`.\n- Al termine, viene eseguita automaticamente la macro `AggiornaAttivitaProgrammate_Veloce` dal file `Database_Report_Attivita.xlsm`.")
                if st.button("🔄 Sincronizza DB <-> Excel e Avvia Macro", type="primary", help="Avvia la sincronizzazione bidirezionale e l'esecuzione della macro."):
                    from sincronizzatore import sincronizza_db_excel
                    with st.spinner("Sincronizzazione in corso... Non chiudere la pagina."):
                        success, message = sincronizza_db_excel()
                        if success:
                            st.success("Operazione completata!")
                            st.info(message)
                            st.cache_data.clear()
                        else:
                            st.error(f"Errore durante l'operazione: {message}")
            with caposquadra_tabs[3]:
                validation_tabs = st.tabs(["Validazione Report Attività", "Validazione Relazioni"])
                with validation_tabs[0]:
                    render_report_validation_tab(matricola_utente)
                with validation_tabs[1]:
                    st.subheader("Validazione Relazioni Inviate")
                    unvalidated_relazioni_df = get_unvalidated_relazioni()
                    if unvalidated_relazioni_df.empty:
                        st.success("🎉 Nessuna nuova relazione da validare al momento.")
                    else:
                        st.info(f"Ci sono {len(unvalidated_relazioni_df)} relazioni da validare.")
                        if 'data_intervento' in unvalidated_relazioni_df.columns:
                            unvalidated_relazioni_df['data_intervento'] = pd.to_datetime(unvalidated_relazioni_df['data_intervento'], errors='coerce').dt.strftime('%d/%m/%Y')
                        if 'timestamp_invio' in unvalidated_relazioni_df.columns:
                            unvalidated_relazioni_df['timestamp_invio'] = pd.to_datetime(unvalidated_relazioni_df['timestamp_invio'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
                        edited_relazioni_df = st.data_editor(
                            unvalidated_relazioni_df,
                            num_rows="dynamic",
                            key="relazioni_editor",
                            width='stretch',
                            column_config={
                                "corpo_relazione": st.column_config.TextColumn(width="large"),
                                "id_relazione": st.column_config.Column(disabled=True),
                                "timestamp_invio": st.column_config.Column(disabled=True),
                            }
                        )
                        if st.button("✅ Salva Relazioni Validate", type="primary"):
                            with st.spinner("Salvataggio delle relazioni in corso..."):
                                if process_and_commit_validated_relazioni(edited_relazioni_df, matricola_utente):
                                    st.success("Relazioni validate e salvate con successo!")
                                    st.rerun()
                                else:
                                    st.error("Si è verificato un errore durante il salvataggio delle relazioni.")
        with main_admin_tabs[1]:
            tecnica_tabs = st.tabs(["Gestione Account", "Cronologia Accessi", "Gestione IA"])
            with tecnica_tabs[0]:
                render_gestione_account(gestionale_data)
            with tecnica_tabs[1]:
                render_access_logs_tab(gestionale_data)
            with tecnica_tabs[2]:
                st.header("Gestione Intelligenza Artificiale")
                ia_sub_tabs = st.tabs(["Revisione Conoscenze", "Memoria IA"])
                with ia_sub_tabs[0]:
                    st.markdown("### 🧠 Revisione Voci del Knowledge Core")
                    unreviewed_entries = learning_module.load_unreviewed_knowledge()
                    pending_entries = [e for e in unreviewed_entries if e.get('stato') == 'in attesa di revisione']
                    if not pending_entries:
                        st.success("🎉 Nessuna nuova voce da revisionare!")
                    else:
                        st.info(f"Ci sono {len(pending_entries)} nuove voci suggerite dai tecnici da revisionare.")
                    for i, entry in enumerate(pending_entries):
                        with st.expander(f"**Voce ID:** `{entry['id']}` - **Attività:** {entry['attivita_collegata']}", expanded=i==0):
                            st.markdown(f"*Suggerito da: **{entry['suggerito_da']}** il {datetime.datetime.fromisoformat(entry['data_suggerimento']).strftime('%d/%m/%Y %H:%M')}*")
                            st.markdown(f"*PdL di riferimento: `{entry['pdl']}`*")
                            st.write("**Dettagli del report compilato:**"); st.json(entry['dettagli_report'])
                            st.markdown("---"); st.markdown("**Azione di Integrazione**")
                            col1, col2 = st.columns(2)
                            with col1:
                                new_equipment_key = st.text_input("Nuova Chiave Attrezzatura (es. 'motore_elettrico')", key=f"key_{entry['id']}")
                                new_display_name = st.text_input("Nome Visualizzato (es. 'Motore Elettrico')", key=f"disp_{entry['id']}")
                            with col2:
                                if st.button("✅ Integra nel Knowledge Core", key=f"integrate_{entry['id']}", type="primary"):
                                    if new_equipment_key and new_display_name:
                                        first_question = {"id": "sintomo_iniziale", "text": "Qual era il sintomo principale?", "options": {k.lower().replace(' ', '_'): v for k, v in entry['dettagli_report'].items()}}
                                        details = {"equipment_key": new_equipment_key, "display_name": new_display_name, "new_question": first_question}
                                        result = learning_module.integrate_knowledge(entry['id'], details)
                                        if result.get("success"):
                                            st.success(f"Voce '{entry['id']}' integrata con successo!"); st.cache_data.clear(); st.rerun()
                                        else:
                                            st.error(f"Errore integrazione: {result.get('error')}")
                                    else:
                                        st.warning("Per integrare, fornisci sia la chiave che il nome visualizzato.")
                with ia_sub_tabs[1]:
                    st.subheader("Gestione Modello IA")
                    st.info("Usa questo pulsante per aggiornare la base di conoscenza dell'IA con le nuove relazioni inviate. L'operazione potrebbe richiedere alcuni minuti.")
                    if st.button("🧠 Aggiorna Memoria IA", type="primary"):
                        with st.spinner("Ricostruzione dell'indice in corso..."):
                            result = learning_module.build_knowledge_base()
                        if result.get("success"):
                            st.success(result.get("message")); st.cache_data.clear()
                        else:
                            st.error(result.get("message"))
