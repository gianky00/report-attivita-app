"""
Vista Amministrativa e Caposquadra.
Funge da router per le diverse funzionalità gestionali.
"""

import streamlit as st


def render_caposquadra_view(matricola_utente: str) -> None:
    """Renderizza la vista per il Caposquadra."""
    from .shifts_view import render_new_shift_form
    from .validation_view import (
        render_relazioni_validation_tab,
        render_report_validation_tab,
    )

    st.markdown('<div class="card">', unsafe_allow_html=True)
    caposquadra_tabs = st.tabs(["Crea Nuovo Turno", "Validazione Report"])

    with caposquadra_tabs[0]:
        render_new_shift_form()

    with caposquadra_tabs[1]:
        validation_tabs = st.tabs(["Validazione Report Attività", "Validazione Relazioni"])
        with validation_tabs[0]:
            render_report_validation_tab(matricola_utente)
        with validation_tabs[1]:
            render_relazioni_validation_tab(matricola_utente)
    st.markdown("</div>", unsafe_allow_html=True)


def render_sistema_view() -> None:
    """Renderizza la vista 'Sistema' suddivisa in tab operative."""
    from pages.gestione_dati import render_gestione_dati_tab

    from .audit_view import render_audit_tab
    from .ia_view import render_ia_management_tab
    from .logs_view import render_access_logs_tab
    from .system_status_view import render_system_status_tab
    from .users_view import render_gestione_account

    st.markdown('<div class="card">', unsafe_allow_html=True)
    tabs = st.tabs(
        [
            "Gestione Account",
            "Audit Operazioni",
            "Cronologia Accessi",
            "Gestione Dati",
            "Gestione IA",
            "Stato Sistema",
        ]
    )

    with tabs[0]:
        render_gestione_account()
    with tabs[1]:
        render_audit_tab()
    with tabs[2]:
        render_access_logs_tab()
    with tabs[3]:
        render_gestione_dati_tab()
    with tabs[4]:
        render_ia_management_tab()
    with tabs[5]:
        render_system_status_tab()
    st.markdown("</div>", unsafe_allow_html=True)


__all__ = ["render_caposquadra_view", "render_sistema_view"]
