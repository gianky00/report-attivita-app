import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from config import (
    IS_DOCKER,
    PATH_ATTIVITA_PROGRAMMATE,
    PATH_GIORNALIERA_BASE,
    PATH_STORICO_DB,
    check_data_connectivity,
)


def render_system_status_tab() -> None:
    """Renderizza la tab di diagnostica dello stato del sistema."""
    st.subheader("Diagnostica e Stato Sistema")

    from modules.utils import render_svg_icon

    st.markdown(
        f"**Ambiente:** {render_svg_icon('system', 20)} {'Docker' if IS_DOCKER else 'Locale Windows'}"
    )
    st.markdown(f"**OS:** `{sys.platform}`")

    st.divider()

    st.subheader("Verifica Percorsi Dati")
    status = check_data_connectivity()

    for name, available in status.items():
        col1, col2 = st.columns([3, 1])
        path_val = ""
        if name == "Database Tecnico (Excel)":
            path_val = PATH_GIORNALIERA_BASE
        elif name == "Storico DB":
            path_val = PATH_STORICO_DB
        elif name == "Attività Programmate":
            path_val = PATH_ATTIVITA_PROGRAMMATE

        with col1:
            st.markdown(f"**{name}**")
            st.code(path_val)
        with col2:
            if available:
                st.success("Accessibile")
            else:
                st.error("Non Trovato")

    st.divider()

    st.subheader("Esplora Directory (Debug)")
    target_dir = st.selectbox(
        "Seleziona directory da esplorare:",
        [".", "src", "knowledge_base_docs", "reports", "nginx", "mnt", "/mnt/network"],
    )

    if st.button("Elenca File"):
        p = Path(target_dir)
        if p.exists():
            files = [
                {
                    "Nome": item.name,
                    "Tipo": f"{render_svg_icon('archive', 20)} Dir"
                    if item.is_dir()
                    else f"{render_svg_icon('info', 20)} File",
                    "Dimensione (KB)": round(item.stat().st_size / 1024, 2)
                    if item.is_file()
                    else "-",
                }
                for item in p.iterdir()
            ]
            st.table(pd.DataFrame(files))
        else:
            st.error(f"Il percorso `{target_dir}` non esiste nel container.")

    if IS_DOCKER:
        st.info(
            f"{render_svg_icon('info', 20)} **Suggerimento per Docker:** Se i percorsi di rete non sono accessibili, assicurati di aver montato il volume nel file `docker-compose.yml`."
        )
        st.code(
            """
# Esempio di mount nel docker-compose.yml
volumes:
  - \\\\192.168.11.251\\Database_Tecnico_SMI:/mnt/network:ro
        """
        )
