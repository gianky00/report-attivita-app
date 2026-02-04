import datetime

import pandas as pd
import streamlit as st

from modules.data_manager import _carica_giornaliera_mese
from modules.db_manager import get_last_login, get_unvalidated_reports_by_technician
from modules.oncall_logic import get_next_on_call_week
from modules.session_manager import delete_session
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
        date_display = (
            f" del {task['data_attivita'].strftime('%d/%m/%Y')}"
            if "data_attivita" in task
            else ""
        )
        with st.expander(f"**PdL `{task['pdl']}`** - {task['attivita']}{date_display}"):
            st.markdown('<div class="task-card">', unsafe_allow_html=True)

            if "data_attivita" in task and task["data_attivita"]:
                try:
                    activity_date = pd.to_datetime(task["data_attivita"]).strftime(
                        "%d/%m/%Y"
                    )
                    st.markdown(f"**Assegnato il:** {activity_date}")
                except (ValueError, TypeError):
                    st.markdown("**Assegnato il:** Data non disponibile")

            team = task.get("team", [])
            if len(team) > 1:
                team_details_md = "**Team:**\n\n"
                for member in team:
                    orari_accorpati = merge_time_slots(member["orari"])
                    orari_str = ", ".join(orari_accorpati)
                    team_details_md += (
                        f"{member['nome']} ({member['ruolo']})  \n🕒 {orari_str}\n\n"
                    )
                st.info(team_details_md)

            visualizza_storico_organizzato(task.get("storico", []), task["pdl"])

            if len(task.get("team", [])) > 1 and ruolo_utente == "Aiutante":
                st.warning(
                    "ℹ️ Solo i tecnici possono compilare il report per questa attività di team."
                )
            else:
                if st.button(
                    "📝 Compila Report", key=f"manual_{section_key}_{i}", type="primary"
                ):
                    st.session_state.debriefing_task = {
                        **task,
                        "section_key": section_key,
                    }
                    st.session_state.report_mode = "manual"
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    matricola_utente = st.session_state.get("authenticated_user", "")
    if matricola_utente:
        unvalidated_reports_df = get_unvalidated_reports_by_technician(matricola_utente)
        if not unvalidated_reports_df.empty:
            with st.expander("✅ Attività Inviate (Modificabili)", expanded=True):
                for _, report in unvalidated_reports_df.iterrows():
                    with st.container(border=True):
                        st.markdown(
                            f"**PdL `{report['pdl']}`** - Inviato il {pd.to_datetime(report['data_compilazione']).strftime('%d/%m/%Y %H:%M')}"
                        )
                        st.caption("Report Inviato:")
                        st.info(report["testo_report"])
                        if st.button(
                            "Modifica Report",
                            key=f"edit_report_{section_key}_{report['id_report']}",
                        ):
                            task_data = report.to_dict()
                            task_data["section_key"] = section_key
                            st.session_state.debriefing_task = task_data
                            st.session_state.report_mode = "manual"
                            st.rerun()


from modules.notifications import leggi_notifiche, segna_notifica_letta


def render_notification_center(notifications_df, matricola_utente):
    unread_count = len(notifications_df[notifications_df["Stato"] == "non letta"])
    icon_label = f"🔔 {unread_count}" if unread_count > 0 else "🔔"

    with st.popover(icon_label):
        st.subheader("Notifiche")
        if notifications_df.empty:
            st.write("Nessuna notifica.")
        else:
            for _, notifica in notifications_df.iterrows():
                notifica_id = notifica["ID_Notifica"]
                is_unread = notifica["Stato"] == "non letta"

                col1, col2 = st.columns([4, 1])
                with col1:
                    if is_unread:
                        st.markdown(f"**{notifica['Messaggio']}**")
                    else:
                        st.markdown(
                            f"<span style='color: grey;'>{notifica['Messaggio']}</span>",
                            unsafe_allow_html=True,
                        )
                    st.caption(
                        pd.to_datetime(notifica["Timestamp"]).strftime("%d/%m/%Y %H:%M")
                    )

                with col2:
                    if is_unread:
                        if st.button(
                            " letto", key=f"read_{notifica_id}", help="Segna come letto"
                        ):
                            segna_notifica_letta(notifica_id)
                            st.rerun()
                st.divider()


def render_sidebar(matricola_utente, nome_utente_autenticato, ruolo):
    """Renders the sidebar navigation, on-call info, notifications, and logout."""
    with st.sidebar:
        st.header(f"Ciao, {nome_utente_autenticato}!")
        st.caption(f"Ruolo: {ruolo}")

        user_surname = nome_utente_autenticato.split()[-1]
        next_oncall_start = get_next_on_call_week(user_surname)
        if next_oncall_start:
            next_oncall_end = next_oncall_start + datetime.timedelta(days=6)
            today = datetime.date.today()

            if next_oncall_start <= today <= next_oncall_end:
                st.markdown("**Sei reperibile**")
                message = f"Dal: {next_oncall_start.strftime('%d/%m')} al {next_oncall_end.strftime('%d/%m/%Y')}"
            else:
                message = f"Prossima Reperibilità:\n{next_oncall_start.strftime('%d/%m')} - {next_oncall_end.strftime('%d/%m/%Y')}"

            st.info(message)

        user_notifications = leggi_notifiche(matricola_utente)
        render_notification_center(user_notifications, matricola_utente)

        last_login = get_last_login(matricola_utente)
        if last_login:
            last_login_dt = pd.to_datetime(last_login)
            st.caption(f"Ultimo accesso: {last_login_dt.strftime('%d/%m/%Y %H:%M')}")

        st.divider()

        if st.button("📝 Attività Assegnate", use_container_width=True):
            st.session_state.main_tab = "Attività Assegnate"
            st.session_state.navigated = True
            _carica_giornaliera_mese.clear()
            st.rerun()

        if st.button("🗂️ Storico", use_container_width=True):
            st.session_state.main_tab = "Storico"
            st.session_state.navigated = True
            st.rerun()

        st.divider()

        if st.button("📅 Gestione Turni", use_container_width=True):
            st.session_state.main_tab = "📅 Gestione Turni"
            st.session_state.navigated = True
            st.rerun()

        if st.button("Richieste", use_container_width=True):
            st.session_state.main_tab = "Richieste"
            st.session_state.navigated = True
            st.rerun()

        expandable_menu_items = {}
        if ruolo == "Amministratore":
            expandable_menu_items["⚙️ Amministrazione"] = ["Caposquadra", "Sistema"]

        for main_item, sub_items in expandable_menu_items.items():
            is_expanded = main_item == st.session_state.expanded_menu

            if st.button(main_item, use_container_width=True):
                st.session_state.expanded_menu = main_item if not is_expanded else ""
                st.session_state.navigated = True
                st.rerun()

            if is_expanded:
                for sub_item in sub_items:
                    if st.button(
                        sub_item, key=f"nav_{sub_item}", use_container_width=True
                    ):
                        st.session_state.main_tab = sub_item
                        st.session_state.navigated = True
                        st.rerun()

        st.divider()
        if st.button("❓ Guida", use_container_width=True):
            st.session_state.main_tab = "❓ Guida"
            st.session_state.navigated = True
            st.rerun()
        if st.button("Disconnetti", use_container_width=True):
            token_to_delete = st.session_state.get("session_token")
            delete_session(token_to_delete)
            keys_to_clear = list(st.session_state.keys())
            for key in keys_to_clear:
                del st.session_state[key]
            st.query_params.clear()
            st.rerun()
