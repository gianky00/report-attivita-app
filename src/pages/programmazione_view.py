"""
Pagina di visualizzazione della programmazione dei PDL per tutto il team.
"""

import datetime

import pandas as pd
import streamlit as st

from modules.db_manager import get_pdl_programmazione


def render_programmazione_pdl_page() -> None:
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
    def format_df(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        if search:
            df = df[
                df["pdl"].str.contains(search, case=False, na=False)
                | df["team"].str.contains(search, case=False, na=False)
                | df["descrizione"].str.contains(search, case=False, na=False)
            ]

        if df.empty:
            return df

        display_df = df.copy()
        display_df.columns = [
            "PDL",
            "Data Intervento",
            "Tecnico",
            "Descrizione",
            "Team",
            "Stato",
            "Tipo",
            "Pianificato il",
            "Report Inviato",
            "Validato il",
        ]

        for col in ["Pianificato il", "Report Inviato", "Validato il"]:
            display_df[col] = pd.to_datetime(display_df[col], errors="coerce").dt.strftime(
                "%d/%m/%Y - %H:%M"
            )
            display_df[col] = display_df[col].fillna("-")

        return display_df

    # Funzione per applicare colori a tutta la riga in base allo stato
    def color_rows(row: pd.Series) -> list[str]:
        val = row["Stato"]
        color = "black"
        bg_color = "transparent"
        if val == "PIANIFICATO":
            color = "#6c757d"
        elif val == "INVIATO":
            color = "#856404"  # Darker yellow for text
            bg_color = "rgba(255, 193, 7, 0.2)"
        elif val == "VALIDATO":
            color = "#155724"  # Darker green for text
            bg_color = "rgba(40, 167, 69, 0.2)"
        elif val == "NON SVOLTA":
            color = "#721c24"  # Darker red for text
            bg_color = "rgba(220, 53, 69, 0.2)"
        elif val == "SOSPESA":
            color = "#383d41"
            bg_color = "rgba(111, 66, 193, 0.2)"

        style = f"color: {color}; background-color: {bg_color}; font-weight: bold"
        return [style] * len(row)

    df_oggi_fmt = format_df(df_oggi)
    count_oggi = df_oggi_fmt["PDL"].nunique() if not df_oggi_fmt.empty else 0
    st.subheader(f"Oggi ({count_oggi})")

    if df_oggi_fmt.empty:
        st.info("Nessun PDL programmato per oggi.")
    else:
        st.dataframe(
            df_oggi_fmt.style.apply(color_rows, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "PDL": st.column_config.TextColumn("PDL", width="small"),
                "Data Intervento": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Stato": st.column_config.TextColumn("Stato", width="small"),
            },
        )

    st.markdown("---")

    df_settimana_fmt = format_df(df_settimana)
    count_settimana = df_settimana_fmt["PDL"].nunique() if not df_settimana_fmt.empty else 0
    st.subheader(f"Questa Settimana ({count_settimana})")

    if df_settimana_fmt.empty:
        st.info("Nessun PDL programmato per questa settimana.")
    else:
        st.dataframe(
            df_settimana_fmt.style.apply(color_rows, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "PDL": st.column_config.TextColumn("PDL", width="small"),
                "Data Intervento": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Stato": st.column_config.TextColumn("Stato", width="small"),
            },
        )
