"""
Vista di Audit per l'amministratore.
Permette di monitorare tutte le azioni eseguite dagli utenti nel sistema.
"""

import pandas as pd
import streamlit as st

from constants import ICONS
from modules.db_manager import get_all_exclusions, get_all_shift_logs


def render_audit_tab() -> None:
    """Renderizza la sezione di audit delle operazioni utente."""
    st.subheader("Audit Operazioni Utente")
    st.info(
        "In questa sezione puoi monitorare le attività critiche eseguite dai tecnici, "
        "come l'esclusione di report o le modifiche ai turni.",
        icon=ICONS["INFO"],
    )

    audit_tabs = st.tabs(
        [f"{ICONS['MATERIAL']} Esclusioni Report", f"{ICONS['TURNI']} Modifiche Turni"]
    )

    with audit_tabs[0]:
        st.markdown("#### Storico Esclusioni")
        exclusions_df = get_all_exclusions()

        if exclusions_df.empty:
            st.info("Nessuna esclusione registrata.")
        else:
            # Pulizia e formattazione
            df = exclusions_df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%d/%m/%Y %H:%M")

            st.dataframe(
                df,
                column_config={
                    "id_attivita": st.column_config.Column(
                        "Attività (PdL-Descrizione)", width="large"
                    ),
                    "tecnico": st.column_config.Column("Tecnico", width="medium"),
                    "timestamp": st.column_config.Column("Data Azione", width="small"),
                    "matricola_tecnico": None,  # Nascondi la matricola grezza
                },
                use_container_width=True,
                hide_index=True,
            )

    with audit_tabs[1]:
        st.markdown("#### Log Modifiche Turni")
        shift_logs_df = get_all_shift_logs()

        if shift_logs_df.empty:
            st.info("Nessun log di modifica turni trovato.")
        else:
            df_s = shift_logs_df.copy()
            df_s["Timestamp"] = pd.to_datetime(df_s["Timestamp"]).dt.strftime("%d/%m/%Y %H:%M")

            st.dataframe(
                df_s,
                column_config={
                    "ID_Modifica": None,
                    "Timestamp": st.column_config.Column("Ora", width="small"),
                    "ID_Turno": st.column_config.Column("Turno", width="small"),
                    "Azione": st.column_config.Column("Azione", width="medium"),
                    "UtenteOriginale": st.column_config.Column("Utente Orig.", width="small"),
                    "UtenteSubentrante": st.column_config.Column("Utente Sub.", width="small"),
                    "EseguitoDa": st.column_config.Column("Operatore", width="small"),
                },
                use_container_width=True,
                hide_index=True,
            )
