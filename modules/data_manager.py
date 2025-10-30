import streamlit as st
import pandas as pd
import os
import json
import datetime
import re
import threading
import openpyxl

import config
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

def scrivi_o_aggiorna_risposta(dati_da_scrivere, matricola, data_riferimento):
    """
    Scrive un report direttamente nella tabella `report_da_validare` del database SQLite.
    """
    import sqlite3
    import uuid

    azione = "inviato per validazione"
    timestamp_compilazione = datetime.datetime.now()

    conn = None
    try:
        conn = sqlite3.connect("schedario.db")
        cursor = conn.cursor()

        cursor.execute("SELECT \"Nome Cognome\" FROM contatti WHERE Matricola = ?", (str(matricola),))
        user_result = cursor.fetchone()
        if not user_result:
            st.error(f"Impossibile trovare l'utente con matricola {matricola}.")
            return False
        nome_completo = user_result[0]

        descrizione_completa = str(dati_da_scrivere['descrizione'])
        pdl_match = re.search(r'PdL (\d{6}/[CS]|\d{6})', descrizione_completa)
        pdl = pdl_match.group(1) if pdl_match else "N/D"

        id_report = str(uuid.uuid4())

        dati_nuovo_report = {
            "id_report": id_report,
            "pdl": pdl,
            "descrizione_attivita": dati_da_scrivere['descrizione'],
            "matricola_tecnico": str(matricola),
            "nome_tecnico": nome_completo,
            "stato_attivita": dati_da_scrivere['stato'],
            "testo_report": dati_da_scrivere['report'],
            "data_compilazione": timestamp_compilazione.isoformat(),
            "data_riferimento_attivita": data_riferimento.isoformat()
        }

        with conn:
            cols = ', '.join(f'"{k}"' for k in dati_nuovo_report.keys())
            placeholders = ', '.join('?' for _ in dati_nuovo_report)
            sql = f"INSERT INTO report_da_validare ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_nuovo_report.values()))

        from modules.email_sender import invia_email_con_outlook_async
        titolo_email = f"Nuovo Report da Validare da: {nome_completo}"
        report_html = dati_da_scrivere['report'].replace('\n', '<br>')
        html_body = f"""
        <html><head><style>
            body {{ font-family: Calibri, sans-serif; }} table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }} th {{ background-color: #f2f2f2; }}
        </style></head><body>
        <h2>Nuovo Report da Validare</h2>
        <p>Un report è stato <strong>{azione}</strong> dal tecnico {nome_completo}.</p>
        <table>
            <tr><th>Data di Riferimento Attività</th><td>{data_riferimento.strftime('%d/%m/%Y')}</td></tr>
            <tr><th>Data e Ora Invio Report</th><td>{timestamp_compilazione.strftime('%d/%m/%Y %H:%M:%S')}</td></tr>
            <tr><th>Tecnico</th><td>{nome_completo}</td></tr>
            <tr><th>Attività</th><td>{dati_da_scrivere['descrizione']}</td></tr>
            <tr><th>Stato Finale</th><td><b>{dati_da_scrivere['stato']}</b></td></tr>
            <tr><th>Report Compilato</th><td>{report_html}</td></tr>
        </table>
        <br><hr>
        <p><em>Email generata automaticamente dal sistema Gestionale.</em></p>
        <p><strong>Gianky Allegretti</strong><br>
        Direttore Tecnico</p>
        </body></html>
        """
        invia_email_con_outlook_async(titolo_email, html_body)

        st.cache_data.clear()
        return True

    except sqlite3.Error as e:
        st.error(f"Errore durante il salvataggio del report nel database: {e}")
        return False
    except Exception as e:
        st.error(f"Errore imprevisto durante il salvataggio del report: {e}")
        return False
    finally:
        if conn:
            conn.close()

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

@st.cache_data(ttl=3600)
def _carica_giornaliera_mese(path):
    """
    Funzione cachata per caricare il file Excel una sola volta per mese/anno.
    Spostata al livello superiore del modulo per permettere la pulizia della cache.
    """
    try:
        return pd.read_excel(path, sheet_name=None, header=None)
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Errore imprevisto durante la lettura di {path}: {e}")
        return None

def trova_attivita(matricola, giorno, mese, anno, df_contatti):
    try:
        # --- FASE 1: Trova il nome completo dell'utente dalla matricola ---
        if df_contatti is None or df_contatti.empty:
            st.warning("Dataframe contatti non disponibile per `trova_attivita`.")
            return []

        user_series = df_contatti[df_contatti['Matricola'] == str(matricola)]
        if user_series.empty:
            st.warning(f"Impossibile trovare l'utente con matricola {matricola}.")
            return []
        utente_completo = user_series.iloc[0]['Nome Cognome']

        path_giornaliera_mensile = os.path.join(config.PATH_GIORNALIERA_BASE, f"Giornaliera {mese:02d}-{anno}.xlsm")

        # Carica l'intero workbook in memoria (cachato)
        workbook_sheets = _carica_giornaliera_mese(path_giornaliera_mensile)
        if workbook_sheets is None:
            return [] # File non trovato per il mese/anno

        # Trova il nome corretto del foglio per il giorno richiesto
        target_sheet_name = None
        day_str = str(giorno)
        for sheet_name in workbook_sheets.keys():
            if day_str in sheet_name.split():
                target_sheet_name = sheet_name
                break

        if not target_sheet_name:
            return [] # Foglio per il giorno non trovato

        df_giornaliera = workbook_sheets[target_sheet_name]
        df_range = df_giornaliera.iloc[3:45]

        pdls_utente = set()
        for _, riga in df_range.iterrows():
            if 5 < len(riga) and 9 < len(riga):
                nome_in_giornaliera = str(riga[5]).strip()
                if nome_in_giornaliera and _match_partial_name(nome_in_giornaliera, utente_completo):
                    pdl_text = str(riga[9])
                    if not pd.isna(pdl_text):
                        pdls_found = re.findall(r'(\d{6}/[CS]|\d{6})', pdl_text)
                        pdls_utente.update(pdls_found)

        if not pdls_utente:
            return []

        # Ottimizzazione: Carica lo storico una sola volta
        df_storico_db = pd.DataFrame() #FIXME: carica_dati_attivita_programmate() was removed

        attivita_collezionate = {}
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
                    # Filtra lo storico per il PdL corrente
                    storico_pdl = [] #df_storico_db[df_storico_db['PdL'] == pdl].to_dict('records')

                    attivita_collezionate[activity_key] = {
                        'pdl': pdl,
                        'attivita': desc,
                        'storico': storico_pdl[0]['Storico'] if storico_pdl and 'Storico' in storico_pdl[0] else [],
                        'team_members': {}
                    }

                if nome_membro not in attivita_collezionate[activity_key]['team_members']:
                    ruolo_membro = "Sconosciuto"
                    for _, contact_row in df_contatti.iterrows():
                        if _match_partial_name(nome_membro, contact_row['Nome Cognome']):
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

    except Exception as e:
        # Evita di mostrare errori se il file non esiste (comportamento atteso per giorni futuri)
        if not isinstance(e, FileNotFoundError):
            st.error(f"Errore durante la ricerca attività per il {giorno}/{mese}/{anno}: {e}")
        return []

