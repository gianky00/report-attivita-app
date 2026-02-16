"""
Pagina per la consultazione dell'archivio storico delle schede di manutenzione.
Versione ottimizzata per mobile con design Horizon.
"""

import streamlit as st
import os
import datetime
from modules.archive_manager import search_archive, get_archive_stats
from constants import ICONS

def render_archivio_page():
    # Stile CSS aggiuntivo per rendere i risultati più compatti e professionali
    st.markdown("""
        <style>
        .archive-card {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
            margin-bottom: 10px;
        }
        .file-info {
            font-size: 0.85rem;
            color: #64748b;
            margin-top: 5px;
        }
        .tag-highlight {
            color: #4364f7;
            font-weight: 600;
        }
        </style>
    """, unsafe_allow_html=True)

    st.subheader("Archivio Storico Schede")
    
    # Statistiche in alto con design Horizon (più compatto)
    stats = get_archive_stats()
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f"<div style='text-align: center;'><small>TOTALE</small><br><b style='font-size: 1.1rem;'>{stats['total_files']:,}</b></div>", unsafe_allow_html=True)
    with s2:
        st.markdown(f"<div style='text-align: center;'><small>ANNI</small><br><b style='font-size: 1.1rem;'>{stats['year_range']}</b></div>", unsafe_allow_html=True)
    with s3:
        st.markdown(f"<div style='text-align: center;'><small>STATO</small><br><b style='font-size: 1.1rem; color: #059669;'>● ONLINE</b></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Ricerca con icona integrata
    search_query = st.text_input(
        "🔍 Cerca per Tag o nome file", 
        placeholder="Es: PT-101, 01F015...",
        help="Inserisci almeno 2 caratteri per iniziare la ricerca",
        key="archive_search_input"
    )

    if len(search_query) >= 2:
        results = search_archive(search_query)
        
        if not results.empty:
            st.markdown(f"<p style='color: #64748b; font-size: 0.9rem;'>Trovate {len(results)} corrispondenze</p>", unsafe_allow_html=True)
            
            for _, row in results.iterrows():
                # Formattazione data GG/MM/AAAA
                try:
                    raw_date = row['last_modified'].split('T')[0]
                    dt = datetime.datetime.strptime(raw_date, '%Y-%m-%d')
                    display_date = dt.strftime('%d/%m/%Y')
                except Exception:
                    display_date = row['last_modified']

                # Estrazione Tag
                fname = row['filename']
                tag_part = fname.split(' ')[0].split('(')[0].replace('.xls', '').replace('.xlsm', '')

                with st.expander(f"📄 {fname}"):
                    # Layout pulito
                    st.markdown(f"""
                        <div style='margin-bottom: 10px;'>
                            <div style='font-size: 0.9rem;'><b>Tag:</b> <span class='tag-highlight'>{tag_part}</span></div>
                            <div style='font-size: 0.85rem; color: #64748b;'><b>Periodo:</b> {row['month']} {row['year']}</div>
                            <div style='font-size: 0.85rem; color: #64748b;'><b>Ultima Modifica:</b> {display_date}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Gestione Path per Docker
                    file_path = row['full_path']
                    if os.environ.get("IS_DOCKER") == "true":
                        windows_prefix = r"D:\PC ALLEGRETTI COEMI\STORICO SCHEDE\Archivio Schede Elaborate"
                        docker_prefix = "/mnt/archivio_storico"
                        if windows_prefix in file_path:
                            file_path = file_path.replace(windows_prefix, docker_prefix).replace("\\", "/")
                    
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label="📥 Apri Scheda Excel",
                                data=f,
                                file_name=fname,
                                mime="application/vnd.ms-excel",
                                key=f"dl_{fname}_{row['year']}_{display_date}",
                                use_container_width=True
                            )
                    else:
                        st.error(f"⚠️ File momentaneamente non accessibile sul server.")
                        if st.checkbox("Mostra dettagli errore", key=f"err_{fname}"):
                            st.code(f"Path: {file_path}")
        else:
            st.warning("Nessun file trovato. Prova con un altro tag.")
    elif search_query:
        st.info("Digita almeno 2 caratteri.")
    else:
        st.markdown("""
            <div style='background-color: #f8fafc; padding: 20px; border-radius: 10px; text-align: center; border: 1px dashed #cbd5e1;'>
                <p style='color: #64748b; margin: 0;'>Digita il tag di uno strumento per visualizzare lo storico dei suoi interventi.</p>
            </div>
        """, unsafe_allow_html=True)
