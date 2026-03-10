"""
Modulo principale del Gestionale Tecnici.
Gestisce l'interfaccia Streamlit e la logica di navigazione principale.
Il flusso di login è delegato a login_handler.py.
"""

import datetime
from typing import Any

import pandas as pd
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

from components.form_handlers import render_debriefing_ui, render_edit_shift_form
from components.ui_components import (
    disegna_sezione_attivita,
    render_sidebar,
)
from constants import ICONS

# Re-export per backward compatibility (usato dai test e da __main__)
from login_handler import handle_login_and_navigation
from modules.auth import (
    get_user_by_matricola,
)
from modules.data_manager import (
    carica_knowledge_core,
    trova_attivita,
)
from modules.db_manager import (
    get_all_users,
    get_validated_intervention_reports,
)
from modules.license_manager import check_pyarmor_license
from modules.shift_management import sync_oncall_shifts
from pages.admin import render_caposquadra_view, render_sistema_view
from pages.gestione_turni import render_gestione_turni_tab
from pages.guida import render_guida_tab
from pages.programmazione_view import render_programmazione_pdl_page
from pages.richieste import render_richieste_tab

# --- ESEGUI CHECK LICENZA ALL'AVVIO ---
check_pyarmor_license()


@st.cache_resource
def autorizza_google() -> Any:
    """Autorizza l'accesso alle API di Google Sheets."""
    import gspread

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    if creds.access_token_expired:
        client.login()  # type: ignore[attr-defined]
    return client


def recupera_attivita_non_rendicontate(
    matricola_utente: str, df_contatti: pd.DataFrame
) -> list[dict[str, Any]]:
    """Recupera le attività non rendicontate degli ultimi 30 giorni."""
    oggi = datetime.date.today()
    attivita_da_recuperare = []
    for i in range(1, 31):
        giorno_controllo = oggi - datetime.timedelta(days=i)
        attivita_giorno = trova_attivita(
            matricola_utente,
            giorno_controllo.day,
            giorno_controllo.month,
            giorno_controllo.year,
            df_contatti,
        )
        for task in attivita_giorno:
            task["data_attivita"] = giorno_controllo
        attivita_da_recuperare.extend(attivita_giorno)
    return attivita_da_recuperare


