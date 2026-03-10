import datetime

import pandas as pd
import streamlit as st

from constants import ICONS
from modules.db_manager import (
    add_material_request,
    get_all_users,
    get_material_requests,
    salva_storico_materiali,
)


def render_richieste_tab(matricola_utente: str, ruolo: str, nome_utente_autenticato: str) -> None:
    """Renderizza l'interfaccia per l'invio e la visualizzazione di richieste materiali."""
    richieste_tabs = st.tabs([f"{ICONS['MATERIAL']} Materiali"])

    with richieste_tabs[0]:
        st.subheader("Richiesta Materiali")
        with st.form("form_richiesta_materiali", clear_on_submit=True):
            dettagli_richiesta = st.text_area("Elenca qui i materiali necessari:", height=150)
            submitted = st.form_submit_button("Invia Richiesta Materiali", type="primary")
            if submitted and dettagli_richiesta.strip():
                now_iso = datetime.datetime.now().isoformat()
                new_id = f"MAT_{int(datetime.datetime.now().timestamp())}"

                parts = nome_utente_autenticato.split(" ", 1)
                nome = parts[0]
                cognome = parts[1] if len(parts) > 1 else ""

                new_request_data = {
                    "ID_Richiesta": new_id,
                    "Richiedente_Matricola": matricola_utente,
                    "richiedente_nome": nome,
                    "richiedente_cognome": cognome,
                    "Timestamp": now_iso,
                    "Stato": "Inviata",
                    "Dettagli": dettagli_richiesta,
                }

                if add_material_request(new_request_data):
                    storico_data = {
                        "id_richiesta": new_id,
                        "richiedente_matricola": matricola_utente,
                        "nome_richiedente": nome_utente_autenticato,
                        "richiedente_nome": nome,
                        "richiedente_cognome": cognome,
                        "timestamp_richiesta": now_iso,
                        "dettagli_richiesta": dettagli_richiesta,
                        "timestamp_approvazione": now_iso,
                    }
                    salva_storico_materiali(storico_data)

                    st.success("Richiesta materiali inviata con successo!")
                    st.rerun()
                else:
                    st.error("Errore durante il salvataggio della richiesta.")
            elif submitted:
                st.warning("Il campo dei materiali non può essere vuoto.")

        st.divider()
        st.subheader("Storico Richieste Materiali")
        df_richieste_materiali = get_material_requests()
        if df_richieste_materiali.empty:
            st.info("Nessuna richiesta di materiali inviata.")
        else:
            df_contatti = get_all_users()
            df_richieste_con_nome = pd.merge(
                df_richieste_materiali,
                df_contatti[["Matricola", "Nome Cognome"]],
                left_on="Richiedente_Matricola",
                right_on="Matricola",
                how="left",
            )
            df_richieste_con_nome["Nome Cognome"] = df_richieste_con_nome["Nome Cognome"].fillna(
                "Sconosciuto"
            )
            df_richieste_con_nome["Timestamp"] = pd.to_datetime(
                df_richieste_con_nome["Timestamp"]
            ).dt.strftime("%d/%m/%Y %H:%M")
            st.dataframe(
                df_richieste_con_nome[
                    ["Timestamp", "Nome Cognome", "Dettagli", "Stato"]
                ].sort_values(by="Timestamp", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
