"""
Pagina di visualizzazione della programmazione dei PDL per tutto il team.
"""

import datetime
import pandas as pd
import streamlit as st
from modules.db_manager import get_pdl_programmazione
from constants import ICONS

def render_programmazione_pdl_page():
    """Renderizza la vista ordinata della programmazione PDL."""
    st.title(f"{ICONS['PROGRAMMAZIONE']} Programmazione PDL Team")
    st.info("In questa sezione puoi consultare tutti i PDL assegnati al team e il loro stato di avanzamento.", icon=ICONS["INFO"])

    # Filtri di ricerca
    c1, c2, c3 = st.columns([1, 1, 1])
    today = datetime.date.today()
    
    with c1:
        data_inizio = st.date_input("Dalla data", today - datetime.timedelta(days=7))
    with c2:
        data_fine = st.date_input("Alla data", today + datetime.timedelta(days=7))
    
    # Recupero dati
    df = get_pdl_programmazione(data_inizio.isoformat(), data_fine.isoformat())
    
    if df.empty:
        st.warning("Nessun PDL trovato per il periodo selezionato.")
        return

    with c3:
        search = st.text_input("Cerca (Tecnico o PDL)", "")

    if search:
        df = df[
            df['pdl'].str.contains(search, case=False, na=False) | 
            df['tecnico_assegnato'].str.contains(search, case=False, na=False)
        ]

    # Formattazione per la visualizzazione
    display_df = df.copy()
    
    # Rinominazione colonne per chiarezza UI
    display_df.columns = [
        "PDL", "Data Intervento", "Tecnico", "Descrizione", "Team", "Stato", "Tipo",
        "Pianificato il", "Report Inviato", "Validato il"
    ]

    # Funzione per applicare colori allo stato
    def color_status(val):
        color = 'black'
        if val == 'PIANIFICATO': color = '#6c757d' # Muted
        elif val == 'INVIATO': color = '#ffc107' # Warning
        elif val == 'VALIDATO': color = '#28a745' # Success
        return f'color: {color}; font-weight: bold'

    st.markdown("---")
    
    # Tabella interattiva
    st.dataframe(
        display_df.style.map(color_status, subset=['Stato']),
        use_container_width=True,
        hide_index=True,
        column_config={
            "PDL": st.column_config.TextColumn("PDL", width="small"),
            "Data Intervento": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Stato": st.column_config.TextColumn("Stato", width="small"),
        }
    )

    st.caption(f"Ultimo aggiornamento: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