def main_app(matricola_utente: str, ruolo: str) -> None:
    """
    Gestisce l'interfaccia utente principale dopo l'autenticazione.
    Include sidebar, notifiche, navigazione tra i tab e rendering dei moduli.
    """
    # Avvio sincronizzazione elastica (non bloccante)
    from modules.data_manager import trigger_smart_sync

    trigger_smart_sync()

    st.set_page_config(
        layout="wide",
        page_title="Horizon - Technical Operations Platform",
        page_icon="assets/icons/settings.svg",
        initial_sidebar_state="auto",
    )

    def load_css(file_name: str) -> None:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    load_css("src/styles/style.css")

    user_info = get_user_by_matricola(matricola_utente)
    if not user_info:
        st.error("Errore critico: dati utente non trovati.")
        st.stop()
    nome_utente_autenticato = user_info["Nome Cognome"]

    today = datetime.date.today()
    start_sync = today - datetime.timedelta(days=180)
    end_sync = today + datetime.timedelta(days=180)
    sync_oncall_shifts(start_date=start_sync, end_date=end_sync)

    if st.session_state.get("editing_turno_id"):
        render_edit_shift_form()
    elif st.session_state.get("debriefing_task"):
        knowledge_core = carica_knowledge_core()
        if knowledge_core is not None:
            task_info = st.session_state.debriefing_task
            data_rif = task_info.get("data_attivita", datetime.date.today())
            render_debriefing_ui(knowledge_core, matricola_utente, data_rif)
    else:
        render_sidebar(matricola_utente, nome_utente_autenticato, ruolo)

        # Controllo connettività dati
        from config import check_data_connectivity

        status = check_data_connectivity()
        if not all(status.values()):
            with st.sidebar:
                st.error(f"{ICONS['WARNING']} Errore Connessione Dati")
                for name, available in status.items():
                    color = "green" if available else "red"
                    st.markdown(
                        f"- {name}: <span style='color:{color}'>{'OK' if available else 'NON DISPONIBILE'}</span>",
                        unsafe_allow_html=True,
                    )
                st.warning(
                    "Alcune funzionalità (Recupero Attività) potrebbero non funzionare correttamente."
                )

        st.header(st.session_state.main_tab)
        st.markdown('<div class="main-container">', unsafe_allow_html=True)
        st.markdown('<div class="page-content">', unsafe_allow_html=True)

        selected_tab = st.session_state.get("main_tab", "Attività Assegnate")
        df_contatti = get_all_users()

        if ruolo == "Amministratore":
            if selected_tab == "Caposquadra":
                render_caposquadra_view(matricola_utente)
                st.stop()
            elif selected_tab == "Sistema":
                render_sistema_view()
                st.stop()

        if selected_tab == "Attività Assegnate":
            if ruolo in ("Tecnico", "Aiutante", "Amministratore"):
                sub_labels = [
                    "Attività di Oggi",
                    "Recupero Attività",
                    "Attività Validate",
                    "Compila Relazione",
                ]
            else:
                sub_labels = [
                    "Attività di Oggi",
                    "Recupero Attività",
                    "Attività Validate",
                ]
            sub_tabs = st.tabs(sub_labels)

            with sub_tabs[0]:
                st.subheader(f"Attività del {today.strftime('%d/%m/%Y')}")
                lista = trova_attivita(
                    matricola_utente, today.day, today.month, today.year, df_contatti
                )
                for t in lista:
                    t["data_attivita"] = today
                disegna_sezione_attivita(lista, "today", ruolo)

            with sub_tabs[1]:
                st.subheader("Recupero Attività")
                attivita = recupera_attivita_non_rendicontate(matricola_utente, df_contatti)
                disegna_sezione_attivita(attivita, "yesterday", ruolo)

            with sub_tabs[2]:
                st.subheader("Attività Validate")
                reports_df = get_validated_intervention_reports(matricola_tecnico=matricola_utente)
                if reports_df.empty:
                    st.info("Nessun report validato.")
                else:
                    for _, r in reports_df.iterrows():
                        d_rif = pd.to_datetime(r["data_riferimento_attivita"]).strftime("%d/%m/%Y")
                        with st.expander(f"PdL `{r['pdl']}` - Intervento del {d_rif}"):
                            st.markdown(f"**Descrizione:** {r['descrizione_attivita']}")
                            st.info(f"**Report:**\n\n{r['testo_report']}")

            if ruolo in ("Tecnico", "Aiutante", "Amministratore") and len(sub_tabs) > 3:
                with sub_tabs[3]:
                    from components.form_handlers import (
                        render_relazione_reperibilita_ui,
                    )

                    render_relazione_reperibilita_ui(matricola_utente, nome_utente_autenticato)

        elif selected_tab == "Gestione Turni":
            render_gestione_turni_tab(matricola_utente, ruolo)
        elif selected_tab == "Programmazione PDL":
            render_programmazione_pdl_page()
        elif selected_tab == "Richieste":
            render_richieste_tab(matricola_utente, ruolo, nome_utente_autenticato)
        elif selected_tab == "Storico":
            from pages.storico import render_storico_tab

            render_storico_tab()
        elif selected_tab == "Impostazioni":
            from pages.impostazioni import render_impostazioni_page

            render_impostazioni_page(matricola_utente)
        elif selected_tab == "Guida":
            render_guida_tab(ruolo)

        st.markdown("</div></div>", unsafe_allow_html=True)

        if st.session_state.get("navigated"):
            script = (
                "<script>setTimeout(() => { "
                "window.parent.document.querySelector("
                "'[data-testid=\"stSidebar\"] > div > div > button').click(); "
                "}, 100);</script>"
            )
            st.components.v1.html(script, height=0)
            st.session_state.navigated = False


if __name__ == "__main__":
    handle_login_and_navigation()
