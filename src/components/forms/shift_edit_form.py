"""
Form per la modifica dei turni esistenti (riservato agli amministratori).
"""
import datetime
import pandas as pd
import streamlit as st
from modules.db_manager import (
    get_all_users,
    get_bookings_for_shift,
    get_shift_by_id,
    update_shift,
    delete_booking,
    add_booking,
)
from modules.notifications import crea_notifica
from modules.shift_management import log_shift_change

def render_edit_shift_form():
    """Renderizza il form per la modifica di un turno esistente (solo Admin)."""
    t_id = st.session_state.get("editing_turno_id")
    if not t_id:
        st.error("ID Turno mancante.")
        return

    info = get_shift_by_id(t_id)
    if not info:
        st.error("Turno non trovato.")
        return

    bookings = get_bookings_for_shift(t_id)
    current_roles = bookings.set_index("Matricola")["RuoloOccupato"].to_dict()
    users = get_all_users()
    u_dict = users.set_index("Matricola")["Nome Cognome"].to_dict()

    st.subheader(f"Modifica Turno: {info.get('Descrizione', 'N/A')}")

    with st.form("edit_shift_form"):
        desc = st.text_input("Descrizione", value=info.get("Descrizione", ""))
        tipo = st.selectbox("Tipo", ["Reperibilità", "Ferie"], index=0)

        dt_val = pd.to_datetime(info.get("Data", datetime.date.today()))
        start_val = pd.to_datetime(info.get("OraInizio", "00:00")).time()
        end_val = pd.to_datetime(info.get("OraFine", "00:00")).time()

        c1, c2, c3 = st.columns(3)
        d_inp = c1.date_input("Data", value=dt_val)
        s_inp = c2.time_input("Inizio", value=start_val)
        e_inp = c3.time_input("Fine", value=end_val)

        techs = st.multiselect(
            "Tecnici", u_dict.keys(), format_func=lambda x: u_dict[x],
            default=[m for m, r in current_roles.items() if r == "Tecnico"]
        )
        helpers = st.multiselect(
            "Aiutanti", u_dict.keys(), format_func=lambda x: u_dict[x],
            default=[m for m, r in current_roles.items() if r == "Aiutante"]
        )

        if st.form_submit_button("Salva"):
            upd = {
                "Descrizione": desc, "Tipo": tipo, "Data": d_inp.isoformat(),
                "OraInizio": s_inp.strftime("%H:%M"), "OraFine": e_inp.strftime("%H:%M")
            }
            if update_shift(t_id, upd):
                _handle_shift_update_participants(t_id, desc, current_roles, techs, helpers)
                st.success("Aggiornato!")
                del st.session_state["editing_turno_id"]
                st.rerun()
            else:
                st.error("Errore aggiornamento.")

def _handle_shift_update_participants(t_id, desc, old_roles, new_techs, new_helpers):
    """Gestisce la logica di aggiunta/rimozione partecipanti dopo l'aggiornamento di un turno."""
    old_set = set(old_roles.keys())
    new_set = set(new_techs + new_helpers)

    for m in old_set - new_set:
        if delete_booking(m, t_id):
            crea_notifica(m, f"Rimosso dal turno '{desc}'.")
            log_shift_change(
                t_id, "Rimozione", matricola_originale=m,
                matricola_eseguito_da=st.session_state["authenticated_user"]
            )

    for m in new_set - old_set:
        role = "Tecnico" if m in new_techs else "Aiutante"
        if add_booking({"ID_Turno": t_id, "Matricola": m, "RuoloOccupato": role}):
            crea_notifica(m, f"Aggiunto al turno '{desc}'.")
            log_shift_change(
                t_id, "Aggiunta", matricola_subentrante=m,
                matricola_eseguito_da=st.session_state["authenticated_user"]
            )
