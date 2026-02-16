"""
Form per la compilazione del report di attività (debriefing).
"""

from typing import Any

import streamlit as st

from constants import STATI_ATTIVITA
from modules.data_manager import scrivi_o_aggiorna_risposta


def handle_submit(
    report_text: str,
    stato: str,
    task: dict[str, Any],
    matricola_utente: str,
    data_riferimento: Any,
) -> bool:
    """Gestisce il salvataggio dei dati del report attività."""
    if not report_text.strip() and stato != "IN CORSO":
        st.warning("Il report non può essere vuoto (opzionale solo se 'IN CORSO').")
        return False

    # Estrazione nomi del team: gestisce sia lista (Excel) che stringa (DB)
    raw_team = task.get("team")
    if isinstance(raw_team, list):
        team_string = ", ".join([str(m.get("nome", "")) for m in raw_team])
    elif isinstance(raw_team, str):
        team_string = raw_team
    else:
        team_string = ""

    desc = task.get("attivita") or task.get("descrizione_attivita") or "N/D"
    dati = {
        "descrizione": f"PdL {task['pdl']} - {desc}",
        "report": report_text,
        "stato": stato,
        "ore": str(task.get("ore_lavoro", 0.0)),
        "team_completo": team_string,
    }

    if scrivi_o_aggiorna_risposta(dati, matricola_utente, data_riferimento):
        _update_completed_tasks(task, report_text, stato, task["section_key"])
        st.success("Report inviato con successo!")
        del st.session_state.debriefing_task
        st.balloons()
        return True
    else:
        st.error("Errore durante il salvataggio del report.")
        return False


def render_debriefing_ui(
    knowledge_core: dict[str, Any], matricola_utente: str, data_riferimento: Any
) -> None:
    """UI per la compilazione del report di attività dopo un intervento."""
    task = st.session_state.debriefing_task

    from modules.utils import render_svg_icon

    st.markdown(
        render_svg_icon("report", 32) + "<h1 style='display:inline;'>Compila Report</h1>",
        unsafe_allow_html=True,
    )

    # Gestione compatibilità nomi chiavi (Excel vs Database)
    desc = task.get("attivita") or task.get("descrizione_attivita") or "Descrizione non disponibile"
    pdl = task.get("pdl", "N/D")

    st.subheader(f"PdL `{pdl}` - {desc}")
    report_text = st.text_area(
        "Inserisci il tuo report qui:",
        value=task.get("report", "") or task.get("testo_report", ""),
        height=200,
    )

    c_ore, c_stato = st.columns(2)
    # Gestione ore (possono venire da 'ore_lavoro' di Excel o 'ore_lavoro' del DB)
    ore_val = task.get("ore_lavoro", 0.0)
    c_ore.markdown(f"**Ore Lavoro (Auto):** {ore_val}")

    opts = STATI_ATTIVITA
    current = task.get("stato") or task.get("stato_attivita")
    idx = opts.index(current) if current in opts else 0
    stato = c_stato.selectbox("Stato Finale", opts, index=idx, key="manual_stato")

    c1, c2 = st.columns(2)
    if c1.button("Invia Report", type="primary") and handle_submit(
        report_text, stato, task, matricola_utente, data_riferimento
    ):
        st.rerun()
    if c2.button("Annulla"):
        del st.session_state.debriefing_task
        st.rerun()


def _update_completed_tasks(
    task: dict[str, Any], report: str, stato: str, section_key: str
) -> None:
    """Aggiorna lo stato delle attività completate nella sessione Streamlit."""
    completed_data = task | {"report": report, "stato": stato}
    key = f"completed_tasks_{section_key}"

    current_list = st.session_state.get(key, [])
    current_list = [t for t in current_list if t["pdl"] != task["pdl"]]
    current_list.append(completed_data)
    st.session_state[key] = current_list

    if section_key == "yesterday":
        if "completed_tasks_yesterday" not in st.session_state:
            st.session_state.completed_tasks_yesterday = []
        st.session_state.completed_tasks_yesterday.append(completed_data)
