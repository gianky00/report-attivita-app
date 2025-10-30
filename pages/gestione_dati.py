import streamlit as st
import pandas as pd
from modules.db_manager import (
    get_table_names,
    get_table_data,
    save_table_data,
    get_assignments_by_technician,
    add_assignment_exclusion,
    delete_reports_by_ids,
)

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
    st.info("Questa sezione permette di eliminare e bloccare permanentemente un assegnamento di attività.")

    matricola_utente = st.session_state.get('authenticated_user')
    if matricola_utente:
        assignments_df = get_assignments_by_technician(matricola_utente)
        if assignments_df.empty:
            st.info("Nessun assegnamento da visualizzare.")
        else:
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
                if st.button("Elimina e Blocca Assegnamento Selezionato"):
                    id_attivita_to_block = selected_assignment.iloc[0]["id_attivita"]
                    if add_assignment_exclusion(matricola_utente, id_attivita_to_block):
                        if delete_reports_by_ids([id_attivita_to_block]):
                            st.success("Assegnamento bloccato ed eliminato con successo!")
                            st.rerun()
                        else:
                            st.error("Errore durante l'eliminazione dell'assegnamento.")
                    else:
                        st.error("Errore durante il blocco dell'assegnamento.")
