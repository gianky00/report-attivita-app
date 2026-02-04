import datetime

import pandas as pd
import streamlit as st

from modules.db_manager import (
    get_all_users,
    get_shift_by_id,
    get_shifts_by_type,
)
from modules.shift_management import (
    manual_override_logic,
    pubblica_turno_in_bacheca_logic,
    richiedi_sostituzione_logic,
)

# --- COSTANTI LOCALI ---
HOLIDAYS_2025 = [
    datetime.date(2025, 1, 1), datetime.date(2025, 1, 6), datetime.date(2025, 4, 20),
    datetime.date(2025, 4, 21), datetime.date(2025, 4, 25), datetime.date(2025, 5, 1),
    datetime.date(2025, 6, 2), datetime.date(2025, 8, 15), datetime.date(2025, 11, 1),
    datetime.date(2025, 12, 8), datetime.date(2025, 12, 13), datetime.date(2025, 12, 25),
    datetime.date(2025, 12, 26),
]
WEEKDAY_NAMES_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
MESI_ITALIANI = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


def render_reperibilita_tab(df_prenotazioni, df_contatti, matricola_utente, ruolo_utente):
    """Renderizza il tab della reperibilità settimanale."""
    st.subheader("📅 Calendario Reperibilità")

    if st.session_state.get("editing_oncall_shift_id"):
        _render_oncall_edit_form(matricola_utente)
        return

    if st.session_state.get("managing_oncall_shift_id"):
        _render_oncall_management_form(df_contatti)
        return

    _render_oncall_filters()
    st.divider()
    _render_oncall_export_section(df_prenotazioni, df_contatti, ruolo_utente)
    _render_oncall_navigation()
    st.divider()
    _render_oncall_calendar_grid(df_prenotazioni, df_contatti, matricola_utente, ruolo_utente)


def _render_oncall_edit_form(admin_id):
    """Form di modifica manuale del turno (solo admin)."""
    s_id = st.session_state.editing_oncall_shift_id
    info = get_shift_by_id(s_id)
    with st.container(border=True):
        dt = pd.to_datetime(info["Data"]).strftime("%d/%m/%Y")
        st.subheader(f"Modifica per il {dt}")
        users = get_all_users()
        u_list = users["Matricola"].tolist()
        u_dict = pd.Series(users["Nome Cognome"].values, index=users["Matricola"]).to_dict()

        t1 = st.selectbox("Tecnico 1:", options=u_list, format_func=lambda x: u_dict.get(x, x))
        t2 = st.selectbox("Tecnico 2:", options=u_list, format_func=lambda x: u_dict.get(x, x), index=1 if len(u_list)>1 else 0)

        c1, c2 = st.columns(2)
        if c1.button("Salva", type="primary"):
            if manual_override_logic(s_id, t1, t2, admin_id):
                del st.session_state.editing_oncall_shift_id
                st.rerun()
        if c2.button("Annulla"):
            del st.session_state.editing_oncall_shift_id
            st.rerun()
    st.stop()


def _render_oncall_management_form(df_contatti):
    """Form di gestione (Bacheca/Scambio) per il tecnico titolare del turno."""
    s_id = st.session_state.managing_oncall_shift_id
    m_id = st.session_state.managing_oncall_user_matricola
    u_name = df_contatti[df_contatti["Matricola"] == m_id].iloc[0]["Nome Cognome"]
    info = get_shift_by_id(s_id)

    with st.container(border=True):
        st.subheader("Gestione Turno")
        if info:
            st.write(f"Turno di **{u_name}** del **{pd.to_datetime(info['Data']).strftime('%d/%m/%Y')}**")
        else:
            st.error("Errore turno."); st.button("Indietro", on_click=lambda: st.session_state.pop("managing_oncall_shift_id"))
            return

        if st.session_state.get("oncall_swap_mode"):
            _render_oncall_swap_ui(m_id, s_id, df_contatti)
        else:
            c1, c2 = st.columns(2)
            if c1.button("📢 Pubblica in Bacheca"):
                if pubblica_turno_in_bacheca_logic(m_id, s_id):
                    del st.session_state.managing_oncall_shift_id
                    st.rerun()
            if c2.button("🔄 Chiedi Sostituzione"):
                st.session_state.oncall_swap_mode = True
                st.rerun()

        if st.button("⬅️ Torna al Calendario"):
            for k in ["managing_oncall_shift_id", "managing_oncall_user_matricola", "oncall_swap_mode"]:
                st.session_state.pop(k, None)
            st.rerun()
    st.stop()


def _render_oncall_swap_ui(m_id, s_id, df_contatti):
    """UI specifica per lo scambio della reperibilità."""
    valid = df_contatti[(df_contatti["Matricola"] != m_id) & (df_contatti["PasswordHash"].notna())]
    m_to_n = pd.Series(valid["Nome Cognome"].values, index=valid["Matricola"]).to_dict()
    target = st.selectbox("Collega:", valid["Matricola"].tolist(), format_func=lambda m: m_to_n.get(m, m))

    if st.button("Invia Richiesta", type="primary"):
        if richiedi_sostituzione_logic(m_id, target, s_id):
            for k in ["managing_oncall_shift_id", "oncall_swap_mode"]: st.session_state.pop(k, None)
            st.rerun()


