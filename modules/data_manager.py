import streamlit as st
import pandas as pd
import os
import json
import datetime
import re
import threading
import openpyxl

import config
from modules.email_sender import invia_email_con_outlook_async
from config import get_attivita_programmate_path, get_storico_db_path, get_gestionale_path

@st.cache_data
def carica_knowledge_core():
    try:
        with open(config.PATH_KNOWLEDGE_CORE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Errore critico: File '{config.PATH_KNOWLEDGE_CORE}' non trovato.")
        return None
    except json.JSONDecodeError:
        st.error(f"Errore critico: Il file '{config.PATH_KNOWLEDGE_CORE}' non è un JSON valido.")
        return None

#@st.cache_data
def carica_gestionale():
    with config.EXCEL_LOCK:
        try:
            xls = pd.ExcelFile(config.PATH_GESTIONALE)
            data = {
                'contatti': pd.read_excel(xls, sheet_name='Contatti'),
                'turni': pd.read_excel(xls, sheet_name='TurniDisponibili'),
                'prenotazioni': pd.read_excel(xls, sheet_name='Prenotazioni'),
                'sostituzioni': pd.read_excel(xls, sheet_name='SostituzioniPendenti')
            }

            # Handle 'Tipo' column in 'turni' DataFrame for backward compatibility
            if 'Tipo' not in data['turni'].columns:
                data['turni']['Tipo'] = 'Assistenza'
            data['turni']['Tipo'].fillna('Assistenza', inplace=True)

            required_notification_cols = ['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione']

            if 'Notifiche' in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name='Notifiche')
                # Sanitize column names to remove leading/trailing whitespace
                df.columns = df.columns.str.strip()

                # Check for missing columns and add them if necessary
                for col in required_notification_cols:
                    if col not in df.columns:
                        df[col] = pd.NA
                data['notifiche'] = df
            else:
                data['notifiche'] = pd.DataFrame(columns=required_notification_cols)

            # Aggiunto per la bacheca turni
            required_bacheca_cols = ['ID_Bacheca', 'ID_Turno', 'Tecnico_Originale', 'Ruolo_Originale', 'Timestamp_Pubblicazione', 'Stato', 'Tecnico_Subentrante', 'Timestamp_Assegnazione']
            if 'TurniInBacheca' in xls.sheet_names:
                df_bacheca = pd.read_excel(xls, sheet_name='TurniInBacheca')
                df_bacheca.columns = df_bacheca.columns.str.strip()
                for col in required_bacheca_cols:
                    if col not in df_bacheca.columns:
                        df_bacheca[col] = pd.NA
                data['bacheca'] = df_bacheca
            else:
                data['bacheca'] = pd.DataFrame(columns=required_bacheca_cols)


            return data
        except Exception as e:
            st.error(f"Errore critico nel caricamento del file Gestionale_Tecnici.xlsx: {e}")
            return None

def _save_to_excel_backend(data):
    """Questa funzione è sicura per essere eseguita in un thread separato."""
    with config.EXCEL_LOCK:
        try:
            with pd.ExcelWriter(config.PATH_GESTIONALE, engine='openpyxl') as writer:
                data['contatti'].to_excel(writer, sheet_name='Contatti', index=False)
                data['turni'].to_excel(writer, sheet_name='TurniDisponibili', index=False)
                data['prenotazioni'].to_excel(writer, sheet_name='Prenotazioni', index=False)
                data['sostituzioni'].to_excel(writer, sheet_name='SostituzioniPendenti', index=False)
                if 'notifiche' in data:
                    data['notifiche'].to_excel(writer, sheet_name='Notifiche', index=False)
                if 'bacheca' in data:
                    data['bacheca'].to_excel(writer, sheet_name='TurniInBacheca', index=False)
            return True
        except Exception as e:
            print(f"ERRORE CRITICO NEL THREAD DI SALVATAGGIO: {e}")
            return False

