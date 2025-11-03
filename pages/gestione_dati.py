import streamlit as st
import pandas as pd
import datetime
from modules.db_manager import (
    get_table_names,
    get_table_data,
    save_table_data,
    add_assignment_exclusion,
    get_all_users,
    get_validated_intervention_reports,
)
from modules.data_manager import get_all_assigned_activities

def render_gestione_dati_tab():
    st.subheader("Gestione Dati")
    st.info("Questa sezione permette di visualizzare e modificare i dati di qualsiasi tabella del database.")

    table_names = get_table_names()
    if not table_names:
        st.warning("Nessuna tabella trovata nel database.")
        return

    selected_table = st.selectbox("Seleziona una tabella", table_names)

    if selected_table:
        df = get_table_data(selected_table)
        st.write(f"Dati della tabella: **{selected_table}**")
        edited_df = st.data_editor(df, num_rows="dynamic")

        if st.button("Salva Modifiche"):
            if save_table_data(edited_df, selected_table):
                st.success("Dati salvati con successo!")
            else:
                st.error("Errore durante il salvataggio dei dati.")

    st.divider()

    st.subheader("Gestione Esclusioni Assegnamenti")
    st.info("Questa sezione permette di eliminare un assegnamento di attività per un tecnico e bloccarlo per tutto il team.")

    users_df = get_all_users()
    technicians_and_admins = users_df[users_df['Ruolo'].isin(['Tecnico', 'Amministratore'])]
    technician_names = technicians_and_admins['Nome Cognome'].tolist()
    selected_technician_name = st.selectbox("Seleziona un tecnico", [""] + sorted(technician_names))


    if selected_technician_name:
        selected_technician_matricola = technicians_and_admins[technicians_and_admins['Nome Cognome'] == selected_technician_name].iloc[0]['Matricola']

        all_activities = get_all_assigned_activities(selected_technician_matricola, users_df)

        validated_reports_df = get_validated_intervention_reports(selected_technician_matricola)
        validated_activities = set()
        if not validated_reports_df.empty:
            for _, report in validated_reports_df.iterrows():
                validated_activities.add((report['pdl'], report['descrizione_attivita']))

        unvalidated_activities = [
            activity for activity in all_activities
            if (activity['pdl'], activity['attivita']) not in validated_activities
        ]

        if not unvalidated_activities:
            st.info(f"Nessuna attività non validata trovata per {selected_technician_name}.")
        else:
            assignments_df = pd.DataFrame(unvalidated_activities)
            assignments_df["team"] = assignments_df["team"].apply(lambda team: ", ".join([member['nome'] for member in team]))
            assignments_df["Data Assegnamento"] = pd.to_datetime(assignments_df["Data Assegnamento"]).dt.strftime('%d/%m/%Y')
            assignments_df["seleziona"] = False

            edited_assignments_df = st.data_editor(
                assignments_df,
                column_config={
                    "seleziona": st.column_config.CheckboxColumn(
                        "Seleziona", help="Seleziona per bloccare l'assegnamento."
                    ),
                },
                disabled=assignments_df.columns.drop("seleziona"),
            )

            selected_assignment = edited_assignments_df[edited_assignments_df["seleziona"]]
            if not selected_assignment.empty:
                if st.button("Blocca Assegnamento Selezionato"):
                    pdl_to_block = selected_assignment.iloc[0]["pdl"]
                    attivita_to_block = selected_assignment.iloc[0]["attivita"]
                    activity_identifier = f"{pdl_to_block}-{attivita_to_block}"
                    admin_matricola = st.session_state.get('authenticated_user')
                    if add_assignment_exclusion(admin_matricola, activity_identifier):
                        st.success("Assegnamento bloccato con successo! Ricarica la pagina per vedere l'attività scomparire.")
                        st.rerun()
                    else:
                        st.error("Errore durante il blocco dell'assegnamento.")
