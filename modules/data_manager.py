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

            # Aggiunto per le richieste di materiali
            required_materiali_cols = ['ID_Richiesta', 'Richiedente', 'Timestamp', 'Stato', 'Dettagli']
            if 'RichiesteMateriali' in xls.sheet_names:
                df_materiali = pd.read_excel(xls, sheet_name='RichiesteMateriali')
                df_materiali.columns = df_materiali.columns.str.strip()
                for col in required_materiali_cols:
                    if col not in df_materiali.columns:
                        df_materiali[col] = pd.NA
                data['richieste_materiali'] = df_materiali
            else:
                data['richieste_materiali'] = pd.DataFrame(columns=required_materiali_cols)

            # Aggiunto per le richieste di assenze
            required_assenze_cols = ['ID_Richiesta', 'Richiedente', 'Timestamp', 'Tipo_Assenza', 'Data_Inizio', 'Data_Fine', 'Note', 'Stato']
            if 'RichiesteAssenze' in xls.sheet_names:
                df_assenze = pd.read_excel(xls, sheet_name='RichiesteAssenze')
                df_assenze.columns = df_assenze.columns.str.strip()
                for col in required_assenze_cols:
                    if col not in df_assenze.columns:
                        df_assenze[col] = pd.NA
                data['richieste_assenze'] = df_assenze
            else:
                data['richieste_assenze'] = pd.DataFrame(columns=required_assenze_cols)


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
            if 'richieste_materiali' in data:
                data['richieste_materiali'].to_excel(writer, sheet_name='RichiesteMateriali', index=False)
            if 'richieste_assenze' in data:
                data['richieste_assenze'].to_excel(writer, sheet_name='RichiesteAssenze', index=False)
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

def crea_storico_da_programmazione():
    """
    Crea uno storico "fittizio" basato sui dati del file delle attività programmate.
    Questo serve per popolare l'archivio con interventi passati non registrati tramite l'app.
    """
    excel_path = get_attivita_programmate_path()
    all_backfill_data = []

    sheets_to_read = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']
    backfill_cols = ['PdL', 'DATA\nCONTROLLO', 'PERSONALE\nIMPIEGATO', "DESCRIZIONE\nATTIVITA'"]

    for sheet_name in sheets_to_read:
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=2)
            df.columns = [str(col).strip() for col in df.columns]

            if not all(col in df.columns for col in backfill_cols):
                continue

            df_filtered = df[backfill_cols].copy()
            df_filtered.dropna(subset=['PdL', 'DATA\nCONTROLLO', 'PERSONALE\nIMPIEGATO'], inplace=True)
            if df_filtered.empty:
                continue

            all_backfill_data.append(df_filtered)
        except Exception:
            continue # Ignora fogli mancanti o con errori di formato

    if not all_backfill_data:
        return pd.DataFrame()

    df_backfill = pd.concat(all_backfill_data, ignore_index=True)

    # Rinomina le colonne per corrispondere allo schema dell'archivio
    df_backfill.rename(columns={
        "DATA\nCONTROLLO": "Data_Riferimento",
        "PERSONALE\nIMPIEGATO": "Tecnico",
        "DESCRIZIONE\nATTIVITA'": "Report"
    }, inplace=True)

    # Aggiungi colonne mancanti con valori di default
    df_backfill['Data_Compilazione'] = pd.to_datetime(df_backfill['Data_Riferimento'], errors='coerce')
    df_backfill['Stato'] = 'Storico Importato'
    df_backfill['Descrizione'] = "Intervento importato da storico programmazione"

    return df_backfill


