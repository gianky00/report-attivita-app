"""
Componenti UI per la visualizzazione delle attività assegnate e dello storico.
"""
import pandas as pd
import streamlit as st
from modules.db_manager import get_unvalidated_reports_by_technician
from modules.utils import merge_time_slots

def visualizza_storico_organizzato(storico_list, pdl):
    """Mostra lo storico di un'attività in modo organizzato, usando st.toggle."""
    if storico_list:
        with st.expander(f"Mostra cronologia interventi per PdL {pdl}", expanded=False):
            try:
                storico_list.sort(
                    key=lambda x: pd.to_datetime(x.get("Data_Riferimento_dt")),
                    reverse=True,
                )
            except (TypeError, ValueError):
                pass

            for i, intervento in enumerate(storico_list):
                data_dt = pd.to_datetime(
                    intervento.get("Data_Riferimento_dt"), errors="coerce"
                )
                if pd.notna(data_dt):
                    toggle_key = f"toggle_{pdl}_{i}"
                    label = f"Intervento del {data_dt.strftime('%d/%m/%Y')}"

                    if st.toggle(label, key=toggle_key):
                        st.markdown(
                            f"**Data:** {data_dt.strftime('%d/%m/%Y')} - **Tecnico:** {intervento.get('Tecnico', 'N/D')}"
                        )
                        st.info(
                            f"**Report:** {intervento.get('Report', 'Nessun report.')}"
                        )
                        st.markdown("---")
    else:
        st.markdown("*Nessuno storico disponibile per questo PdL.*")

def disegna_sezione_attivita(lista_attivita, section_key, ruolo_utente):
    """Disegna la lista delle attività da compilare e quelle già inviate."""
    if f"completed_tasks_{section_key}" not in st.session_state:
        st.session_state[f"completed_tasks_{section_key}"] = []

    completed_pdls = {
        task["pdl"]
        for task in st.session_state.get(f"completed_tasks_{section_key}", [])
    }
    attivita_da_fare = [
        task for task in lista_attivita if task["pdl"] not in completed_pdls
    ]

    st.header("📝 Attività da Compilare")
    if not attivita_da_fare:
        st.success("Tutte le attività per questa sezione sono state compilate.")

    for i, task in enumerate(attivita_da_fare):
        _render_attivita_card(task, i, section_key, ruolo_utente)

    st.divider()
    _render_unvalidated_section(section_key)

def _render_attivita_card(task, idx, section_key, ruolo_utente):
    """Sotto-funzione per renderizzare la singola card attività."""
    date_display = f" del {task['data_attivita'].strftime('%d/%m/%Y')}" if "data_attivita" in task else ""
    with st.expander(f"**PdL `{task['pdl']}`** - {task['attivita']}{date_display}"):
        st.markdown('<div class="task-card">', unsafe_allow_html=True)

        if "data_attivita" in task and task["data_attivita"]:
            with st.container():
                try:
                    dt = pd.to_datetime(task["data_attivita"]).strftime("%d/%m/%Y")
                    st.markdown(f"**Assegnato il:** {dt}")
                except (ValueError, TypeError):
                    st.markdown("**Assegnato il:** Data non disponibile")

        _render_team_info(task.get("team", []))
        visualizza_storico_organizzato(task.get("storico", []), task["pdl"])

        if len(task.get("team", [])) > 1 and ruolo_utente == "Aiutante":
            st.warning("ℹ️ Solo i tecnici possono compilare il report per attività di team.")
        else:
            if st.button("📝 Compila Report", key=f"manual_{section_key}_{idx}", type="primary"):
                st.session_state.debriefing_task = {**task, "section_key": section_key}
                st.session_state.report_mode = "manual"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

def _render_team_info(team):
    """Visualizza le informazioni sui membri del team."""
    if len(team) > 1:
        details = "**Team:**\n\n"
        for member in team:
            slots = merge_time_slots(member["orari"])
            details += f"{member['nome']} ({member['ruolo']})  \n🕒 {', '.join(slots)}\n\n"
        st.info(details)

def _render_unvalidated_section(section_key):
    """Visualizza i report inviati e ancora modificabili."""
    matricola = st.session_state.get("authenticated_user", "")
    if not matricola:
        return

    df = get_unvalidated_reports_by_technician(matricola)
    if not df.empty:
        with st.expander("✅ Attività Inviate (Modificabili)", expanded=True):
            for _, r in df.iterrows():
                with st.container(border=True):
                    st.markdown(f"**PdL `{r['pdl']}`** - Inviato il {pd.to_datetime(r['data_compilazione']).strftime('%d/%m/%Y %H:%M')}")
                    st.info(r["testo_report"])
                    if st.button("Modifica Report", key=f"edit_{section_key}_{r['id_report']}"):
                        task_data = r.to_dict()
                        task_data["section_key"] = section_key
                        st.session_state.debriefing_task = task_data
                        st.session_state.report_mode = "manual"
                        st.rerun()
