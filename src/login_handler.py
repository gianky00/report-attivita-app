"""
Modulo per la gestione del flusso di login e autenticazione 2FA.
Estratto da app.py per ridurre la complessità ciclomatica.
"""

import io
from typing import Any

import bcrypt
import qrcode
import streamlit as st

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
from modules.session_manager import load_session, save_session


def _init_session_state() -> None:
    """Inizializza lo stato della sessione se non presente."""
    if "login_state" not in st.session_state:
        st.session_state.update(
            {
                "login_state": "password",
                "authenticated_user": None,
                "ruolo": None,
                "expanded_menu": "Attività",
                "main_tab": "Attività Assegnate",
            }
        )


def _try_session_recovery() -> None:
    """Tenta il recupero della sessione da query params."""
    if not st.session_state.get("authenticated_user"):
        token = st.query_params.get("session_token")
        if token and load_session(token):
            st.session_state.session_token = token
        else:
            st.query_params.clear()


def _handle_password_login() -> None:
    """Gestisce il form di login con password."""
    with st.form("login_form"):
        m_in = st.text_input("Matricola")
        p_in = st.text_input("Password", type="password")
        if st.form_submit_button("Accedi") and m_in and p_in:
            res, data = authenticate_user(m_in, p_in)
            if res == "2FA_REQUIRED":
                log_access_attempt(m_in, "2FA richiesta")
                st.session_state.update({"login_state": "verify_2fa", "temp_user_for_2fa": m_in})
                st.rerun()
            elif res == "SUCCESS":
                log_access_attempt(m_in, "Login riuscito (senza 2FA)")
                token = save_session(m_in, data[1])
                st.session_state.update(
                    {
                        "login_state": "logged_in",
                        "authenticated_user": m_in,
                        "ruolo": data[1],
                        "session_token": token,
                    }
                )
                st.query_params["session_token"] = token
                st.rerun()
            elif res == "FIRST_LOGIN_SETUP":
                _handle_first_login(m_in, data)
            else:
                st.error("Credenziali non valide.")


def _handle_first_login(matricola: str, data: Any) -> None:
    """Gestisce il primo login impostando la password e loggando l'utente (2FA opzionale)."""
    h_p = bcrypt.hashpw(data[2].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    if not get_user_by_matricola(matricola):
        create_user(
            {
                "Matricola": matricola,
                "Nome Cognome": data[0],
                "Ruolo": data[1],
                "PasswordHash": h_p,
            }
        )
    else:
        update_user(matricola, {"PasswordHash": h_p})

    log_access_attempt(matricola, "Primo accesso: password impostata")

    # Invece di forzare il setup 2FA, logghiamo direttamente
    token = save_session(matricola, data[1])
    st.session_state.update(
        {
            "login_state": "logged_in",
            "authenticated_user": matricola,
            "ruolo": data[1],
            "session_token": token,
        }
    )
    st.query_params["session_token"] = token
    st.rerun()


def _handle_2fa_setup() -> None:
    """Gestisce la configurazione iniziale del 2FA."""
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
        if (
            st.form_submit_button("Verifica")
            and verify_2fa_code(secret, code)
            and update_user(m_to, {"2FA_Secret": secret})
        ):
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


def _handle_2fa_verification() -> None:
    """Gestisce la verifica del codice 2FA durante il login."""
    st.subheader("Verifica 2FA")
    m_to = st.session_state.temp_user_for_2fa
    user = get_user_by_matricola(m_to)
    if user is None:
        st.error("Utente non trovato.")
        st.stop()
    with st.form("verify_2fa_login"):
        label = f"Ciao {user['Nome Cognome'].split()[0]}, inserisci il codice"
        code = st.text_input(label)
        if st.form_submit_button("Verifica") and verify_2fa_code(user["2FA_Secret"], code):
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


def handle_login_and_navigation() -> None:
    """Gestisce il flusso di login e il routing dell'applicazione con persistenza sessione."""
    from app import main_app  # import locale per evitare circular import

    _init_session_state()

    # Se non siamo loggati in session_state, proviamo a recuperare dal token URL
    if st.session_state.login_state != "logged_in":
        _try_session_recovery()

    if st.session_state.login_state == "logged_in":
        main_app(st.session_state.authenticated_user, st.session_state.ruolo)
    else:
        st.set_page_config(layout="centered", page_title="Horizon - Technical Operations Platform", page_icon="assets/icons/settings.svg")

        # CSS Enterprise per Login
        st.markdown("""
            <style>
            [data-testid="stAppViewContainer"] {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            }
            .stButton > button {
                width: 100%;
                border-radius: 8px;
                height: 3rem;
                background-color: #4364F7 !important;
                font-weight: bold;
            }
            .stTextInput > div > div > input {
                border-radius: 8px;
            }
            </style>
        """, unsafe_allow_html=True)

        with st.container():
            # Header Professionale con Logo
            st.image("assets/logo.svg", use_container_width=True)

            st.markdown("<p style='text-align: center; color: #64748b; letter-spacing: 2px; margin-bottom: 2rem; font-size: 0.8rem;'>TECHNICAL OPERATIONS ACCESS</p>", unsafe_allow_html=True)

            if st.session_state.login_state == "password":
                _handle_password_login()
            elif st.session_state.login_state == "setup_2fa":
                _handle_2fa_setup()
            elif st.session_state.login_state == "verify_2fa":
                _handle_2fa_verification()