def carica_archivio_completo():
    """
    Carica l'archivio storico completo, unendo i report reali con lo storico
    importato dal file di programmazione per completezza.
    """
    storico_path = config.PATH_STORICO_DB
    df_reale = pd.DataFrame()
    df_backfill = pd.DataFrame()

    # 1. Carica l'archivio reale dei report compilati
    try:
        sheet_name = 'Database_Attivita'
        df_reale = pd.read_excel(storico_path, sheet_name=sheet_name)
        df_reale['Data_Riferimento_dt'] = pd.to_datetime(df_reale['Data_Riferimento'], errors='coerce')
    except FileNotFoundError:
        st.warning(f"File archivio '{os.path.basename(storico_path)}' non trovato. Verrà usato solo lo storico da programmazione.")
    except Exception as e:
        st.error(f"Errore imprevisto durante il caricamento del file di archivio: {e}")
        return pd.DataFrame() # Errore bloccante

    # 2. Crea lo storico dal file di programmazione
    df_backfill = crea_storico_da_programmazione()
    if not df_backfill.empty:
        df_backfill['Data_Riferimento_dt'] = pd.to_datetime(df_backfill['Data_Riferimento'], errors='coerce')

    # 3. Unisci i due DataFrame, dando priorità ai dati reali
    if not df_reale.empty and not df_backfill.empty:
        # Crea una chiave univoca (PdL + Data) per la de-duplicazione
        df_reale['join_key'] = df_reale['PdL'].astype(str) + '_' + df_reale['Data_Riferimento_dt'].dt.strftime('%Y-%m-%d')
        df_backfill['join_key'] = df_backfill['PdL'].astype(str) + '_' + df_backfill['Data_Riferimento_dt'].dt.strftime('%Y-%m-%d')

        # Filtra i dati di backfill per mantenere solo quelli non presenti nei dati reali
        df_backfill_filtered = df_backfill[~df_backfill['join_key'].isin(df_reale['join_key'])]

        # Concatena e rimuovi la colonna chiave
        df_finale = pd.concat([df_reale, df_backfill_filtered], ignore_index=True)
        df_finale.drop(columns=['join_key'], inplace=True, errors='ignore')

    elif not df_reale.empty:
        df_finale = df_reale
    elif not df_backfill.empty:
        df_finale = df_backfill
    else:
        return pd.DataFrame()

    # 4. Pulisci e ordina il DataFrame finale
    df_finale['Data_Riferimento_dt'] = pd.to_datetime(df_finale['Data_Riferimento'], errors='coerce')
    # Assicura che la colonna di compilazione sia di tipo datetime per un ordinamento corretto
    df_finale['Data_Compilazione'] = pd.to_datetime(df_finale['Data_Compilazione'], errors='coerce')
    df_finale.dropna(subset=['Data_Riferimento_dt'], inplace=True)
    df_finale.sort_values(by='Data_Compilazione', ascending=True, inplace=True)
    # Rimuovi eventuali duplicati residui (anche se la logica di join dovrebbe averli già gestiti)
    df_finale.drop_duplicates(subset=['PdL', 'Tecnico', 'Data_Riferimento'], keep='last', inplace=True)

    return df_finale

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

def _match_partial_name(partial_name, full_name):
    """
    Intelligently matches a partial name (e.g., 'Garro L.') with a full name (e.g., 'Luca Garro').
    """
    if not partial_name or not full_name:
        return False

    # Normalize and split names into parts
    partial_parts = [p.replace('.', '') for p in partial_name.lower().split()]
    full_parts = full_name.lower().split()

    # Separate names and initials from the partial name
    partial_initials = {p for p in partial_parts if len(p) == 1}
    partial_names = {p for p in partial_parts if len(p) > 1}

    # All name parts from the partial name must be in the full name
    if not partial_names.issubset(set(full_parts)):
        return False

    # Get the parts of the full name that are not in the partial name (potential first names)
    remaining_full_parts = set(full_parts) - partial_names

    # Get the initials of the remaining parts
    remaining_initials = {p[0] for p in remaining_full_parts}

    # All initials from the partial name must match the initials of the remaining parts
    if not partial_initials.issubset(remaining_initials):
        return False

    return True

