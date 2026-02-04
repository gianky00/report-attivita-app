"""
Vista Amministrativa e Caposquadra.
Funge da router per le diverse funzionalità gestionali.
"""

import streamlit as st

from src.pages.admin.ia_view import render_ia_management_tab
from src.pages.admin.logs_view import render_access_logs_tab
from src.pages.admin.shifts_view import render_new_shift_form
from src.pages.admin.users_view import render_gestione_account
from src.pages.admin.validation_view import (
    render_relazioni_validation_tab,
    render_report_validation_tab,
)
from src.pages.gestione_dati import render_gestione_dati_tab


def render_caposquadra_view(matricola_utente):
    """Renderizza la vista per il Caposquadra."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    caposquadra_tabs = st.tabs(["Crea Nuovo Turno", "Validazione Report"])

    with caposquadra_tabs[0]:
        render_new_shift_form()

    with caposquadra_tabs[1]:
        validation_tabs = st.tabs(
            ["Validazione Report Attività", "Validazione Relazioni"]
        )
        with validation_tabs[0]:
            render_report_validation_tab(matricola_utente)
        with validation_tabs[1]:
            render_relazioni_validation_tab(matricola_utente)
    st.markdown("</div>", unsafe_allow_html=True)


def render_sistema_view():
    """Renderizza la vista 'Sistema' suddivisa in tab operative."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tabs = st.tabs(
        ["Gestione Account", "Cronologia Accessi", "Gestione Dati", "Gestione IA"]
    )

    with tabs[0]:
        render_gestione_account()
    with tabs[1]:
        render_access_logs_tab()
    with tabs[2]:
        render_gestione_dati_tab()
    with tabs[3]:
        render_ia_management_tab()
    st.markdown("</div>", unsafe_allow_html=True)
