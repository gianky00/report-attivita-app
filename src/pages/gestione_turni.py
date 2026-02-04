"""
Punto di ingresso principale per la gestione turni.
Funge da router per le diverse visualizzazioni dei turni.
"""

import pandas as pd
import streamlit as st

from modules.db_manager import (
    get_all_bacheca_items,
    get_all_bookings,
    get_all_substitutions,
    get_all_users,
    get_shifts_by_type,
)
from pages.shifts.market_view import render_bacheca_tab, render_sostituzioni_tab
from pages.shifts.oncall_calendar_view import render_reperibilita_tab
from pages.shifts.shifts_list_view import render_turni_list


def render_gestione_turni_tab(matricola_utente, ruolo):
    """Router per la gestione dei turni."""
    st.subheader("Gestione Turni")

    df_p = get_all_bookings()
    df_u = get_all_users()
    df_b = get_all_bacheca_items()
    df_s = get_all_substitutions()
    m_to_n = pd.Series(
        df_u["Nome Cognome"].values, index=df_u["Matricola"].astype(str)
    ).to_dict()

    t1, t2, t3 = st.tabs(["📅 Turni", "📢 Bacheca", "🔄 Sostituzioni"])

    with t1:
        st1, st2, st3 = st.tabs(["Assistenza", "Straordinario", "Reperibilità"])
        with st1:
            render_turni_list(
                get_shifts_by_type("Assistenza"),
                df_p,
                df_u,
                matricola_utente,
                ruolo,
                "assistenza",
            )
        with st2:
            render_turni_list(
                get_shifts_by_type("Straordinario"),
                df_p,
                df_u,
                matricola_utente,
                ruolo,
                "straordinario",
            )
        with st3:
            render_reperibilita_tab(df_p, df_u, matricola_utente, ruolo)

    with t2:
        render_bacheca_tab(df_b, df_u, matricola_utente, ruolo, m_to_n)
    with t3:
        render_sostituzioni_tab(df_s, m_to_n, matricola_utente)
