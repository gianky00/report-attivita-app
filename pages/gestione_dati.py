import streamlit as st
import pandas as pd
import datetime
from modules.db_manager import (
    get_table_names,
    get_table_data,
    save_table_data,
    add_assignment_exclusion,
    get_all_users,
)
from modules.data_manager import trova_attivita

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
    technicians = users_df[users_df['Ruolo'] == 'Tecnico']
    technician_names = technicians['Nome Cognome'].tolist()
    selected_technician_name = st.selectbox("Seleziona un tecnico", [""] + technician_names)


    if selected_technician_name:
        selected_technician_matricola = technicians[technicians['Nome Cognome'] == selected_technician_name].iloc[0]['Matricola']

        today = datetime.date.today()
        assignments = trova_attivita(selected_technician_matricola, today.day, today.month, today.year, users_df)

        if not assignments:
            st.info(f"Nessun assegnamento da visualizzare per {selected_technician_name} per la data di oggi.")
        else:
            assignments_df = pd.DataFrame(assignments)
            assignments_df["seleziona"] = False

            edited_assignments_df = st.data_editor(
                assignments_df,
                column_config={
                    "seleziona": st.column_config.CheckboxColumn(
                        "Seleziona", help="Seleziona per bloccare l'assegnamento."
                    )
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