def salva_gestionale_async(data):
    """Funzione da chiamare dall'app Streamlit per un salvataggio non bloccante."""
    st.cache_data.clear()
    data_copy = {k: v.copy() for k, v in data.items()}
    thread = threading.Thread(target=_save_to_excel_backend, args=(data_copy,))
    thread.start()
    return True # Ritorna immediatamente

def carica_archivio_completo():
    """
    Carica l'archivio storico completo dal file Excel specificato in configurazione.
    Include una gestione degli errori robusta per notificare problemi all'utente.
    """
    storico_path = config.PATH_STORICO_DB
    try:
        # Usiamo ExcelFile per ispezionare prima di leggere
        xls = pd.ExcelFile(storico_path)
        sheet_name = xls.sheet_names[0]
        st.info(f"Tentativo di caricamento dell'archivio dal foglio: '{sheet_name}'")

        df = pd.read_excel(xls, sheet_name=sheet_name)

        # Verifica delle colonne necessarie
        required_cols = ['Data_Riferimento', 'Data_Compilazione', 'PdL', 'Tecnico']
        if not all(col in df.columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in df.columns]
            st.error(f"Errore nell'archivio: Colonne richieste mancanti nel foglio '{sheet_name}'. Colonne mancanti: {missing_cols}")
            return pd.DataFrame()

        df['Data_Riferimento_dt'] = pd.to_datetime(df['Data_Riferimento'], errors='coerce')
        df.dropna(subset=['Data_Riferimento_dt'], inplace=True)
        df.sort_values(by='Data_Compilazione', ascending=True, inplace=True)
        df.drop_duplicates(subset=['PdL', 'Tecnico', 'Data_Riferimento'], keep='last', inplace=True)
        return df

    except FileNotFoundError:
        st.error(f"File archivio non trovato al percorso: {storico_path}. Verificare il percorso in `secrets.toml` e la connessione di rete.")
        return pd.DataFrame()
    except IndexError:
        st.error(f"Errore nell'archivio: Il file Excel '{os.path.basename(storico_path)}' sembra essere vuoto (non contiene fogli).")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Errore imprevisto durante il caricamento del file di archivio: {e}")
        return pd.DataFrame()

def scrivi_o_aggiorna_risposta(client, dati_da_scrivere, nome_completo, data_riferimento, row_index=None):
    try:
        foglio_risposte = client.open(config.NOME_FOGLIO_RISPOSTE).sheet1
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        dati_formattati = [timestamp, nome_completo, dati_da_scrivere['descrizione'], dati_da_scrivere['report'], dati_da_scrivere['stato'], data_riferimento.strftime('%d/%m/%Y')]

        if row_index:
            foglio_risposte.update(f'A{row_index}:F{row_index}', [dati_formattati])
            azione = "aggiornato"
        else:
            foglio_risposte.append_row(dati_formattati)
            row_index = len(foglio_risposte.get_all_values())
            azione = "inviato"

        titolo_email = f"Report Attività {azione.upper()} da: {nome_completo}"
        report_html = dati_da_scrivere['report'].replace('\n', '<br>')
        html_body = f"""
        <html>
        <head>
        <style>
            body {{ font-family: Calibri, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
            th {{ background-color: #f2f2f2; }}
            .report-content {{ white-space: pre-wrap; word-wrap: break-word; }}
        </style>
        </head>
        <body>
        <h2>Riepilogo Report Attività</h2>
        <p>Un report è stato <strong>{azione}</strong> dal tecnico {nome_completo}.</p>
        <table>
            <tr>
                <th>Data di Riferimento Attività</th>
                <td>{data_riferimento.strftime('%d/%m/%Y')}</td>
            </tr>
            <tr>
                <th>Data e Ora Invio Report</th>
                <td>{timestamp}</td>
            </tr>
            <tr>
                <th>Tecnico</th>
                <td>{nome_completo}</td>
            </tr>
            <tr>
                <th>Attività</th>
                <td>{dati_da_scrivere['descrizione']}</td>
            </tr>
            <tr>
                <th>Stato Finale</th>
                <td><b>{dati_da_scrivere['stato']}</b></td>
            </tr>
            <tr>
                <th>Report Compilato</th>
                <td class="report-content">{report_html}</td>
            </tr>
        </table>
        </body>
        </html>
        """
        invia_email_con_outlook_async(titolo_email, html_body)
        return row_index
    except Exception as e:
        st.error(f"Errore salvataggio GSheets: {e}")
        return None

