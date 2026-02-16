"""
Componenti UI per la navigazione (sidebar e bottoni).
"""

import datetime

import pandas as pd
import streamlit as st

from components.ui.notifications_ui import render_notification_center
from constants import ICONS
from modules.db_manager import get_last_login
from modules.importers.excel_giornaliera import _carica_giornaliera_mese
from modules.notifications import leggi_notifiche
from modules.oncall_logic import get_next_on_call_week
from modules.session_manager import delete_session


def render_sidebar(matricola_utente: str, nome_utente_autenticato: str, ruolo: str) -> None:
    """Gestisce la navigazione laterale e le informazioni utente."""
    with st.sidebar:
        # Logo in Sidebar
        st.image("assets/logo.svg", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(f"<h2 style='font-size: 1.5rem; margin-bottom: 0;'>Benvenuto, <span style='color: #4364F7;'>{nome_utente_autenticato.split()[0]}</span></h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: #64748b; font-size: 0.9rem; margin-top: 0;'>{ruolo}</p>", unsafe_allow_html=True)

        notifications = leggi_notifiche(matricola_utente)
        render_notification_center(notifications, matricola_utente)
        
        st.divider()
        _render_nav_buttons()

        if ruolo == "Amministratore":
            _render_admin_menu()

        st.divider()
        if st.button("Guida", icon=ICONS["GUIDA"], use_container_width=True, key="nav_guida"):
            st.session_state.main_tab = "Guida"
            st.rerun()
        
        # Info Reperibilità (solo se disponibile)
        _render_oncall_info(nome_utente_autenticato)

        if st.button("Esci dal portale", icon=ICONS["LOGOUT"], use_container_width=True, key="nav_logout"):
            delete_session(st.session_state.get("session_token"))
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

        from constants import APP_VERSION
        st.markdown(f"<div style='text-align: center; color: #94a3b8; font-size: 0.7rem; margin-top: 1rem;'>HORIZON PLATFORM v{APP_VERSION}</div>", unsafe_allow_html=True)


def _render_oncall_info(name: str) -> None:
    """Visualizza i dati sulla reperibilità in sidebar con layout ottimizzato."""
    surname = name.split()[-1]
    if start := get_next_on_call_week(surname):
        end = start + datetime.timedelta(days=6)
        today = datetime.date.today()
        is_now = start <= today <= end

        label = "SEI REPERIBILE" if is_now else "PROSSIMA REPERIBILITÀ"
        color = "#059669" if is_now else "#4364F7"
        bg_color = "#ecfdf5" if is_now else "#eff6ff"
        dates = f"{start.strftime('%d/%m')} — {end.strftime('%d/%m/%Y')}"

        st.markdown(f"""
            <div style='background-color: {bg_color}; padding: 12px; border-radius: 10px; border-left: 4px solid {color}; margin: 10px 0;'>
                <div style='color: {color}; font-weight: 700; font-size: 0.65rem; letter-spacing: 0.5px;'>{label}</div>
                <div style='color: #1e293b; font-size: 0.85rem; white-space: nowrap; margin-top: 4px;'>{dates}</div>
            </div>
        """, unsafe_allow_html=True)


def _render_nav_buttons() -> None:
    """Pulsanti di navigazione standard."""
    if st.button("Attività Assegnate", icon=ICONS["ATTIVITA"], use_container_width=True, key="nav_tasks"):
        st.session_state.main_tab = "Attività Assegnate"
        _carica_giornaliera_mese.clear()
        st.rerun()
    if st.button("Storico", icon=ICONS["STORICO"], use_container_width=True, key="nav_history"):
        st.session_state.main_tab = "Storico"
        st.rerun()
    if st.button("Archivio Tecnico", icon=ICONS["ARCHIVIO"], use_container_width=True, key="nav_archive"):
        st.session_state.main_tab = "Archivio Tecnico"
        st.rerun()
    st.divider()
    if st.button("Gestione Turni", icon=ICONS["TURNI"], use_container_width=True, key="nav_shifts"):
        st.session_state.main_tab = "Gestione Turni"
        st.rerun()
    if st.button("Richieste", icon=ICONS["RICHIESTE"], use_container_width=True, key="nav_requests"):
        st.session_state.main_tab = "Richieste"
        st.rerun()

    _render_settings_menu()

def _render_settings_menu() -> None:
    """Menu a fisarmonica per le impostazioni utente."""
    is_expanded = st.session_state.get("expanded_menu") == "Impostazioni"
    if st.button("Impostazioni", icon=ICONS["ADMIN"], use_container_width=True, key="nav_settings_toggle"):
        st.session_state.expanded_menu = "Impostazioni" if not is_expanded else ""
        st.rerun()

    if is_expanded and st.button("Generali", icon=ICONS["SECURITY"], use_container_width=True, key="nav_settings_gen"):
        # Selezionando 'Impostazioni' carichiamo la pagina principale che ha i tab
        st.session_state.main_tab = "Impostazioni"
        st.rerun()


def _render_admin_menu() -> None:
    """Menu a fisarmonica per gli amministratori."""
    is_expanded = st.session_state.get("expanded_menu") == "Amministrazione"
    if st.button("Amministrazione", icon=ICONS["ADMIN"], use_container_width=True, key="nav_admin_toggle"):
        st.session_state.expanded_menu = "Amministrazione" if not is_expanded else ""
        st.rerun()

    if is_expanded:
        for item in ("Caposquadra", "Sistema"):
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.main_tab = item
                st.rerun()