def _render_oncall_filters():
    """Filtri temporali per la reperibilità."""
    today = datetime.date.today()
    c = st.columns([2, 2, 3, 3])
    y = c[0].selectbox("Anno", list(range(today.year - 2, today.year + 3)), index=2, label_visibility="collapsed")
    m = c[1].selectbox("Mese", MESI_ITALIANI, index=today.month - 1, label_visibility="collapsed")
    if c[2].button("Vai al mese", use_container_width=True):
        first = datetime.date(y, MESI_ITALIANI.index(m) + 1, 1)
        st.session_state.week_start_date = first - datetime.timedelta(days=first.weekday())
        st.rerun()
    if c[3].button("Sett. Corrente", use_container_width=True):
        st.session_state.week_start_date = today - datetime.timedelta(days=today.weekday())
        st.rerun()


def _render_oncall_export_section(df_p, df_c, ruolo):
    """Sezione export PDF per amministratori."""
    if ruolo == "Amministratore" and st.button("Esporta PDF", use_container_width=True):
        st.info("Funzionalità di esportazione avviata...")
        st.warning("L'export PDF richiede dati contestuali dei filtri.")


def _render_oncall_navigation():
    """Pulsanti di navigazione settimanale."""
    c = st.columns([1, 10, 1])
    if c[0].button("⬅️", use_container_width=True):
        st.session_state.week_start_date -= datetime.timedelta(days=7); st.rerun()

    start = st.session_state.week_start_date
    end = start + datetime.timedelta(days=6)
    st.markdown(f"<h5 style='text-align: center;'>{start.day} {MESI_ITALIANI[start.month-1][:3]} - {end.day} {MESI_ITALIANI[end.month-1][:3]} {end.year}</h5>", unsafe_allow_html=True)

    if c[2].button("➡️", use_container_width=True):
        st.session_state.week_start_date += datetime.timedelta(days=7); st.rerun()


def _render_oncall_calendar_grid(df_p, df_c, matricola, ruolo):
    """Disegna la griglia dei 7 giorni della settimana corrente."""
    today = datetime.date.today()
    shifts = get_shifts_by_type("Reperibilità")
    shifts["Data"] = pd.to_datetime(shifts["Data"], format="mixed", errors="coerce").dt.date

    dates = [st.session_state.week_start_date + datetime.timedelta(days=i) for i in range(7)]
    cols = st.columns(7)
    m_to_n = pd.Series(df_c["Nome Cognome"].values, index=df_c["Matricola"].astype(str)).to_dict()

    for i, day in enumerate(dates):
        with cols[i]:
            _render_day_cell(day, today, shifts, df_p, m_to_n, matricola, ruolo)


def _render_day_cell(day, today, shifts, df_p, m_to_n, matricola, ruolo):
    """Renderizza la singola cella del calendario."""
    is_today = day == today
    is_special = day.weekday() == 6 or day in HOLIDAYS_2025

    bg = "#e0f7fa" if is_today else ("#fff0f0" if is_special else "white")
    color = "red" if is_special else "inherit"
    border = "2px solid #007bff" if is_today else "1px solid #d3d3d3"

    shift = shifts[shifts["Data"] == day]
    s_id, tech_html, user_on_call, managed_mat = None, "N/D", False, matricola

    if not shift.empty:
        s_id = shift.iloc[0]["ID_Turno"]
        p_today = df_p[df_p["ID_Turno"] == s_id]
        if not p_today.empty:
            tech_list = []
            for _, b in p_today.iterrows():
                m = str(b["Matricola"])
                name = m_to_n.get(m, f"M. {m}")
                tech_list.append(name.split()[-1].upper())
                if m == str(matricola): user_on_call = True
            managed_mat = str(p_today.iloc[0]["Matricola"])
            tech_html = "".join([f"<div style='font-size: 0.8em; font-weight: 500;'>{s}</div>" for s in tech_list])
        else:
            tech_html = "<span style='color: grey; font-style: italic;'>Libero</span>"

    st.markdown(f"""
        <div style="border: {border}; border-radius: 8px; padding: 8px; background-color: {bg}; height: 130px;">
            <p style="font-weight: bold; color: {color}; margin: 0; font-size: 0.8em;">{WEEKDAY_NAMES_IT[day.weekday()]}</p>
            <h3 style="margin: 0; color: {color};">{day.day}</h3>
            <div style="text-align: right; margin-top: 5px;">{tech_html}</div>
        </div>
    """, unsafe_allow_html=True)

    if (user_on_call or ruolo == "Amministratore") and s_id:
        c1, c2 = st.columns(2)
        if c1.button("🛠️", key=f"m_{day}", help="Gestisci"):
            st.session_state.managing_oncall_shift_id = s_id
            st.session_state.managing_oncall_user_matricola = managed_mat
            st.rerun()
        if ruolo == "Amministratore" and c2.button("✏️", key=f"e_{day}", help="Modifica"):
            st.session_state.editing_oncall_shift_id = s_id
            st.rerun()
