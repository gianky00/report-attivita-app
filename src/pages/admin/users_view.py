"""
Modulo per la gestione amministrativa degli account tecnici e amministratori.
Include funzionalità di creazione, modifica, eliminazione e reset credenziali/2FA.
"""

import pandas as pd
import streamlit as st

from src.modules.auth import (
    create_user,
    delete_user,
    reset_user_2fa,
    reset_user_password,
    update_user,
)
from src.modules.db_manager import get_all_users


def _render_user_edit_form(user_to_edit):
    """Sotto-funzione per il form di modifica utente."""
    with st.form(key="edit_user_form"):
        st.subheader(f"Modifica Utente: {user_to_edit['Nome Cognome']}")
        new_nome_cognome = st.text_input(
            "Nome Cognome", value=user_to_edit["Nome Cognome"]
        )
        new_matricola = st.text_input("Matricola", value=user_to_edit["Matricola"])
        ruoli_disponibili = ["Tecnico", "Aiutante", "Amministratore"]
        try:
            current_role_index = ruoli_disponibili.index(user_to_edit["Ruolo"])
        except ValueError:
            current_role_index = 0
        new_role = st.selectbox(
            "Nuovo Ruolo", options=ruoli_disponibili, index=current_role_index
        )

        col1, col2 = st.columns(2)
        if col1.form_submit_button("Salva Modifiche", type="primary"):
            update_data = {
                "Nome Cognome": new_nome_cognome,
                "Matricola": new_matricola,
                "Ruolo": new_role,
            }
            if update_user(st.session_state.editing_user_matricola, update_data):
                st.success("Utente aggiornato con successo.")
                st.session_state.editing_user_matricola = None
                st.rerun()
            else:
                st.error("Errore durante il salvataggio delle modifiche.")
        if col2.form_submit_button("Annulla"):
            st.session_state.editing_user_matricola = None
            st.rerun()


def _render_user_card(user):
    """Sotto-funzione per renderizzare la card di un singolo utente nell'elenco."""
    user_name = user["Nome Cognome"]
    user_matricola = user["Matricola"]

    def start_edit():
        st.session_state.editing_user_matricola = user_matricola
        st.session_state.deleting_user_matricola = None

    def start_delete():
        st.session_state.deleting_user_matricola = user_matricola
        st.session_state.editing_user_matricola = None

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            is_placeholder = pd.isna(user.get("PasswordHash"))
            status = "Da Attivare" if is_placeholder else "Attivo"
            st.markdown(
                f"**{user_name}** (`{user_matricola}`) - *{user['Ruolo']}* - Stato: **{status}**"
            )
        with col2:
            st.button(
                "✏️ Modifica",
                key=f"edit_{user_matricola}",
                on_click=start_edit,
            )

        b1, b2, b3 = st.columns(3)
        b1.button(
            "🔑 Resetta Password",
            key=f"reset_pwd_{user_matricola}",
            on_click=lambda m=user_matricola, n=user_name: (
                reset_user_password(m) and st.success(f"Password per {n} resettata.")
            ),
        )
        b2.button(
            "📱 Resetta 2FA",
            key=f"reset_2fa_{user_matricola}",
            on_click=lambda m=user_matricola, n=user_name: (
                reset_user_2fa(m) and st.success(f"2FA per {n} resettata.")
            ),
            disabled=pd.isna(user.get("2FA_Secret")),
        )

        if st.session_state.deleting_user_matricola == user_matricola:
            st.warning(
                f"Sei sicuro di voler eliminare l'utente **{user_name}**? Questa azione è irreversibile."
            )
            c1, c2 = st.columns(2)
            if c1.button(
                "✅ Conferma Eliminazione",
                key=f"confirm_delete_{user_matricola}",
                type="primary",
            ):
                if delete_user(user_matricola):
                    st.success(f"Utente {user_name} eliminato.")
                    st.session_state.deleting_user_matricola = None
                    st.rerun()
                else:
                    st.error("Errore durante l'eliminazione.")
            if c2.button("❌ Annulla", key=f"cancel_delete_{user_matricola}"):
                st.session_state.deleting_user_matricola = None
                st.rerun()
        else:
            b3.button(
                "❌ Elimina Utente",
                key=f"delete_{user_matricola}",
                on_click=start_delete,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def _render_new_user_expander(df_contatti):
    """Sotto-funzione per il form di creazione nuovo utente."""
    with st.expander("➕ Crea Nuovo Utente"):
        with st.form("new_user_form", clear_on_submit=True):
            st.subheader("Dati Nuovo Utente")
            c1, c2 = st.columns(2)
            new_nome = c1.text_input("Nome*")
            new_cognome = c2.text_input("Cognome*")
            c3, c4 = st.columns(2)
            new_matricola = c3.text_input("Matricola*")
            new_ruolo = c4.selectbox("Ruolo", ["Tecnico", "Aiutante", "Amministratore"])

            if st.form_submit_button("Crea Utente"):
                if new_nome and new_cognome and new_matricola:
                    if not df_contatti[
                        df_contatti["Matricola"].astype(str) == str(new_matricola)
                    ].empty:
                        st.error(f"Errore: La matricola '{new_matricola}' esiste già.")
                    else:
                        nome_completo = f"{new_nome.strip()} {new_cognome.strip()}"
                        new_user_data = {
                            "Matricola": str(new_matricola),
                            "Nome Cognome": nome_completo,
                            "Ruolo": new_ruolo,
                            "PasswordHash": None,
                            "2FA_Secret": None,
                        }
                        if create_user(new_user_data):
                            st.success(
                                f"Utente '{nome_completo}' creato. Dovrà impostare la password al primo accesso."
                            )
                            st.rerun()
                        else:
                            st.error("Errore durante la creazione dell'utente.")
                else:
                    st.warning("Nome, Cognome e Matricola sono obbligatori.")


def render_gestione_account():
    """Renderizza l'interfaccia di gestione degli account utenti."""
    st.subheader("Gestione Account Utente")
    df_contatti = get_all_users()

    if "editing_user_matricola" not in st.session_state:
        st.session_state.editing_user_matricola = None
    if "deleting_user_matricola" not in st.session_state:
        st.session_state.deleting_user_matricola = None

    if st.session_state.editing_user_matricola:
        user_rows = df_contatti[
            df_contatti["Matricola"] == st.session_state.editing_user_matricola
        ]
        if not user_rows.empty:
            _render_user_edit_form(user_rows.iloc[0])

    st.subheader("Elenco Utenti")
    search_term = st.text_input(
        "Cerca per nome o matricola...", key="user_search_admin"
    )
    df_filtrati = df_contatti
    if search_term:
        df_filtrati = df_contatti[
            df_contatti["Nome Cognome"].str.contains(search_term, case=False, na=False)
            | df_contatti["Matricola"]
            .astype(str)
            .str.contains(search_term, case=False, na=False)
        ]

    for _, user in df_filtrati.iterrows():
        _render_user_card(user)

    st.divider()
    _render_new_user_expander(df_contatti)