def trova_attivita(utente_completo, giorno, mese, anno, df_contatti):
    try:
        path_giornaliera_mensile = os.path.join(config.PATH_GIORNALIERA_BASE, f"Giornaliera {mese:02d}-{anno}.xlsm")
        df_giornaliera = pd.read_excel(path_giornaliera_mensile, sheet_name=str(giorno), engine='openpyxl', header=None)
        df_range = df_giornaliera.iloc[3:45]

        # 1. Trova tutti i PdL per l'utente corrente
        pdls_utente = set()
        for _, riga in df_range.iterrows():
            nome_in_giornaliera = str(riga[5]).strip().lower()
            if utente_completo.lower() in nome_in_giornaliera:
                pdl_text = str(riga[9])
                if not pd.isna(pdl_text):
                    pdls_found = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
                    pdls_utente.update(pdls_found)

        if not pdls_utente:
            return []

        # 2. Raccogli tutte le attività e i membri del team per i PdL rilevanti
        attivita_collezionate = {} # Dizionario per raggruppare per (pdl, desc)
        df_storico_db = carica_archivio_completo()

        for _, riga in df_range.iterrows():
            pdl_text = str(riga[9])
            if pd.isna(pdl_text): continue

            lista_pdl_riga = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)

            # Controlla se c'è almeno un PdL rilevante in questa riga
            if not any(pdl in pdls_utente for pdl in lista_pdl_riga):
                continue

            desc_text = str(riga[6])
            nome_membro = str(riga[5]).strip()
            start_time = str(riga[10])
            end_time = str(riga[11])
            orario = f"{start_time}-{end_time}"

            if pd.isna(desc_text) or not nome_membro or nome_membro.lower() == 'nan':
                continue

            lista_descrizioni_riga = [line.strip() for line in desc_text.splitlines() if line.strip()]

            for pdl, desc in zip(lista_pdl_riga, lista_descrizioni_riga):
                if pdl not in pdls_utente: continue

                activity_key = (pdl, desc)
                if activity_key not in attivita_collezionate:
                    # Carica storico solo la prima volta che incontriamo l'attività
                    storico = []
                    if not df_storico_db.empty:
                        storico_df_pdl = df_storico_db[df_storico_db['PdL'] == pdl].copy()
                        if not storico_df_pdl.empty:
                            storico_df_pdl['Data_Riferimento'] = pd.to_datetime(storico_df_pdl['Data_Riferimento_dt']).dt.strftime('%d/%m/%Y')
                            storico = storico_df_pdl.to_dict('records')

                    attivita_collezionate[activity_key] = {
                        'pdl': pdl,
                        'attivita': desc,
                        'storico': storico,
                        'team_members': {} # Usiamo un dizionario per raggruppare gli orari per membro
                    }

                # Aggiungi o aggiorna il membro del team con il suo orario
                if nome_membro not in attivita_collezionate[activity_key]['team_members']:
                    ruolo_membro = "Sconosciuto"
                    if df_contatti is not None and not df_contatti.empty:
                        matching_user = df_contatti[df_contatti['Nome Cognome'].str.strip().str.lower() == nome_membro.lower()]
                        if not matching_user.empty:
                            ruolo_membro = matching_user.iloc[0].get('Ruolo', 'Tecnico')

                    attivita_collezionate[activity_key]['team_members'][nome_membro] = {
                        'ruolo': ruolo_membro,
                        'orari': set()
                    }

                attivita_collezionate[activity_key]['team_members'][nome_membro]['orari'].add(orario)

        # 3. Formatta l'output finale
        lista_attivita_finale = []
        for activity_data in attivita_collezionate.values():
            team_list = []
            for nome, details in activity_data['team_members'].items():
                team_list.append({
                    'nome': nome,
                    'ruolo': details['ruolo'],
                    'orari': sorted(list(details['orari']))
                })

            activity_data['team'] = team_list
            del activity_data['team_members'] # Pulisci la struttura intermedia
            lista_attivita_finale.append(activity_data)

        return lista_attivita_finale
    except FileNotFoundError:
        return []
    except Exception as e:
        st.error(f"Errore lettura giornaliera: {e}")
        return []

