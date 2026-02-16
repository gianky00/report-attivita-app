"""
Pagina per la consultazione dell'archivio storico delle schede di manutenzione.
"""

import streamlit as st
import os
from modules.archive_manager import search_archive, get_archive_stats
from constants import ICONS

def render_archivio_page():
    st.header("📂 Archivio Storico Schede")
    
    # Statistiche in alto
    stats = get_archive_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("Totale Schede", f"{stats['total_files']:,}")
    col2.metric("Periodo", stats['year_range'])
    col3.metric("Stato", "Disponibile")

    st.markdown("---")

    # Ricerca
    search_query = st.text_input("🔍 Cerca per Tag o nome file (es. PT-101 o 01F015)", placeholder="Inserisci almeno 3 caratteri...")

    if len(search_query) >= 3:
        results = search_archive(search_query)
        
        if not results.empty:
            st.success(f"Trovate {len(results)} corrispondenze (mostrate le prime 50)")
            
            # Tabella dei risultati
            for _, row in results.iterrows():
                with st.expander(f"📄 {row['filename']}"):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Percorso:** `{row['full_path']}`")
                        st.markdown(f"**Periodo:** {row['month']} {row['year']}")
                        st.markdown(f"**Ultima Modifica:** {row['last_modified']}")
                    
                    with c2:
                        # Bottone per scaricare il file
                        if os.path.exists(row['full_path']):
                            with open(row['full_path'], "rb") as f:
                                st.download_button(
                                    label="📥 Scarica Excel",
                                    data=f,
                                    file_name=row['filename'],
                                    mime="application/vnd.ms-excel",
                                    key=f"dl_{row['filename']}"
                                )
                        else:
                            st.error("File non trovato sul disco.")
        else:
            st.warning("Nessun file trovato con questo nome.")
    elif search_query:
        st.info("Inserisci almeno 3 caratteri per iniziare la ricerca.")
    else:
        st.info("Digita il tag di uno strumento o parte del nome del file per visualizzare lo storico.")
