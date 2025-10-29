import streamlit as st
import pandas as pd
import datetime
from modules.data_manager import salva_gestionale_async
from modules.email_sender import invia_email_con_outlook_async
from modules.db_manager import salva_storico_materiali, salva_storico_assenze

def render_richieste_tab(gestionale_data, matricola_utente, ruolo, nome_utente_autenticato):
    st.header("Richieste")
    richieste_tabs = st.tabs(["Materiali", "Assenze"])
    with richieste_tabs[0]:
        st.subheader("Richiesta Materiali")
        with st.form("form_richiesta_materiali", clear_on_submit=True):
            dettagli_richiesta = st.text_area("Elenca qui i materiali necessari:", height=150)
            submitted = st.form_submit_button("Invia Richiesta Materiali", type="primary")
            if submitted:
                if dettagli_richiesta.strip():
                    new_id = f"MAT_{int(datetime.datetime.now().timestamp())}"
                    df_materiali = gestionale_data.get('richieste_materiali', pd.DataFrame())
                    nuova_richiesta_data = {'ID_Richiesta': new_id, 'Richiedente_Matricola': str(matricola_utente), 'Timestamp': datetime.datetime.now(), 'Stato': 'Inviata', 'Dettagli': dettagli_richiesta}
                    if not df_materiali.columns.empty:
                        nuova_richiesta_df = pd.DataFrame([nuova_richiesta_data], columns=df_materiali.columns)
                    else:
                        nuova_richiesta_df = pd.DataFrame([nuova_richiesta_data])
                    gestionale_data['richieste_materiali'] = pd.concat([df_materiali, nuova_richiesta_df], ignore_index=True)
                    if salva_gestionale_async(gestionale_data):
                        # Salva nello storico immutabile
                        storico_data = {
                            "id_richiesta": new_id,
                            "richiedente_matricola": str(matricola_utente),
                            "nome_richiedente": nome_utente_autenticato,
                            "timestamp_richiesta": datetime.datetime.now().isoformat(),
                            "dettagli_richiesta": dettagli_richiesta,
                            "timestamp_approvazione": datetime.datetime.now().isoformat() # Immediata approvazione
                        }
                        salva_storico_materiali(storico_data)

                        st.success("Richiesta materiali inviata con successo!")
                        titolo_email = f"Nuova Richiesta Materiali da {nome_utente_autenticato}"
                        html_body = f"""
                        <html><head><style>body {{ font-family: Calibri, sans-serif; }}</style></head><body>
                        <h3>Nuova Richiesta Materiali</h3>
                        <p><strong>Richiedente:</strong> {nome_utente_autenticato} ({matricola_utente})</p>
                        <p><strong>Data e Ora:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        <hr>
                        <h4>Materiali Richiesti:</h4>
                        <p>{dettagli_richiesta.replace('\\n', '<br>')}</p>
                        <br><hr>
                        <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
                        </body></html>
                        """
                        invia_email_con_outlook_async(titolo_email, html_body)
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio della richiesta.")
                else:
                    st.warning("Il campo dei materiali non può essere vuoto.")
        st.divider()
        st.subheader("Storico Richieste Materiali")
        df_richieste_materiali = gestionale_data.get('richieste_materiali', pd.DataFrame())
        if df_richieste_materiali.empty:
            st.info("Nessuna richiesta di materiali inviata.")
        else:
            df_contatti = gestionale_data.get('contatti', pd.DataFrame())
            df_richieste_con_nome = pd.merge(df_richieste_materiali, df_contatti[['Matricola', 'Nome Cognome']], left_on='Richiedente_Matricola', right_on='Matricola', how='left')
            df_richieste_con_nome['Nome Cognome'] = df_richieste_con_nome['Nome Cognome'].fillna('Sconosciuto')
            df_richieste_con_nome['Timestamp'] = pd.to_datetime(df_richieste_con_nome['Timestamp'])
            display_cols = ['Timestamp', 'Nome Cognome', 'Dettagli', 'Stato']
            final_cols = [col for col in display_cols if col in df_richieste_con_nome.columns]
            st.dataframe(df_richieste_con_nome[final_cols].sort_values(by="Timestamp", ascending=False), width='stretch')

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
                if data_inizio and data_fine:
                    if data_inizio > data_fine:
                        st.error("La data di inizio non può essere successiva alla data di fine.")
                    else:
                        new_id = f"ASS_{int(datetime.datetime.now().timestamp())}"
                        nuova_richiesta_assenza = pd.DataFrame([{{'ID_Richiesta': new_id, 'Richiedente_Matricola': str(matricola_utente), 'Timestamp': datetime.datetime.now(), 'Tipo_Assenza': tipo_assenza, 'Data_Inizio': pd.to_datetime(data_inizio), 'Data_Fine': pd.to_datetime(data_fine), 'Note': note_assenza, 'Stato': 'Inviata'}}])
                        df_assenze = gestionale_data.get('richieste_assenze', pd.DataFrame())
                        gestionale_data['richieste_assenze'] = pd.concat([df_assenze, nuova_richiesta_assenza], ignore_index=True)
                        if salva_gestionale_async(gestionale_data):
                            # Salva nello storico immutabile
                            storico_data = {
                                "id_richiesta": new_id,
                                "richiedente_matricola": str(matricola_utente),
                                "nome_richiedente": nome_utente_autenticato,
                                "timestamp_richiesta": datetime.datetime.now().isoformat(),
                                "tipo_assenza": tipo_assenza,
                                "data_inizio": data_inizio.isoformat(),
                                "data_fine": data_fine.isoformat(),
                                "note": note_assenza,
                                "timestamp_approvazione": datetime.datetime.now().isoformat() # Immediata approvazione
                            }
                            salva_storico_assenze(storico_data)

                            st.success("Richiesta di assenza inviata con successo!")
                            titolo_email = f"Nuova Richiesta di Assenza da {nome_utente_autenticato}"
                            html_body = f"""
                            <html><head><style>body {{ font-family: Calibri, sans-serif; }}</style></head><body>
                            <h3>Nuova Richiesta di Assenza</h3>
                            <p><strong>Richiedente:</strong> {nome_utente_autenticato} ({matricola_utente})</p>
                            <p><strong>Tipo:</strong> {tipo_assenza}</p>
                            <p><strong>Periodo:</strong> dal {data_inizio.strftime('%d/%m/%Y')} al {data_fine.strftime('%d/%m/%Y')}</p>
                            <hr>
                            <h4>Note:</h4>
                            <p>{note_assenza.replace('\\n', '<br>') if note_assenza else 'Nessuna nota.'}</p>
                            <br><hr>
                            <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
                            </body></html>
                            """
                            invia_email_con_outlook_async(titolo_email, html_body)
                            st.rerun()
                        else:
                            st.error("Errore durante il salvataggio della richiesta.")
                else:
                    st.warning("Le date di inizio e fine sono obbligatorie.")
        if ruolo == "Amministratore":
            st.divider()
            st.subheader("Storico Richieste Assenze (Visibile solo agli Admin)")
            df_richieste_assenze = gestionale_data.get('richieste_assenze', pd.DataFrame())
            if df_richieste_assenze.empty:
                st.info("Nessuna richiesta di assenza inviata.")
            else:
                df_richieste_assenze['Timestamp'] = pd.to_datetime(df_richieste_assenze['Timestamp'])
                df_richieste_assenze['Data_Inizio'] = pd.to_datetime(df_richieste_assenze['Data_Inizio']).dt.strftime('%d/%m/%Y')
                df_richieste_assenze['Data_Fine'] = pd.to_datetime(df_richieste_assenze['Data_Fine']).dt.strftime('%d/%m/%Y')
                st.dataframe(df_richieste_assenze.sort_values(by="Timestamp", ascending=False), width='stretch')
