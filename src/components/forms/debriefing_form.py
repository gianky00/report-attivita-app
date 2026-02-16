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
    ore: float,
    task: dict[str, Any],
    matricola_utente: str,
    data_riferimento: Any,
) -> bool:
    """Gestisce il salvataggio dei dati del report attività."""
    if not report_text.strip():
        st.warning("Il report non può essere vuoto.")
        return False

    # Estrazione nomi del team in una stringa separata da virgole
    team_members = [m["nome"] for m in task.get("team", [])]
    team_string = ", ".join(team_members)

    dati = {
        "descrizione": f"PdL {task['pdl']} - {task['attivita']}",
        "report": report_text,
        "stato": stato,
        "ore": str(ore),
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
    st.subheader(f"PdL `{task['pdl']}` - {task['attivita']}")
    report_text = st.text_area(
        "Inserisci il tuo report qui:", value=task.get("report", ""), height=200
    )

    c_ore, c_stato = st.columns(2)
    ore = c_ore.number_input("Ore Lavoro", min_value=0.5, max_value=12.0, value=2.0, step=0.5)

    opts = STATI_ATTIVITA
    current = task.get("stato")
    idx = opts.index(current) if current in opts else 0
    stato = c_stato.selectbox("Stato Finale", opts, index=idx, key="manual_stato")

    c1, c2 = st.columns(2)
    if c1.button("Invia Report", type="primary") and handle_submit(
        report_text, stato, ore, task, matricola_utente, data_riferimento
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
