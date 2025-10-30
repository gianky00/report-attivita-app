import streamlit as st
import pandas as pd
from modules.utils import merge_time_slots
from modules.db_manager import get_unvalidated_reports_by_technician

def visualizza_storico_organizzato(storico_list, pdl):
    """Mostra lo storico di un'attività in modo organizzato, usando st.toggle."""
    if storico_list:
        with st.expander(f"Mostra cronologia interventi per PdL {pdl}", expanded=False):
            try:
                storico_list.sort(key=lambda x: pd.to_datetime(x.get('Data_Riferimento_dt')), reverse=True)
            except (TypeError, ValueError):
                pass

            for i, intervento in enumerate(storico_list):
                data_dt = pd.to_datetime(intervento.get('Data_Riferimento_dt'), errors='coerce')
                if pd.notna(data_dt):
                    toggle_key = f"toggle_{pdl}_{i}"
                    label = f"Intervento del {data_dt.strftime('%d/%m/%Y')}"

                    if st.toggle(label, key=toggle_key):
                        st.markdown(f"**Data:** {data_dt.strftime('%d/%m/%Y')} - **Tecnico:** {intervento.get('Tecnico', 'N/D')}")
                        st.info(f"**Report:** {intervento.get('Report', 'Nessun report.')}")
                        st.markdown("---")
    else:
        st.markdown("*Nessuno storico disponibile per questo PdL.*")

def disegna_sezione_attivita(lista_attivita, section_key, ruolo_utente):
    if f"completed_tasks_{section_key}" not in st.session_state:
        st.session_state[f"completed_tasks_{section_key}"] = []

    completed_pdls = {task['pdl'] for task in st.session_state.get(f"completed_tasks_{section_key}", [])}
    attivita_da_fare = [task for task in lista_attivita if task['pdl'] not in completed_pdls]

    st.header("📝 Attività da Compilare")
    if not attivita_da_fare:
        st.success("Tutte le attività per questa sezione sono state compilate.")

    for i, task in enumerate(attivita_da_fare):
        date_display = f" del {task['data_attivita'].strftime('%d/%m/%Y')}" if 'data_attivita' in task else ""
        with st.expander(f"**PdL `{task['pdl']}`** - {task['attivita']}{date_display}"):
            st.markdown('<div class="task-card">', unsafe_allow_html=True)

            if 'data_attivita' in task and task['data_attivita']:
                try:
                    activity_date = pd.to_datetime(task['data_attivita']).strftime('%d/%m/%Y')
                    st.markdown(f"**Assegnato il:** {activity_date}")
                except (ValueError, TypeError):
                    st.markdown(f"**Assegnato il:** Data non disponibile")

            team = task.get('team', [])
            if len(team) > 1:
                team_details_md = "**Team:**\n"
                for member in team:
                    orari_accorpati = merge_time_slots(member['orari'])
                    orari_str = ", ".join(orari_accorpati)
                    team_details_md += f"- {member['nome']} ({member['ruolo']}) | 🕒 {orari_str}\n"
                st.info(team_details_md)

            visualizza_storico_organizzato(task.get('storico', []), task['pdl'])

            if len(task.get('team', [])) > 1 and ruolo_utente == "Aiutante":
                st.warning("ℹ️ Solo i tecnici possono compilare il report per questa attività di team.")
            else:
                if st.button("📝 Compila Report", key=f"manual_{section_key}_{i}", type="primary"):
                    st.session_state.debriefing_task = {**task, "section_key": section_key}
                    st.session_state.report_mode = 'manual'
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    matricola_utente = st.session_state.get('authenticated_user', '')
    if matricola_utente:
        unvalidated_reports_df = get_unvalidated_reports_by_technician(matricola_utente)
        if not unvalidated_reports_df.empty:
            with st.expander("✅ Attività Inviate (Modificabili)", expanded=True):
                for _, report in unvalidated_reports_df.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**PdL `{report['pdl']}`** - Inviato il {pd.to_datetime(report['data_compilazione']).strftime('%d/%m/%Y %H:%M')}")
                        st.caption("Report Inviato:")
                        st.info(report['testo_report'])
                        if st.button("Modifica Report", key=f"edit_report_{report['id_report']}"):
                            task_data = report.to_dict()
                            st.session_state.debriefing_task = task_data
                            st.session_state.report_mode = 'manual'
                            st.rerun()

from modules.notifications import segna_notifica_letta

def render_notification_center(notifications_df, matricola_utente):
    unread_count = len(notifications_df[notifications_df['Stato'] == 'non letta'])
    icon_label = f"🔔 {unread_count}" if unread_count > 0 else "🔔"

    with st.popover(icon_label):
        st.subheader("Notifiche")
        if notifications_df.empty:
            st.write("Nessuna notifica.")
        else:
            for _, notifica in notifications_df.iterrows():
                notifica_id = notifica['ID_Notifica']
                is_unread = notifica['Stato'] == 'non letta'

                col1, col2 = st.columns([4, 1])
                with col1:
                    if is_unread:
                        st.markdown(f"**{notifica['Messaggio']}**")
                    else:
                        st.markdown(f"<span style='color: grey;'>{notifica['Messaggio']}</span>", unsafe_allow_html=True)
                    st.caption(pd.to_datetime(notifica['Timestamp']).strftime('%d/%m/%Y %H:%M'))

                with col2:
                    if is_unread:
                        if st.button(" letto", key=f"read_{notifica_id}", help="Segna come letto"):
                            segna_notifica_letta(notifica_id)
                            st.rerun()
                st.divider()
