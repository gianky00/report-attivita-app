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
    
    # Ricerca globale per la pagina
    search = st.text_input("Cerca (Team, PDL o Descrizione)", "")

    # Date calcolate
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)

    # Recupero dati
    df_oggi = get_pdl_programmazione(today.isoformat(), today.isoformat())
    df_settimana = get_pdl_programmazione(start_of_week.isoformat(), end_of_week.isoformat())

    # Formattazione per la visualizzazione
    def format_df(df):
        if df.empty:
            return df
            
        if search:
            df = df[
                df['pdl'].str.contains(search, case=False, na=False) | 
                df['team'].str.contains(search, case=False, na=False) |
                df['descrizione'].str.contains(search, case=False, na=False)
            ]
            
        if df.empty:
            return df
            
        display_df = df.copy()
        display_df.columns = [
            "PDL", "Data Intervento", "Tecnico", "Descrizione", "Team", "Stato", "Tipo",
            "Pianificato il", "Report Inviato", "Validato il"
        ]

        for col in ["Pianificato il", "Report Inviato", "Validato il"]:
            display_df[col] = pd.to_datetime(display_df[col], errors='coerce').dt.strftime('%d/%m/%Y - %H:%M')
            display_df[col] = display_df[col].fillna("-")
            
        return display_df

    # Funzione per applicare colori allo stato
    def color_status(val):
        color = 'black'
        if val == 'PIANIFICATO': color = '#6c757d' # Muted
        elif val == 'INVIATO': color = '#ffc107' # Warning
        elif val == 'VALIDATO': color = '#28a745' # Success
        return f'color: {color}; font-weight: bold'

    st.subheader("Oggi")
    df_oggi_fmt = format_df(df_oggi)
    if df_oggi_fmt.empty:
        st.info("Nessun PDL programmato per oggi.")
    else:
        st.dataframe(
            df_oggi_fmt.style.map(color_status, subset=['Stato']),
            use_container_width=True,
            hide_index=True,
            column_config={
                "PDL": st.column_config.TextColumn("PDL", width="small"),
                "Data Intervento": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Stato": st.column_config.TextColumn("Stato", width="small"),
            }
        )

    st.markdown("---")

    st.subheader("Questa Settimana")
    df_settimana_fmt = format_df(df_settimana)
    if df_settimana_fmt.empty:
        st.info("Nessun PDL programmato per questa settimana.")
    else:
        st.dataframe(
            df_settimana_fmt.style.map(color_status, subset=['Stato']),
            use_container_width=True,
            hide_index=True,
            column_config={
                "PDL": st.column_config.TextColumn("PDL", width="small"),
                "Data Intervento": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Stato": st.column_config.TextColumn("Stato", width="small"),
            }
        )
