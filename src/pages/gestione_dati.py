"""
Modulo per la gestione diretta dei dati del database e delle esclusioni assegnamenti.
"""

import pandas as pd
import streamlit as st

from modules.data_manager import get_all_assigned_activities
from modules.db_manager import (
    add_assignment_exclusion,
    get_all_users,
    get_table_data,
    get_table_names,
    get_validated_intervention_reports,
    save_table_data,
)


def render_gestione_dati_tab():
    """Renderizza l'interfaccia per la gestione tabellare del database."""
    st.subheader("Gestione Dati")
    st.info(
        "Questa sezione permette di visualizzare e modificare i dati di "
        "qualsiasi tabella del database."
    )

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
    _render_esclusioni_sezione()


def _render_esclusioni_sezione():
    """Sotto-funzione per la gestione delle esclusioni degli assegnamenti."""
    st.subheader("Gestione Esclusioni Assegnamenti")
    st.info(
        "Questa sezione permette di eliminare un assegnamento di attività per "
        "un tecnico e bloccarlo per tutto il team."
    )

    users_df = get_all_users()
    technicians_and_admins = users_df[
        users_df["Ruolo"].isin(["Tecnico", "Amministratore"])
    ]
    technician_names = technicians_and_admins["Nome Cognome"].tolist()
    selected_technician_name = st.selectbox(
        "Seleziona un tecnico", [""] + sorted(technician_names)
    )

    if selected_technician_name:
        selected_row = technicians_and_admins[
            technicians_and_admins["Nome Cognome"] == selected_technician_name
        ]
        if selected_row.empty:
            return

        matricola = selected_row.iloc[0]["Matricola"]
        all_activities = get_all_assigned_activities(matricola, users_df)
        validated_reports_df = get_validated_intervention_reports(matricola)

        validated_activities = set()
        if not validated_reports_df.empty:
            for _, report in validated_reports_df.iterrows():
                validated_activities.add(
                    (report["pdl"], report["descrizione_attivita"])
                )

        unvalidated_activities = [
            a
            for a in all_activities
            if (a["pdl"], a["attivita"]) not in validated_activities
        ]

        if not unvalidated_activities:
            st.info(
                f"Nessuna attività non validata trovata per {selected_technician_name}."
            )
        else:
            _render_assignments_table(unvalidated_activities)


def _render_assignments_table(activities):
    """Renderizza la tabella degli assegnamenti filtrati per il blocco."""
    assignments_df = pd.DataFrame(activities)
    assignments_df["team"] = assignments_df["team"].apply(
        lambda team: ", ".join([member["nome"] for member in team])
    )
    assignments_df["Data Assegnamento"] = pd.to_datetime(
        assignments_df["Data Assegnamento"]
    ).dt.strftime("%d/%m/%Y")
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
            pdl = selected_assignment.iloc[0]["pdl"]
            task = selected_assignment.iloc[0]["attivita"]
            identifier = f"{pdl}-{task}"
            admin_matricola = st.session_state.get("authenticated_user")
            if add_assignment_exclusion(admin_matricola, identifier):
                st.success("Assegnamento bloccato! Ricarica la pagina.")
                st.rerun()
            else:
                st.error("Errore durante il blocco.")