def trova_attivita(utente_completo, giorno, mese, anno, df_contatti):
    try:
        path_giornaliera_mensile = os.path.join(config.PATH_GIORNALIERA_BASE, f"Giornaliera {mese:02d}-{anno}.xlsm")

        target_sheet = str(giorno)
        try:
            workbook = openpyxl.load_workbook(path_giornaliera_mensile, read_only=True)
            day_str = str(giorno)
            for sheet_name in workbook.sheetnames:
                if day_str in sheet_name.split():
                    target_sheet = sheet_name
                    break
        except Exception:
            pass

        df_giornaliera = pd.read_excel(path_giornaliera_mensile, sheet_name=target_sheet, engine='openpyxl', header=None)
        df_range = df_giornaliera.iloc[3:45]

        pdls_utente = set()
        for _, riga in df_range.iterrows():
            if 5 < len(riga) and 9 < len(riga):
                nome_in_giornaliera = str(riga[5]).strip().lower()
                if nome_in_giornaliera and nome_in_giornaliera in utente_completo.lower():
                    pdl_text = str(riga[9])
                    if not pd.isna(pdl_text):
                        pdls_found = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
                        pdls_utente.update(pdls_found)

        if not pdls_utente:
            return []

        attivita_collezionate = {}
        df_storico_db = carica_archivio_completo()

        for _, riga in df_range.iterrows():
            pdl_text = str(riga[9])
            if pd.isna(pdl_text): continue
            lista_pdl_riga = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
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
                        'team_members': {}
                    }
                if nome_membro not in attivita_collezionate[activity_key]['team_members']:
                    ruolo_membro = "Sconosciuto"
                    if df_contatti is not None and not df_contatti.empty:
                        for _, contact_row in df_contatti.iterrows():
                            full_name = contact_row['Nome Cognome']
                            if _match_partial_name(nome_membro, full_name):
                                ruolo_membro = contact_row.get('Ruolo', 'Tecnico')
                                break
                    attivita_collezionate[activity_key]['team_members'][nome_membro] = {
                        'ruolo': ruolo_membro,
                        'orari': set()
                    }
                attivita_collezionate[activity_key]['team_members'][nome_membro]['orari'].add(orario)

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
            del activity_data['team_members']
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
    
    # Refactoring: Chiama la funzione centralizzata per caricare lo storico, garantendo coerenza.
    df_storico_full = carica_archivio_completo()
    if not df_storico_full.empty:
        latest_status = df_storico_full.sort_values('Data_Compilazione').drop_duplicates('PdL', keep='last')
        latest_status = latest_status.set_index('PdL')['Stato'].to_dict()
    else:
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

# --- NUOVA LOGICA DI SINCRONIZZAZIONE MANUALE ---

def _leggi_report_da_google(client):
    """Legge i dati grezzi dei report dal foglio Google specificato."""
    try:
        sheet = client.open(config.NOME_FOGLIO_RISPOSTE).sheet1
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if df.empty:
            return None
        return df
    except Exception as e:
        st.error(f"Errore durante la lettura dei dati da Google Sheets: {e}")
        return None

def _processa_dati_grezzi(df_grezzo):
    """Processa i dati grezzi letti da Google per prepararli all'inserimento nel database."""
    if df_grezzo is None:
        return None

    lista_attivita_pulite = []

    # Nomi delle colonne come appaiono nel foglio Google
    COLONNA_TIMESTAMP = 'Informazioni cronologiche'
    COLONNA_UTENTE = 'Nome e Cognome'
    COLONNA_DESCRIZIONE_PDL = '1. Descrizione PdL'
    COLONNA_REPORT = '1. Report Attività'
    COLONNA_STATO = '1. Stato attività'
    COLONNA_DATA_RIFERIMENTO = 'Data Riferimento Attività'

    # Validazione colonne
    colonne_necessarie = [COLONNA_TIMESTAMP, COLONNA_UTENTE, COLONNA_DESCRIZIONE_PDL, COLONNA_REPORT, COLONNA_STATO]
    for col in colonne_necessarie:
        if col not in df_grezzo.columns:
            st.error(f"Errore critico: La colonna '{col}' non è stata trovata nel foglio Google!")
            return None

    for _, riga in df_grezzo.iterrows():
        if pd.isna(riga[COLONNA_DESCRIZIONE_PDL]) or str(riga[COLONNA_DESCRIZIONE_PDL]).strip() == '':
            continue

        descrizione_completa = str(riga[COLONNA_DESCRIZIONE_PDL])
        pdl_match = re.search(r'PdL (\d{6}/[CS]|\d{6})', descrizione_completa)
        pdl = pdl_match.group(1) if pdl_match else ''
        descrizione_pulita = re.sub(r'PdL \d{6}/?[CS]?\s*[-:]?\s*', '', descrizione_completa).strip()

        data_riferimento_str = str(riga.get(COLONNA_DATA_RIFERIMENTO, '')).strip()
        if data_riferimento_str:
            data_riferimento = data_riferimento_str
        else:
            timestamp_str = str(riga.get(COLONNA_TIMESTAMP, ''))
            match = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})', timestamp_str)
            data_riferimento = match.group(1).replace('-', '/').replace('.', '/') if match else datetime.date.today().strftime('%d/%m/%Y')

        nuova_riga = {
            'PdL': pdl,
            'Descrizione': descrizione_pulita,
            'Stato': riga[COLONNA_STATO],
            'Tecnico': riga[COLONNA_UTENTE],
            'Report': riga[COLONNA_REPORT],
            'Data_Compilazione': riga[COLONNA_TIMESTAMP],
            'Data_Riferimento': data_riferimento
        }
        lista_attivita_pulite.append(nuova_riga)

    if not lista_attivita_pulite:
        return None

    return pd.DataFrame(lista_attivita_pulite)

