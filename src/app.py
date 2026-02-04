"""
Modulo principale del Gestionale Tecnici.
Gestisce l'interfaccia Streamlit, l'autenticazione 2FA e la logica principale.
"""

import datetime
import io

import bcrypt
import pandas as pd
import qrcode
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

from components.form_handlers import render_debriefing_ui, render_edit_shift_form
from components.ui_components import (
    disegna_sezione_attivita,
    render_sidebar,
)
from modules.auth import (
    authenticate_user,
    create_user,
    generate_2fa_secret,
    get_provisioning_uri,
    get_user_by_matricola,
    log_access_attempt,
    update_user,
    verify_2fa_code,
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
from modules.session_manager import load_session, save_session
from modules.shift_management import sync_oncall_shifts
from pages.admin import render_caposquadra_view, render_sistema_view
from pages.gestione_turni import render_gestione_turni_tab
from pages.guida import render_guida_tab
from pages.richieste import render_richieste_tab

# --- ESEGUI CHECK LICENZA ALL'AVVIO ---
check_pyarmor_license()


@st.cache_resource
def autorizza_google():
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
        client.login()
    return client


def recupera_attivita_non_rendicontate(matricola_utente, df_contatti):
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


def main_app(matricola_utente, ruolo):
    """
    Gestisce l'interfaccia utente principale dopo l'autenticazione.
    Include sidebar, notifiche, navigazione tra i tab e rendering dei moduli.
    """
    st.set_page_config(
        layout="wide", page_title="Gestionale", initial_sidebar_state="collapsed"
    )

    def load_css(file_name):
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
        if knowledge_core:
            task_info = st.session_state.debriefing_task
            data_rif = task_info.get("data_attivita", datetime.date.today())
            render_debriefing_ui(knowledge_core, matricola_utente, data_rif)
    else:
        render_sidebar(matricola_utente, nome_utente_autenticato, ruolo)

        st.title(st.session_state.main_tab)
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
            if ruolo in ["Tecnico", "Amministratore"]:
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
                attivita = recupera_attivita_non_rendicontate(
                    matricola_utente, df_contatti
                )
                disegna_sezione_attivita(attivita, "yesterday", ruolo)

            with sub_tabs[2]:
                st.subheader("Attività Validate")
                reports_df = get_validated_intervention_reports(
                    matricola_tecnico=str(matricola_utente)
                )
                if reports_df.empty:
                    st.info("Nessun report validato.")
                else:
                    for _, r in reports_df.iterrows():
                        d_rif = pd.to_datetime(r["data_riferimento_attivita"]).strftime(
                            "%d/%m/%Y"
                        )
                        with st.expander(f"PdL `{r['pdl']}` - Intervento del {d_rif}"):
                            st.markdown(f"**Descrizione:** {r['descrizione_attivita']}")
                            st.info(f"**Report:**\n\n{r['testo_report']}")

            if ruolo in ["Tecnico", "Amministratore"] and len(sub_tabs) > 3:
                with sub_tabs[3]:
                    from components.form_handlers import (
                        render_relazione_reperibilita_ui,
                    )

                    render_relazione_reperibilita_ui(
                        matricola_utente, nome_utente_autenticato
                    )

        elif selected_tab == "📅 Gestione Turni":
            render_gestione_turni_tab(matricola_utente, ruolo)
        elif selected_tab == "Richieste":
            render_richieste_tab(matricola_utente, ruolo, nome_utente_autenticato)
        elif selected_tab == "Storico":
            from pages.storico import render_storico_tab
            render_storico_tab()
        elif selected_tab == "❓ Guida":
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


# --- GESTIONE LOGIN E SESSIONE ---

if "login_state" not in st.session_state:
    st.session_state.update({
        "login_state": "password",
        "authenticated_user": None,
        "ruolo": None,
        "expanded_menu": "Attività",
        "main_tab": "Attività Assegnate"
    })

if not st.session_state.get("authenticated_user"):
    token = st.query_params.get("session_token")
    if token and load_session(token):
        st.session_state.session_token = token
    else:
        st.query_params.clear()

if st.session_state.login_state == "logged_in":
    main_app(st.session_state.authenticated_user, st.session_state.ruolo)
else:
    st.set_page_config(layout="centered", page_title="Login")
    st.title("Accesso Area Gestionale")

    if st.session_state.login_state == "password":
        with st.form("login_form"):
            m_in = st.text_input("Matricola")
            p_in = st.text_input("Password", type="password")
            if st.form_submit_button("Accedi") and m_in and p_in:
                res, data = authenticate_user(m_in, p_in)
                if res == "2FA_REQUIRED":
                    log_access_attempt(m_in, "2FA richiesta")
                    st.session_state.update({
                        "login_state": "verify_2fa", "temp_user_for_2fa": m_in
                    })
                    st.rerun()
                elif res == "2FA_SETUP_REQUIRED":
                    log_access_attempt(m_in, "Setup 2FA richiesto")
                    st.session_state.update(
                        {
                            "login_state": "setup_2fa",
                            "ruolo": data[1],
                            "temp_user_for_2fa": m_in,
                        }
                    )
                    st.rerun()
                elif res == "FIRST_LOGIN_SETUP":
                    h_p = bcrypt.hashpw(
                        data[2].encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8")
                    if not get_user_by_matricola(m_in):
                        create_user(
                            {
                                "Matricola": str(m_in),
                                "Nome Cognome": data[0],
                                "Ruolo": data[1],
                                "PasswordHash": h_p,
                            }
                        )
                    else:
                        update_user(m_in, {"PasswordHash": h_p})
                    st.session_state.update(
                        {
                            "login_state": "setup_2fa",
                            "temp_user_for_2fa": m_in,
                            "ruolo": data[1],
                        }
                    )
                    st.rerun()
                else:
                    st.error("Credenziali non valide.")

    elif st.session_state.login_state == "setup_2fa":
        st.subheader("Configurazione 2FA")
        m_to = st.session_state.temp_user_for_2fa
        u_row = get_user_by_matricola(m_to)
        u_name_disp = u_row["Nome Cognome"] if u_row else "Utente"

        if "2fa_secret" not in st.session_state:
            st.session_state["2fa_secret"] = generate_2fa_secret()
        secret = st.session_state["2fa_secret"]
        uri = get_provisioning_uri(u_name_disp, secret)

        buf = io.BytesIO()
        qrcode.make(uri).save(buf, format="PNG")
        st.image(buf.getvalue())
        st.code(secret)

        with st.form("verify_2fa_setup"):
            code = st.text_input("Codice a 6 cifre")
            if st.form_submit_button("Verifica") and verify_2fa_code(secret, code):
                if update_user(m_to, {"2FA_Secret": secret}):
                    token = save_session(m_to, st.session_state.ruolo)
                    st.session_state.update(
                        {
                            "login_state": "logged_in",
                            "authenticated_user": m_to,
                            "session_token": token,
                        }
                    )
                    st.query_params["session_token"] = token
                    st.rerun()

    elif st.session_state.login_state == "verify_2fa":
        st.subheader("Verifica 2FA")
        m_to = st.session_state.temp_user_for_2fa
        user = get_user_by_matricola(m_to)
        with st.form("verify_2fa_login"):
            label = f"Ciao {user['Nome Cognome'].split()[0]}, inserisci il codice"
            code = st.text_input(label)
            if st.form_submit_button("Verifica") and verify_2fa_code(
                user["2FA_Secret"], code
            ):
                token = save_session(m_to, user["Ruolo"])
                st.session_state.update(
                    {
                        "login_state": "logged_in",
                        "authenticated_user": m_to,
                        "ruolo": user["Ruolo"],
                        "session_token": token,
                    }
                )
                st.query_params["session_token"] = token
                st.rerun()
