import io
from typing import Any

import qrcode
import streamlit as st

from constants import ICONS
from modules.auth import (
    change_user_password,
    generate_2fa_secret,
    get_provisioning_uri,
    get_user_by_matricola,
    update_user,
    verify_2fa_code,
)
from modules.utils import render_svg_icon


def render_impostazioni_page(matricola: str) -> None:
    """Renderizza la pagina delle impostazioni utente."""
    st.title("Impostazioni")

    user = get_user_by_matricola(matricola)
    if not user:
        st.error("Dati utente non trovati.")
        return

    tab1, tab2, tab3 = st.tabs(["Profilo", "Sicurezza (2FA)", "Password"])

    with tab1:
        st.subheader("Informazioni Profilo")
        col1, col2 = st.columns(2)
        col1.text_input("Nome Cognome", value=user["Nome Cognome"], disabled=True)
        col1.text_input("Matricola", value=user["Matricola"], disabled=True)
        col2.text_input("Ruolo", value=user["Ruolo"], disabled=True)
        col2.text_input("Email", value=user.get("Email", "N/D"), disabled=True)
        st.info("I dati del profilo possono essere modificati solo dall'Amministratore.")

    with tab2:
        _render_2fa_section(user)

    with tab3:
        _render_password_section(matricola)


def _render_2fa_section(user: dict[str, Any]) -> None:
    """Sezione per la gestione della 2FA."""
    matricola = user["Matricola"]
    st.subheader("Autenticazione a due fattori (2FA)")
    has_2fa = bool(user.get("2FA_Secret"))

    status = f"{render_svg_icon('check', 20)} **ATTIVA**" if has_2fa else f"{render_svg_icon('close', 20)} **NON ATTIVA**"
    st.markdown(f"Stato attuale: {status}")

    if not has_2fa:
        st.write(
            "Attiva la 2FA per proteggere il tuo account con un codice temporaneo (OTP)."
        )
        if st.button("Configura 2FA", type="primary", icon=ICONS["SECURITY"]):
            st.session_state.setup_2fa_mode = True
            st.rerun()
    elif st.button("Disattiva 2FA", type="secondary", icon=ICONS["DELETE"]):
        if update_user(matricola, {"2FA_Secret": None}):
            st.success("2FA disattivata con successo.")
            st.rerun()

    if st.session_state.get("setup_2fa_mode"):
        st.divider()
        if "temp_2fa_secret" not in st.session_state:
            st.session_state.temp_2fa_secret = generate_2fa_secret()

        secret = st.session_state.temp_2fa_secret
        uri = get_provisioning_uri(user["Nome Cognome"], secret)

        c1, c2 = st.columns(2)
        with c1:
            buf = io.BytesIO()
            qrcode.make(uri).save(buf, format="PNG")
            st.image(buf.getvalue(), caption="Scansiona con Google Authenticator o simili")
        with c2:
            st.code(secret, language=None)
            with st.form("confirm_2fa_setup_settings"):
                code = st.text_input("Codice di conferma (6 cifre)")
                if (
                    st.form_submit_button("Conferma e Attiva")
                    and verify_2fa_code(secret, code)
                    and update_user(matricola, {"2FA_Secret": secret})
                ):
                    st.success("2FA attivata!")
                    if "temp_2fa_secret" in st.session_state:
                        del st.session_state.temp_2fa_secret
                    st.session_state.setup_2fa_mode = False
                    st.rerun()
                elif st.form_submit_button("Conferma e Attiva"):
                    st.error("Codice non valido o errore durante l'attivazione.")

        if st.button("Annulla Setup"):
            st.session_state.setup_2fa_mode = False
            st.rerun()


def _render_password_section(matricola: str) -> None:
    """Sezione per il cambio password."""
    st.subheader("Cambio Password")
    with st.form("change_password_form"):
        old_p = st.text_input("Vecchia Password", type="password")
        new_p = st.text_input("Nuova Password", type="password")
        confirm_p = st.text_input("Conferma Nuova Password", type="password")

        if st.form_submit_button("Aggiorna Password", icon=ICONS["SAVE"]):
            if not old_p or not new_p:
                st.error("Tutti i campi sono obbligatori.")
            elif new_p != confirm_p:
                st.error("Le nuove password non coincidono.")
            elif len(new_p) < 6:
                st.error("La nuova password deve essere di almeno 6 caratteri.")
            else:
                success, msg = change_user_password(matricola, old_p, new_p)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
