"""
Componenti UI per la navigazione (sidebar e bottoni).
"""
import datetime
import pandas as pd
import streamlit as st
from modules.importers.excel_giornaliera import _carica_giornaliera_mese
from modules.db_manager import get_last_login
from modules.notifications import leggi_notifiche
from modules.oncall_logic import get_next_on_call_week
from modules.session_manager import delete_session
from components.ui.notifications_ui import render_notification_center

def render_sidebar(matricola_utente, nome_utente_autenticato, ruolo):
    """Gestisce la navigazione laterale e le informazioni utente."""
    with st.sidebar:
        st.header(f"Ciao, {nome_utente_autenticato}!")
        st.caption(f"Ruolo: {ruolo}")

        _render_oncall_info(nome_utente_autenticato)

        notifications = leggi_notifiche(matricola_utente)
        render_notification_center(notifications, matricola_utente)

        if last := get_last_login(matricola_utente):
            st.caption(f"Ultimo accesso: {pd.to_datetime(last).strftime('%d/%m/%Y %H:%M')}")

        st.divider()
        _render_nav_buttons()

        if ruolo == "Amministratore":
            _render_admin_menu()

        st.divider()
        if st.button("❓ Guida", use_container_width=True):
            st.session_state.main_tab = "❓ Guida"
            st.rerun()
        if st.button("Disconnetti", use_container_width=True):
            delete_session(st.session_state.get("session_token"))
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

def _render_oncall_info(name):
    """Visualizza i dati sulla reperibilità in sidebar."""
    surname = name.split()[-1]
    if start := get_next_on_call_week(surname):
        end = start + datetime.timedelta(days=6)
        today = datetime.date.today()
        is_now = start <= today <= end

        if is_now:
            st.markdown("**Sei reperibile**")
            msg = f"Dal: {start.strftime('%d/%m')} al {end.strftime('%d/%m/%Y')}"
        else:
            msg = f"Prossima Reperibilità:\n{start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')}"
        st.info(msg)

def _render_nav_buttons():
    """Pulsanti di navigazione standard."""
    if st.button("📝 Attività Assegnate", use_container_width=True):
        st.session_state.main_tab = "Attività Assegnate"
        _carica_giornaliera_mese.clear()
        st.rerun()
    if st.button("🗂️ Storico", use_container_width=True):
        st.session_state.main_tab = "Storico"
        st.rerun()
    st.divider()
    if st.button("📅 Gestione Turni", use_container_width=True):
        st.session_state.main_tab = "📅 Gestione Turni"
        st.rerun()
    if st.button("Richieste", use_container_width=True):
        st.session_state.main_tab = "Richieste"
        st.rerun()

def _render_admin_menu():
    """Menu a fisarmonica per gli amministratori."""
    is_expanded = st.session_state.get("expanded_menu") == "⚙️ Amministrazione"
    if st.button("⚙️ Amministrazione", use_container_width=True):
        st.session_state.expanded_menu = "⚙️ Amministrazione" if not is_expanded else ""
        st.rerun()

    if is_expanded:
        for item in ["Caposquadra", "Sistema"]:
            if st.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.main_tab = item
                st.rerun()
