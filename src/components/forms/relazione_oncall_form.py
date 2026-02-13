"""
Form per la compilazione delle relazioni di reperibilità.
"""

import datetime
from typing import Any

import streamlit as st

from constants import ICONS
from learning_module import get_report_knowledge_base_count
from modules.ai_engine import revisiona_con_ia
from modules.db_manager import (
    get_all_users,
    salva_relazione,
)
from modules.email_sender import invia_email_con_outlook_async
from modules.instrumentation_logic import get_technical_suggestions


def render_relazione_reperibilita_ui(matricola_utente: str, nome_utente_autenticato: str) -> None:
    """Renderizza l'interfaccia per la compilazione della relazione di reperibilità settimanale."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Compila Relazione di Reperibilità")

    kb_count = get_report_knowledge_base_count()
    if kb_count > 0:
        st.caption(f":material/info: KB IA: {kb_count} relazioni.")
    else:
        st.caption(":material/info: KB IA vuota.")

    if "relazione_testo" not in st.session_state:
        st.session_state.relazione_testo = ""

    users = get_all_users()
    partners = users[users["Matricola"] != matricola_utente]["Nome Cognome"].tolist()

    with st.form("form_relazione"):
        c1, c2 = st.columns(2)
        c1.text_input("Tecnico", value=nome_utente_autenticato, disabled=True)
        partner = c2.selectbox("Partner", ["Nessuno", *sorted(partners)])

        c3, c4, c5 = st.columns(3)
        dt = c3.date_input("Data*")
        t_start = c4.text_input("Ora Inizio")
        t_end = c5.text_input("Ora Fine")

        text = st.text_area("Testo", height=250, value=st.session_state.relazione_testo)

        b1, b2, b3 = st.columns(3)
        do_ai = b1.form_submit_button("IA", icon=ICONS["IA"])
        do_sugg = b2.form_submit_button("Suggerimenti", icon=ICONS["LIGHTBULB"])
        do_save = b3.form_submit_button("Invia", type="primary", icon=ICONS["CHECK"])

    if do_ai:
        _handle_ai_correction(text)
    if do_sugg:
        _handle_suggestions(text)
    if do_save:
        _handle_submission(dt, text, nome_utente_autenticato, partner, t_start, t_end)

    _render_ai_results_ui()
    st.markdown("</div>", unsafe_allow_html=True)


def _handle_ai_correction(text: str) -> None:
    """Richiede la correzione semantica del testo all'IA Gemini."""
    if not text.strip():
        st.warning("Scrivi il testo.")
        return
    with st.spinner("L'IA sta analizzando..."):
        res = revisiona_con_ia(text)
        if res.get("success"):
            st.session_state.relazione_revisionata = res["text"]
            st.success("Fatto!")
        else:
            st.error(res.get("error", "Errore IA."))


def _handle_suggestions(text: str) -> None:
    """Rileva suggerimenti tecnici basati sulla strumentazione menzionata nel testo."""
    if not text.strip():
        st.warning("Scrivi qualcosa.")
        return
    suggs = get_technical_suggestions(text)
    st.session_state.technical_suggestions = suggs
    if not suggs:
        st.toast("Nessun suggerimento.")


def _handle_submission(
    dt: Any, text: str, user: str, partner: str, t_start: str, t_end: str
) -> None:
    """Invia la relazione definitiva, salvandola nel DB e inviando l'email."""
    if not dt or not text.strip():
        st.error("Dati mancanti.")
        return

    pid = f"REL_{int(datetime.datetime.now().timestamp())}"
    data = {
        "id_relazione": pid,
        "data_intervento": dt.isoformat(),
        "tecnico_compilatore": user,
        "partner": partner if partner != "Nessuno" else None,
        "ora_inizio": t_start,
        "ora_fine": t_end,
        "corpo_relazione": text,
        "stato": "Inviata",
        "timestamp_invio": datetime.datetime.now().isoformat(),
    }

    if salva_relazione(data):
        st.success("Inviata!")
        _send_relazione_email(dt, user, partner, text)
        st.session_state.relazione_testo = ""
        st.rerun()


def _send_relazione_email(dt: Any, user: str, partner: str, text: str) -> None:
    """Invia la notifica email automatica della nuova relazione via Outlook."""
    p_txt = f" con {partner}" if partner != "Nessuno" else ""
    d_str = dt.strftime("%d/%m/%Y")
    subj = f"Relazione Reperibilità {d_str} - {user}"
    body = f"<html><body><h3>Relazione</h3><p><b>Data:</b> {d_str}</p><p><b>Tecnico:</b> {user}{p_txt}</p><hr><p>{text.replace(chr(10), '<br>')}</p></body></html>"
    invia_email_con_outlook_async(subj, body)


def _render_ai_results_ui() -> None:
    """Visualizza i risultati opzionali (IA o suggerimenti) sotto il form principale."""
    if st.session_state.get("relazione_revisionata"):
        st.subheader("Testo IA")
        st.info(st.session_state.relazione_revisionata)
        if st.button("Usa questo testo"):
            st.session_state.relazione_testo = st.session_state.relazione_revisionata
            st.session_state.relazione_revisionata = ""
            st.rerun()

    if st.session_state.get("technical_suggestions"):
        st.subheader("💡 Suggerimenti")
        for s in st.session_state.technical_suggestions:
            st.info(s)