def _salva_db_excel(df, percorso_salvataggio):
    """Salva il DataFrame nel file Excel, preservando le macro."""
    from openpyxl import load_workbook
    from openpyxl.utils.dataframe import dataframe_to_rows
    from openpyxl.styles import Font
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter

    file_template = os.path.join(os.path.dirname(percorso_salvataggio), "Database_Template.xlsm")
    file_da_usare = percorso_salvataggio if os.path.exists(percorso_salvataggio) else file_template

    try:
        wb = load_workbook(file_da_usare, keep_vba=True)
        ws = wb['Database_Attivita']

        # Cancella i vecchi dati ma non l'header
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)

        for r in dataframe_to_rows(df, index=False, header=False):
            ws.append(r)

        # Rimuovi e ricrea la tabella per aggiornare il range
        if 'TabellaAttivita' in ws.tables:
            del ws.tables['TabellaAttivita']

        if not df.empty:
            max_row, max_col = len(df) + 1, len(df.columns)
            table_range = f"A1:{get_column_letter(max_col)}{max_row}"
            tab = Table(displayName="TabellaAttivita", ref=table_range)
            style = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
            tab.tableStyleInfo = style
            ws.add_table(tab)

        wb.save(percorso_salvataggio)
        return True, f"Database salvato con successo in '{os.path.basename(percorso_salvataggio)}'."
    except FileNotFoundError:
        return False, f"Errore: File template '{os.path.basename(file_template)}' o database esistente non trovato."
    except Exception as e:
        return False, f"Errore durante il salvataggio del file Excel: {e}"

def sync_reports_from_google(client_google):
    """
    Funzione principale per orchestrare la sincronizzazione dei report.
    """
    # 1. Leggi i dati da Google Sheets
    df_grezzo = _leggi_report_da_google(client_google)
    if df_grezzo is None:
        return True, "Nessun nuovo report trovato su Google Sheets o foglio vuoto."

    # 2. Processa i dati
    df_nuovi_report = _processa_dati_grezzi(df_grezzo)
    if df_nuovi_report is None:
        return True, "I nuovi report erano vuoti o non validi dopo il processamento."

    # 3. Carica il database esistente
    percorso_db = get_storico_db_path()
    try:
        df_esistente = pd.read_excel(percorso_db)
    except FileNotFoundError:
        df_esistente = pd.DataFrame() # Il file non esiste, verrà creato
    except Exception as e:
        return False, f"Errore nel caricamento del database esistente: {e}"

    # 4. Aggiorna il database
    df_combinato = pd.concat([df_esistente, df_nuovi_report], ignore_index=True)
    colonne_identificative = ['Tecnico', 'Data_Riferimento', 'PdL']
    df_combinato.sort_values('Data_Compilazione', ascending=True, inplace=True)
    df_combinato.drop_duplicates(subset=colonne_identificative, keep='last', inplace=True)
    df_ordinato = df_combinato.sort_values(by=['Data_Riferimento', 'PdL', 'Tecnico'], ascending=[False, True, True])

    # 5. Salva il database aggiornato
    success, message = _salva_db_excel(df_ordinato, percorso_db)

    # 6. Pulisci la cache se il salvataggio è andato a buon fine
    if success:
        st.cache_data.clear()

    return success, message