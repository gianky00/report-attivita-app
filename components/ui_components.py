import streamlit as st
import pandas as pd

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

    st.subheader("📝 Attività da Compilare")
    if not attivita_da_fare:
        st.info("Tutte le attività per questa sezione sono state compilate.")

    for i, task in enumerate(attivita_da_fare):
        with st.container(border=True):
            date_display = ""
            if 'data_attivita' in task:
                date_display = f" del **{task['data_attivita'].strftime('%d/%m/%Y')}**"

            st.markdown(f"**PdL `{task['pdl']}`** - {task['attivita']}{date_display}")

            team = task.get('team', [])
            if len(team) > 1:
                team_details_md = "**Team:**\n"
                for member in team:
                    orari_str = ", ".join(member['orari'])
                    team_details_md += f"- {member['nome']} ({member['ruolo']}) | 🕒 {orari_str}\n"
                st.info(team_details_md)

            visualizza_storico_organizzato(task.get('storico', []), task['pdl'])
            st.markdown("---")

            if len(task.get('team', [])) > 1 and ruolo_utente == "Aiutante":
                st.warning("ℹ️ Solo i tecnici possono compilare il report per questa attività di team.")
            else:
                if st.button("📝 Compila Report", key=f"manual_{section_key}_{i}"):
                    st.session_state.debriefing_task = {**task, "section_key": section_key}
                    st.session_state.report_mode = 'manual'
                    st.rerun()

    st.divider()

    if st.session_state.get(f"completed_tasks_{section_key}", []):
        with st.expander("✅ Attività Inviate (Modificabili)", expanded=False):
            for i, task_data in enumerate(st.session_state[f"completed_tasks_{section_key}"]):
                with st.container(border=True):
                    st.markdown(f"**PdL `{task_data['pdl']}`** - {task_data['stato']}")
                    st.caption("Report Inviato:")
                    st.info(task_data['report'])
                    if st.button("Modifica Report", key=f"edit_{section_key}_{i}"):
                        st.session_state.debriefing_task = task_data
                        st.session_state.report_mode = 'manual'
                        st.rerun()

def render_notification_center(notifications_df, gestionale_data, matricola_utente):
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
                            segna_notifica_letta(gestionale_data, notifica_id)
                            salva_gestionale_async(gestionale_data)
                            st.rerun()
                st.divider()
