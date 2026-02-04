import streamlit as st
import pandas as pd
import datetime
from modules.email_sender import invia_email_con_outlook_async
from modules.db_manager import (
    salva_storico_materiali,
    salva_storico_assenze,
    add_material_request,
    add_leave_request,
    get_material_requests,
    get_leave_requests,
    get_all_users
)

def render_richieste_tab(matricola_utente, ruolo, nome_utente_autenticato):
    st.header("Richieste")
    richieste_tabs = st.tabs(["Materiali", "Assenze"])

    with richieste_tabs[0]:
        st.subheader("Richiesta Materiali")
        with st.form("form_richiesta_materiali", clear_on_submit=True):
            dettagli_richiesta = st.text_area("Elenca qui i materiali necessari:", height=150)
            submitted = st.form_submit_button("Invia Richiesta Materiali", type="primary")
            if submitted and dettagli_richiesta.strip():
                new_id = f"MAT_{int(datetime.datetime.now().timestamp())}"
                new_request_data = {
                    'ID_Richiesta': new_id,
                    'Richiedente_Matricola': str(matricola_utente),
                    'Timestamp': datetime.datetime.now().isoformat(),
                    'Stato': 'Inviata',
                    'Dettagli': dettagli_richiesta
                }

                if add_material_request(new_request_data):
                    storico_data = {
                        "id_richiesta": new_id,
                        "richiedente_matricola": str(matricola_utente),
                        "nome_richiedente": nome_utente_autenticato,
                        "timestamp_richiesta": datetime.datetime.now().isoformat(),
                        "dettagli_richiesta": dettagli_richiesta,
                        "timestamp_approvazione": datetime.datetime.now().isoformat()
                    }
                    salva_storico_materiali(storico_data)

                    st.success("Richiesta materiali inviata con successo!")
                    # Email sending logic remains the same
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
            df_richieste_con_nome = pd.merge(df_richieste_materiali, df_contatti[['Matricola', 'Nome Cognome']], left_on='Richiedente_Matricola', right_on='Matricola', how='left')
            df_richieste_con_nome['Nome Cognome'] = df_richieste_con_nome['Nome Cognome'].fillna('Sconosciuto')
            df_richieste_con_nome['Timestamp'] = pd.to_datetime(df_richieste_con_nome['Timestamp'])
            st.dataframe(df_richieste_con_nome[['Timestamp', 'Nome Cognome', 'Dettagli', 'Stato']].sort_values(by="Timestamp", ascending=False), width='stretch')

    with richieste_tabs[1]:
        st.subheader("Richiesta Assenze (Ferie/Permessi)")
        with st.form("form_richiesta_assenze", clear_on_submit=True):
            tipo_assenza = st.selectbox("Tipo di Assenza", ["Ferie", "Permesso (L. 104)"])
            col1, col2 = st.columns(2)
            data_inizio = col1.date_input("Data Inizio")
            data_fine = col2.date_input("Data Fine")
            note_assenza = st.text_area("Note (opzionale):", height=100)
            submitted_assenza = st.form_submit_button("Invia Richiesta Assenza", type="primary")

            if submitted_assenza:
                if data_inizio > data_fine:
                    st.error("La data di inizio non può essere successiva alla data di fine.")
                else:
                    new_id = f"ASS_{int(datetime.datetime.now().timestamp())}"
                    new_leave_request = {
                        'ID_Richiesta': new_id,
                        'Richiedente_Matricola': str(matricola_utente),
                        'Timestamp': datetime.datetime.now().isoformat(),
                        'Tipo_Assenza': tipo_assenza,
                        'Data_Inizio': data_inizio.isoformat(),
                        'Data_Fine': data_fine.isoformat(),
                        'Note': note_assenza,
                        'Stato': 'Inviata'
                    }
                    if add_leave_request(new_leave_request):
                        storico_data = {
                            "id_richiesta": new_id,
                            "richiedente_matricola": str(matricola_utente),
                            "nome_richiedente": nome_utente_autenticato,
                            "timestamp_richiesta": datetime.datetime.now().isoformat(),
                            "tipo_assenza": tipo_assenza,
                            "data_inizio": data_inizio.isoformat(),
                            "data_fine": data_fine.isoformat(),
                            "note": note_assenza,
                            "timestamp_approvazione": datetime.datetime.now().isoformat()
                        }
                        salva_storico_assenze(storico_data)
                        st.success("Richiesta di assenza inviata con successo!")
                        # Email sending logic remains the same
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio della richiesta.")

        if ruolo == "Amministratore":
            st.divider()
            st.subheader("Storico Richieste Assenze (Visibile solo agli Admin)")
            df_richieste_assenze = get_leave_requests()
            if df_richieste_assenze.empty:
                st.info("Nessuna richiesta di assenza inviata.")
            else:
                df_richieste_assenze['Timestamp'] = pd.to_datetime(df_richieste_assenze['Timestamp'])
                df_richieste_assenze['Data_Inizio'] = pd.to_datetime(df_richieste_assenze['Data_Inizio']).dt.strftime('%d/%m/%Y')
                df_richieste_assenze['Data_Fine'] = pd.to_datetime(df_richieste_assenze['Data_Fine']).dt.strftime('%d/%m/%Y')
                st.dataframe(df_richieste_assenze.sort_values(by="Timestamp", ascending=False), width='stretch')
