import streamlit as st
import pandas as pd
import datetime
import re
import os
import json
from collections import defaultdict

# Importa solo le funzioni necessarie per ridurre la complessità
from modules.data_manager import carica_dati_attivita_programmate
from modules.db_manager import get_filtered_archived_activities, get_archive_filter_options

# --- Funzioni di Rendering dell'Interfaccia Utente ---

def visualizza_storico_organizzato(storico_list, pdl):
    """Mostra lo storico di un'attività in modo organizzato."""
    if storico_list:
        with st.expander(f"Mostra cronologia interventi per PdL {pdl}", expanded=False):
            # Ordina gli interventi per data, dal più recente al più vecchio
            storico_list.sort(key=lambda x: x.get('Data_Riferimento_dt', ''), reverse=True)
            for intervento in storico_list:
                data_riferimento = pd.to_datetime(intervento.get('Data_Riferimento_dt')).strftime('%d/%m/%Y') if pd.notna(intervento.get('Data_Riferimento_dt')) else 'Data non disponibile'
                st.markdown(f"**Data:** {data_riferimento} - **Tecnico:** {intervento.get('Tecnico', 'N/D')}")
                st.info(f"**Report:** {intervento.get('Report', 'Nessun report.')}")
                st.markdown("---")
    else:
        st.markdown("*Nessuno storico disponibile per questo PdL.*")

def render_database_tab():
    """Renderizza la tab 'Database' (Archivio Storico)."""
    st.header("Archivio Storico")
    st.subheader("Ricerca nel Database Attività")
    
    filter_options = get_archive_filter_options()

    c1, c2, c3, c4 = st.columns(4)
    with c1: pdl_search = st.text_input("Filtra per PdL", key="db_pdl_search")
    with c2: desc_search = st.text_input("Filtra per Descrizione", key="db_desc_search")
    with c3: imp_search = st.multiselect("Filtra per Impianto", options=filter_options.get('impianti', []), key="db_imp_search")
    with c4: tec_search = st.multiselect("Filtra per Tecnico/i", options=filter_options.get('tecnici', []), key="db_tec_search")

    st.divider()
    
    st.info("La ricerca mostra tutte le attività che hanno almeno un intervento registrato, ordinate per data dell'intervento più recente.")

    with st.spinner("Ricerca in corso nel database..."):
        risultati_df = get_filtered_archived_activities(pdl_search, desc_search, imp_search, tec_search)

    if risultati_df.empty:
        st.warning("Nessun record trovato.")
    else:
        st.success(f"Trovati {len(risultati_df)} record.")
        for _, row in risultati_df.iterrows():
            with st.container(border=True):
                st.markdown(f"**PdL `{row['PdL']}`** | {row.get('IMP', 'N/D')} | {row.get('DESCRIZIONE_ATTIVITA', 'N/D')}")
                visualizza_storico_organizzato(row['Storico'], row['PdL'])

def main():
    """Funzione principale dell'applicazione Streamlit."""
    st.set_page_config(layout="wide", page_title="Gestionale")
    
    # Simuliamo un utente loggato per il test
    st.title("Gestionale")
    st.header("Ciao, Utente Test!")
    st.caption("Ruolo: Amministratore")

    # Navigazione semplificata per il test
    render_database_tab()

if __name__ == "__main__":
    main()