@st.cache_data(ttl=600)
def carica_dati_attivita_programmate():
    excel_path = get_attivita_programmate_path()
    storico_path = get_storico_db_path()

    if not os.path.exists(excel_path):
        st.error(f"File attività programmate non trovato al percorso: {excel_path}")
        return pd.DataFrame()

    sheets_to_read = {
        'A1': {'tcl': 'Francesco Naselli', 'area': 'Area 1'},
        'A2': {'tcl': 'Francesco Naselli', 'area': 'Area 2'},
        'A3': {'tcl': 'Ferdinando Caldarella', 'area': 'Area 3'},
        'CTE': {'tcl': 'Ferdinando Caldarella', 'area': 'CTE'},
        'BLENDING': {'tcl': 'Ivan Messina', 'area': 'BLENDING'},
    }
    
    all_data = []
    giorni_settimana = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì"]
    
    try:
        # Modifica per robustezza: ispeziona il file e usa il primo foglio disponibile invece di 'DB' hardcoded.
        xls_storico = pd.ExcelFile(storico_path)
        if xls_storico.sheet_names:
            sheet_name_storico = xls_storico.sheet_names[0]
            df_storico_full = pd.read_excel(xls_storico, sheet_name=sheet_name_storico)
            df_storico_full['PdL'] = df_storico_full['PdL'].astype(str)
            # Convert Data_Riferimento for sorting
            df_storico_full['Data_Riferimento_dt'] = pd.to_datetime(df_storico_full['Data_Riferimento'], errors='coerce')
            latest_status = df_storico_full.sort_values('Data_Compilazione').drop_duplicates('PdL', keep='last')
            latest_status = latest_status.set_index('PdL')['Stato'].to_dict()
        else:
            # Se il file non ha fogli, inizializza vuoto
            df_storico_full = pd.DataFrame(columns=['PdL', 'Stato', 'Data_Compilazione', 'Data_Riferimento_dt'])
            latest_status = {}
    except FileNotFoundError:
        # Se il file non esiste, inizializza vuoto (non è un errore bloccante per questa vista)
        df_storico_full = pd.DataFrame(columns=['PdL', 'Stato', 'Data_Compilazione', 'Data_Riferimento_dt'])
        latest_status = {}
    except Exception as e:
        st.warning(f"Errore non critico durante il caricamento dello storico: {e}")
        df_storico_full = pd.DataFrame(columns=['PdL', 'Stato', 'Data_Compilazione', 'Data_Riferimento_dt'])
        latest_status = {}

    status_map = {
        # Mappatura esistente
        'DA EMETTERE': 'Pianificato',
        'CHIUSO': 'Completato',
        'ANNULLATO': 'Annullato',
        # Nuova mappatura richiesta dall'utente
        'INTERROTTO': 'Sospeso',
        'RICHIESTO': 'Da processare',
        'EMESSO': 'Processato',      # Sostituisce 'In Corso'
        'IN CORSO': 'Aperto',
        'DA CHIUDERE': 'Terminata'   # Già presente, ma confermato
    }

    for sheet_name, metadata in sheets_to_read.items():
        try:
            # Correzione Definitiva: L'header è alla 3ª riga (indice 2), non alla 4ª.
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
            
            # Pulisce i nomi delle colonne letti da Pandas per rimuovere spazi e gestire i newline.
            df.columns = [str(col).strip() for col in df.columns]

            # Le colonne richieste ora dovrebbero corrispondere a quelle lette da Pandas.
            # Manteniamo la logica di validazione per sicurezza.
            # Correzione finale: I giorni della settimana sono in MAIUSCOLO.
            required_cols = ['PdL', 'IMP.', "DESCRIZIONE\nATTIVITA'", "STATO\nPdL", 'LUN', 'MAR', 'MER', 'GIO', 'VEN']
            if not all(col in df.columns for col in required_cols):
                # Aggiungiamo un log per il debug se le colonne non corrispondono (ora commentato).
                # st.warning(f"Foglio '{sheet_name}' saltato: colonne mancanti. Trovate: {list(df.columns)}. Richieste: {required_cols}")
                continue

            df = df.dropna(subset=['PdL'])
            if df.empty:
                continue

            df_filtered = df[required_cols].copy()
            # Rinomina le colonne per coerenza interna con il resto dell'applicazione.
            df_filtered.columns = ['PdL', 'Impianto', 'Descrizione', 'Stato_OdL', 'Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì']
            
            df_filtered['PdL'] = df_filtered['PdL'].astype(str)
            df_filtered['TCL'] = metadata['tcl']
            df_filtered['Area'] = metadata['area']

            giorni_programmati = df_filtered[giorni_settimana].apply(
                lambda row: ', '.join([giorni_settimana[i] for i, val in enumerate(row) if str(val).strip().upper() == 'X']),
                axis=1
            )
            df_filtered['GiorniProgrammati'] = giorni_programmati.replace('', 'Non Programmato')

            def get_status(row):
                pdl_str = str(row['PdL']).strip()
                if pdl_str in latest_status:
                    return latest_status[pdl_str]
                if pd.notna(row['Stato_OdL']):
                    return status_map.get(str(row['Stato_OdL']).strip().upper(), 'Non Definito')
                return 'Pianificato'

            df_filtered['Stato'] = df_filtered.apply(get_status, axis=1)
            
            df_filtered['Storico'] = df_filtered['PdL'].apply(lambda p: df_storico_full[df_storico_full['PdL'] == p].sort_values(by='Data_Riferimento_dt', ascending=False).to_dict('records') if p in df_storico_full['PdL'].values else [])

            all_data.append(df_filtered)
        except FileNotFoundError:
            st.error(f"Impossibile trovare il file delle attività programmate nel percorso specificato: {excel_path}")
            # Se il file non viene trovato, è inutile continuare a ciclare.
            break
        except PermissionError:
            st.error(f"Errore di permessi. Impossibile accedere al file: {excel_path}. Verificare i permessi di lettura.")
            # Se c'è un errore di permessi, è inutile continuare.
            break
        except Exception as e:
            # Stampa un avviso per fogli specifici che potrebbero avere problemi, ma continua il ciclo.
            st.warning(f"Si è verificato un errore durante l'elaborazione del foglio '{sheet_name}' dal file {os.path.basename(excel_path)}: {e}")
            continue

    if not all_data:
        # Se dopo tutti i tentativi non ci sono dati, informa l'utente.
        # Questo messaggio apparirà solo se il file esiste ma è vuoto o non contiene fogli validi.
        st.warning("Non sono stati trovati dati validi sulle attività programmate. Verificare che il file Excel non sia vuoto e che i fogli ('A1', 'A2', ecc.) siano formattati correttamente.")
        return pd.DataFrame()

    final_df = pd.concat(all_data, ignore_index=True)
    return final_df