"""
Interfaccia per la consultazione dei log di accesso al sistema.
Include filtri per utente, data e esito del login.
"""

import pandas as pd
import streamlit as st

from src.modules.db_manager import get_access_logs


def render_access_logs_tab():
    """Visualizza e filtra i log di accesso al sistema."""
    st.subheader("Cronologia Accessi al Sistema")
    st.info(
        "Questa sezione mostra tutti i tentativi di accesso registrati, dal più recente al più vecchio."
    )

    logs_df = get_access_logs()

    if logs_df.empty:
        st.warning("Nessun tentativo di accesso registrato.")
        return

    logs_df["timestamp"] = pd.to_datetime(logs_df["timestamp"])
    logs_df = logs_df.sort_values(by="timestamp", ascending=False)

    st.subheader("Filtra Cronologia")
    all_users = sorted(logs_df["username"].unique().tolist())
    selected_users = st.multiselect("Filtra per Utente:", options=all_users, default=[])
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data Inizio", value=None)
    with col2:
        end_date = st.date_input("Data Fine", value=None)

    filtered_df = logs_df.copy()
    if selected_users:
        filtered_df = filtered_df[filtered_df["username"].isin(selected_users)]
    if start_date:
        filtered_df = filtered_df[filtered_df["timestamp"].dt.date >= start_date]
    if end_date:
        filtered_df = filtered_df[filtered_df["timestamp"].dt.date <= end_date]

    st.divider()
    st.subheader("Risultati")
    if filtered_df.empty:
        st.info("Nessun record trovato per i filtri selezionati.")
    else:
        display_df = filtered_df.copy()
        display_df["timestamp"] = display_df["timestamp"].dt.strftime(
            "%d/%m/%Y %H:%M:%S"
        )
        display_df.rename(
            columns={
                "timestamp": "Data e Ora",
                "username": "Nome Utente/Matricola",
                "status": "Esito",
            },
            inplace=True,
        )
        st.dataframe(
            display_df[["Data e Ora", "Nome Utente/Matricola", "Esito"]],
            width="stretch",
        )
