"""
Vista tabellare per l'elenco dei turni di assistenza e straordinario.
Permette il filtraggio, la ricerca e le operazioni di prenotazione/scambio.
"""
import pandas as pd
import streamlit as st

from modules.shift_management import (
    cancella_prenotazione_logic,
    prenota_turno_logic,
    pubblica_turno_in_bacheca_logic,
    richiedi_sostituzione_logic,
)


def render_turni_list(df_turni: pd.DataFrame, df_bookings: pd.DataFrame, df_users: pd.DataFrame, matricola_utente: str, ruolo: str, key_suffix: str):
    """Visualizza l'elenco dei turni disponibili con filtri di ricerca."""
    if df_turni.empty:
        st.info("Nessun turno di questo tipo disponibile al momento.")
        return

    mostra_solo_disponibili = st.checkbox("Solo posti disponibili", key=f"filter_{key_suffix}")
    m_to_n = pd.Series(df_users["Nome Cognome"].values, index=df_users["Matricola"].astype(str)).to_dict()

    if ruolo == "Amministratore":
        search = st.text_input("Cerca descrizione...", key=f"search_{key_suffix}")
        if search:
            df_turni = df_turni[df_turni["Descrizione"].str.contains(search, case=False, na=False)]

    st.divider()
    for _, turno in df_turni.iterrows():
        _render_turno_card(turno, df_bookings, m_to_n, matricola_utente, key_suffix, mostra_solo_disponibili, df_users)


def _render_turno_card(turno: pd.Series, df_bookings: pd.DataFrame, m_to_n: dict, matricola_utente: str, key_suffix: str, filter_active: bool, df_users: pd.DataFrame):
    """Sotto-funzione per il rendering della card del singolo turno."""
    p_turno = df_bookings[df_bookings["ID_Turno"] == turno["ID_Turno"]]
    posti_t, posti_a = int(turno["PostiTecnico"]), int(turno["PostiAiutante"])
    booked_t = len(p_turno[p_turno["RuoloOccupato"] == "Tecnico"])
    booked_a = len(p_turno[p_turno["RuoloOccupato"] == "Aiutante"])

    if filter_active and (booked_t >= posti_t and booked_a >= posti_a):
        return

    with st.container(border=True):
        st.markdown(f"**{turno['Descrizione']}**")
        dt = pd.to_datetime(turno["Data"]).strftime("%d/%m/%Y")
        st.caption(f"{dt} | {turno['OrarioInizio']} - {turno['OrarioFine']}")
        
        st.markdown(f"`Tecnici: {booked_t}/{posti_t}` | `Aiutanti: {booked_a}/{posti_a}`")
        
        if not p_turno.empty:
            names = [f"{m_to_n.get(str(p['Matricola']), 'N/D')} ({p['RuoloOccupato']})" for _, p in p_turno.iterrows()]
            st.markdown(f"**Prenotati:** {', '.join(names)}")

        _render_turno_actions(turno, p_turno, matricola_utente, key_suffix, booked_t, posti_t, booked_a, posti_a, df_users, m_to_n)


def _render_turno_actions(turno: pd.Series, p_turno: pd.DataFrame, matricola_utente: str, key_suffix: str, b_t: int, p_t: int, b_a: int, p_a: int, df_users: pd.DataFrame, m_to_n: dict):
    """Gestisce i pulsanti di azione (Prenota, Cancella, Scambio) per un turno."""
    p_utente = p_turno[p_turno["Matricola"] == str(matricola_utente)]
    t_id = turno["ID_Turno"]

    if not p_utente.empty:
        st.success("Sei prenotato.")
        c1, c2, c3 = st.columns(3)
        if c1.button("Cancella", key=f"del_{t_id}_{key_suffix}"):
            if cancella_prenotazione_logic(matricola_utente, t_id): st.rerun()
        if c2.button("📢 Bacheca", key=f"pub_{t_id}_{key_suffix}"):
            if pubblica_turno_in_bacheca_logic(matricola_utente, t_id): st.rerun()
        if c3.button("🔄 Scambio", key=f"ask_{t_id}_{key_suffix}"):
            st.session_state["sostituzione_turno_id"] = t_id
            st.rerun()
    else:
        opts = []
        if b_t < p_t: opts.append("Tecnico")
        if b_a < p_a: opts.append("Aiutante")
        if opts:
            role = st.selectbox("Ruolo:", opts, key=f"sel_{t_id}_{key_suffix}")
            if st.button("Prenota", key=f"add_{t_id}_{key_suffix}"):
                if prenota_turno_logic(matricola_utente, t_id, role): st.rerun()
        else:
            st.warning("Completo.")

    if st.session_state.get("sostituzione_turno_id") == t_id:
        _render_substitution_form(t_id, matricola_utente, df_users, m_to_n, key_suffix)


def _render_substitution_form(t_id: str, matricola_utente: str, df_users: pd.DataFrame, m_to_n: dict, key_suffix: str):
    """Visualizza il mini-form per la richiesta di sostituzione diretta."""
    st.markdown("---")
    riceventi = [str(m) for m in df_users["Matricola"] if str(m) != str(matricola_utente)]
    target = st.selectbox("Chiedi a:", riceventi, format_func=lambda m: m_to_n.get(m, m), key=f"sw_{t_id}_{key_suffix}")
    if st.button("Invia", key=f"conf_{t_id}_{key_suffix}"):
        if richiedi_sostituzione_logic(matricola_utente, target, t_id):
            del st.session_state["sostituzione_turno_id"]
            st.rerun()