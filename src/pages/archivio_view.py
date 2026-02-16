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
    search_query = st.text_input("🔍 Cerca per Tag o nome file (es. PT-101 o 01F015)", placeholder="Inserisci almeno 2 caratteri...")

    if len(search_query) >= 2:
        results = search_archive(search_query)
        
        if not results.empty:
            st.success(f"Trovate {len(results)} corrispondenze (mostrate le prime 50)")
            
            # Tabella dei risultati
            for _, row in results.iterrows():
                # Formattazione data più leggibile
                try:
                    display_date = row['last_modified'].split('T')[0]
                except:
                    display_date = row['last_modified']

                with st.expander(f"📄 {row['filename']} ({row['month']} {row['year']})"):
                    # Verifica esistenza file fisica
                    file_path = row['full_path']
                    # Patch per Docker: se il percorso inizia con D:\ ma siamo in Linux, non lo troverà mai.
                    # Ma qui l'utente è su Win32 e l'app gira su Win32 (ngrok punta al locale).
                    
                    st.markdown(f"**Percorso completo:** `{file_path}`")
                    st.markdown(f"**Ultima Modifica:** {display_date}")
                    
                    # Debug info se il file non viene trovato
                    file_exists = os.path.exists(file_path)
                    
                    if file_exists:
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label="📥 Scarica Excel",
                                data=f,
                                file_name=row['filename'],
                                mime="application/vnd.ms-excel",
                                key=f"dl_{row['filename']}_{row['year']}"
                            )
                    else:
                        st.error(f"⚠️ File non accessibile. Verifica che il disco D: sia collegato e che il percorso sia corretto.")
                        st.info(f"Tentativo di accesso a: {file_path}")
        else:
            st.warning("Nessun file trovato con questo nome.")
    elif search_query:
        st.info("Inserisci almeno 2 caratteri per iniziare la ricerca.")
    else:
        st.info("Digita il tag di uno strumento o parte del nome del file per visualizzare lo storico.")
