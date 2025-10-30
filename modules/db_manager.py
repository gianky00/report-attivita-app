import sqlite3
import pandas as pd
import os
import json
import streamlit as st

DB_NAME = "schedario.db"

def get_db_connection():
    """Crea e restituisce una connessione al database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_shifts_by_type(shift_type: str) -> pd.DataFrame:
    """Carica i turni di un tipo specifico direttamente dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM turni WHERE Tipo = ? ORDER BY Data DESC"
        df = pd.read_sql_query(query, conn, params=(shift_type,))
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare i turni per tipo '{shift_type}': {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_assignments_by_technician(matricola: str) -> pd.DataFrame:
    """Recupera gli assegnamenti di attività per un tecnico specifico."""
    df = get_unvalidated_reports_by_technician(matricola)
    # Rename id_report to id_attivita to match the UI expectation
    if 'id_report' in df.columns:
        df.rename(columns={'id_report': 'id_attivita'}, inplace=True)
    return df

def add_assignment_exclusion(matricola_escludente: str, id_attivita: str) -> bool:
    """Aggiunge una regola di esclusione per un assegnamento."""
    import datetime
    conn = get_db_connection()
    try:
        with conn:
            sql = "INSERT INTO esclusioni_assegnamenti (matricola_escludente, id_attivita, timestamp) VALUES (?, ?, ?)"
            conn.execute(sql, (matricola_escludente, id_attivita, datetime.datetime.now().isoformat()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta della regola di esclusione: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_globally_excluded_activities() -> list:
    """Recupera una lista di ID di attività escluse globalmente."""
    conn = get_db_connection()
    try:
        query = "SELECT id_attivita FROM esclusioni_assegnamenti"
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row['id_attivita'] for row in rows]
    except sqlite3.Error as e:
        print(f"Errore nel recuperare le attività escluse globalmente: {e}")
        return []
    finally:
        if conn:
            conn.close()


def add_shift_log(log_data: dict) -> bool:
    """Aggiunge un nuovo log di modifica turno al database."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in log_data.keys())
            placeholders = ', '.join('?' for _ in log_data)
            sql = f"INSERT INTO shift_logs ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(log_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta del log di modifica turno: {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_shift(shift_id: str, update_data: dict) -> bool:
    """Aggiorna i dati di un turno."""
    conn = get_db_connection()
    try:
        with conn:
            set_clause = ', '.join(f'"{k}" = ?' for k in update_data.keys())
            sql = f"UPDATE turni SET {set_clause} WHERE ID_Turno = ?"
            params = list(update_data.values()) + [shift_id]
            cursor = conn.execute(sql, params)
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiornamento del turno: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_material_request(request_data: dict) -> bool:
    """Aggiunge una nuova richiesta di materiali al database."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in request_data.keys())
            placeholders = ', '.join('?' for _ in request_data)
            sql = f"INSERT INTO richieste_materiali ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(request_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta della richiesta materiali: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_leave_request(request_data: dict) -> bool:
    """Aggiunge una nuova richiesta di assenza al database."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in request_data.keys())
            placeholders = ', '.join('?' for _ in request_data)
            sql = f"INSERT INTO richieste_assenze ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(request_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta della richiesta di assenza: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_material_requests() -> pd.DataFrame:
    """Carica tutte le richieste di materiali dal database."""
    return get_table_data('richieste_materiali')

def get_leave_requests() -> pd.DataFrame:
    """Carica tutte le richieste di assenza dal database."""
    return get_table_data('richieste_assenze')

def get_notifications_for_user(matricola: str) -> pd.DataFrame:
    """Recupera le notifiche per un utente specifico."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM notifiche WHERE Destinatario_Matricola = ? ORDER BY Timestamp DESC"
        df = pd.read_sql_query(query, conn, params=(str(matricola),))
        return df
    finally:
        if conn:
            conn.close()

def add_notification(notification_data: dict) -> bool:
    """Aggiunge una nuova notifica al database."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in notification_data.keys())
            placeholders = ', '.join('?' for _ in notification_data)
            sql = f"INSERT INTO notifiche ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(notification_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta della notifica: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_bacheca_item_by_id(item_id: str) -> dict:
    """Recupera un annuncio in bacheca per ID."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM bacheca WHERE ID_Bacheca = ?"
        cursor = conn.cursor()
        cursor.execute(query, (item_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        if conn:
            conn.close()

def update_bacheca_item(item_id: str, update_data: dict) -> bool:
    """Aggiorna un annuncio in bacheca."""
    conn = get_db_connection()
    try:
        with conn:
            set_clause = ', '.join(f'"{k}" = ?' for k in update_data.keys())
            sql = f"UPDATE bacheca SET {set_clause} WHERE ID_Bacheca = ?"
            params = list(update_data.values()) + [item_id]
            cursor = conn.execute(sql, params)
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiornamento dell'annuncio in bacheca: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_booking_by_user_and_shift(matricola: str, shift_id: str) -> dict:
    """Recupera una prenotazione specifica per utente e turno."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM prenotazioni WHERE Matricola = ? AND ID_Turno = ?"
        cursor = conn.cursor()
        cursor.execute(query, (str(matricola), shift_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        if conn:
            conn.close()

def add_bacheca_item(item_data: dict) -> bool:
    """Aggiunge un nuovo annuncio in bacheca."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in item_data.keys())
            placeholders = ', '.join('?' for _ in item_data)
            sql = f"INSERT INTO bacheca ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(item_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta dell'annuncio in bacheca: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_substitution_request_by_id(request_id: str) -> dict:
    """Recupera una richiesta di sostituzione per ID."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM sostituzioni WHERE ID_Richiesta = ?"
        cursor = conn.cursor()
        cursor.execute(query, (request_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        if conn:
            conn.close()

def delete_substitution_request(request_id: str) -> bool:
    """Cancella una richiesta di sostituzione per ID."""
    conn = get_db_connection()
    try:
        with conn:
            sql = "DELETE FROM sostituzioni WHERE ID_Richiesta = ?"
            cursor = conn.execute(sql, (request_id,))
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Errore durante la cancellazione della richiesta di sostituzione: {e}")
        return False
    finally:
        if conn:
            conn.close()

def update_booking_user(shift_id: str, old_matricola: str, new_matricola: str) -> bool:
    """Aggiorna la matricola di una prenotazione."""
    conn = get_db_connection()
    try:
        with conn:
            sql = "UPDATE prenotazioni SET Matricola = ? WHERE ID_Turno = ? AND Matricola = ?"
            cursor = conn.execute(sql, (new_matricola, shift_id, old_matricola))
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiornamento della prenotazione: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_substitution_request(request_data: dict) -> bool:
    """Aggiunge una nuova richiesta di sostituzione al database."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in request_data.keys())
            placeholders = ', '.join('?' for _ in request_data)
            sql = f"INSERT INTO sostituzioni ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(request_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta della richiesta di sostituzione: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_booking(matricola: str, shift_id: str) -> bool:
    """Cancella una prenotazione dal database."""
    conn = get_db_connection()
    try:
        with conn:
            sql = "DELETE FROM prenotazioni WHERE Matricola = ? AND ID_Turno = ?"
            cursor = conn.execute(sql, (str(matricola), shift_id))
            # Check if any row was actually deleted
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Errore durante la cancellazione della prenotazione: {e}")
        return False
    finally:
        if conn:
            conn.close()

def create_shift(shift_data: dict) -> bool:
    """Crea un nuovo turno nel database."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in shift_data.keys())
            placeholders = ', '.join('?' for _ in shift_data)
            sql = f"INSERT INTO turni ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(shift_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante la creazione del turno: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_users() -> pd.DataFrame:
    """Carica tutti gli utenti (contatti) dal database."""
    return get_table_data('contatti')

def get_access_logs() -> pd.DataFrame:
    """Carica la cronologia degli accessi dal database."""
    return get_table_data('access_logs')

def get_all_bookings() -> pd.DataFrame:
    """Carica tutte le prenotazioni dal database."""
    return get_table_data('prenotazioni')

def get_all_substitutions() -> pd.DataFrame:
    """Carica tutte le richieste di sostituzione dal database."""
    return get_table_data('sostituzioni')

def get_all_bacheca_items() -> pd.DataFrame:
    """Carica tutti gli annunci in bacheca dal database."""
    return get_table_data('bacheca')

def get_shift_by_id(shift_id: str) -> dict:
    """Recupera un turno specifico per ID."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM turni WHERE ID_Turno = ?"
        cursor = conn.cursor()
        cursor.execute(query, (shift_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        if conn:
            conn.close()

def get_bookings_for_shift(shift_id: str) -> pd.DataFrame:
    """Recupera le prenotazioni per un turno specifico."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM prenotazioni WHERE ID_Turno = ?"
        df = pd.read_sql_query(query, conn, params=(shift_id,))
        return df
    finally:
        if conn:
            conn.close()

def add_booking(booking_data: dict) -> bool:
    """Aggiunge una nuova prenotazione al database."""
    conn = get_db_connection()
    try:
        with conn:
            cols = ', '.join(f'"{k}"' for k in booking_data.keys())
            placeholders = ', '.join('?' for _ in booking_data)
            sql = f"INSERT INTO prenotazioni ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(booking_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiunta della prenotazione: {e}")
        return False
    finally:
        if conn:
            conn.close()

def count_unread_notifications(matricola: str) -> int:
    """Conta il numero di notifiche non lette per un utente."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM notifiche WHERE Destinatario_Matricola = ? AND Stato = 'Non letta'"
        cursor.execute(query, (matricola,))
        count = cursor.fetchone()[0]
        return count
    except sqlite3.Error as e:
        print(f"Errore nel contare le notifiche non lette: {e}")
        return 0
    finally:
        if conn:
            conn.close()

def get_last_login(matricola: str):
    """Recupera l'ultimo timestamp di login riuscito per una data matricola."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT timestamp
            FROM access_logs
            WHERE username = ? AND (status = 'Login 2FA riuscito' OR status = 'Setup 2FA completato e login riuscito')
            ORDER BY timestamp DESC
            LIMIT 1
        """
        cursor.execute(query, (matricola,))
        result = cursor.fetchone()
        return result['timestamp'] if result else None
    except sqlite3.Error as e:
        print(f"Errore nel recuperare l'ultimo login per la matricola {matricola}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def process_and_commit_validated_relazioni(validated_df: pd.DataFrame, validator_id: str) -> bool:
    """Processa le relazioni validate, aggiornandole nel DB."""
    import datetime
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            for _, row in validated_df.iterrows():
                # Ricostruisci la data di intervento dal formato stringa
                try:
                    data_intervento_iso = pd.to_datetime(row['data_intervento'], format='%d/%m/%Y').isoformat()
                except ValueError:
                    data_intervento_iso = row['data_intervento'] # Mantieni il formato se non è valido

                cursor.execute(
                    """
                    UPDATE relazioni SET
                        data_intervento = ?,
                        tecnico_compilatore = ?,
                        partner = ?,
                        ora_inizio = ?,
                        ora_fine = ?,
                        corpo_relazione = ?,
                        stato = ?,
                        id_validatore = ?,
                        timestamp_validazione = ?
                    WHERE id_relazione = ?
                    """,
                    (
                        data_intervento_iso,
                        row.get('tecnico_compilatore'),
                        row.get('partner'),
                        row.get('ora_inizio'),
                        row.get('ora_fine'),
                        row.get('corpo_relazione'),
                        'Validata', # Imposta lo stato a Validata
                        validator_id,
                        datetime.datetime.now().isoformat(),
                        row['id_relazione']
                    )
                )
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio delle relazioni validate: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_unvalidated_relazioni() -> pd.DataFrame:
    """Carica le relazioni in attesa di validazione ('Inviata')."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM relazioni WHERE stato = 'Inviata' ORDER BY timestamp_invio ASC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare le relazioni da validare: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_reports_to_validate() -> pd.DataFrame:
    """Carica tutti i report in attesa di validazione dalla tabella dedicata."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM report_da_validare ORDER BY data_compilazione ASC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare i report da validare: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def delete_reports_by_ids(report_ids: list) -> bool:
    """Cancella una lista di report dalla tabella di validazione."""
    if not report_ids:
        return True
    conn = get_db_connection()
    try:
        with conn:
            placeholders = ','.join('?' for _ in report_ids)
            query = f"DELETE FROM report_da_validare WHERE id_report IN ({placeholders})"
            conn.execute(query, report_ids)
        return True
    except sqlite3.Error as e:
        print(f"Errore durante la cancellazione dei report: {e}")
        return False
    finally:
        if conn:
            conn.close()

def process_and_commit_validated_reports(validated_data: list) -> bool:
    """
    Salva i report validati nella tabella `report_interventi` del database
    e poi li rimuove dalla tabella di validazione.
    """
    if not validated_data:
        return True

    # 1. Salva i report validati nella tabella 'report_interventi'
    import datetime
    for report_dict in validated_data:
        report_data = {
            "id_report": report_dict.get('id_report'),
            "pdl": report_dict.get('pdl'),
            "descrizione_attivita": report_dict.get('descrizione_attivita'),
            "matricola_tecnico": report_dict.get('matricola_tecnico'),
            "nome_tecnico": report_dict.get('nome_tecnico'),
            "stato_attivita": "Validato", # Sovrascrive lo stato
            "testo_report": report_dict.get('testo_report'),
            "data_compilazione": report_dict.get('data_compilazione'),
            "data_riferimento_attivita": report_dict.get('data_riferimento_attivita'),
            "timestamp_validazione": datetime.datetime.now().isoformat()
        }
        if not salva_report_intervento(report_data):
            # Se il salvataggio nel DB fallisce, logga l'errore ma non bloccare la validazione degli altri report
            print(f"ATTENZIONE: Report {report_dict.get('id_report')} non salvato nel DB storico 'report_interventi'.")

    # 2. Infine, rimuovi i report dalla tabella di validazione
    report_ids_to_delete = [report['id_report'] for report in validated_data]
    if not delete_reports_by_ids(report_ids_to_delete):
        print("ERRORE CRITICO: I report sono stati salvati nel DB storico, ma non è stato possibile rimuoverli dalla coda di validazione.")
        return False

    return True

def salva_report_intervento(dati_report: dict) -> bool:
    """Salva un report di intervento validato nel database."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_report.keys())
            placeholders = ', '.join('?' for _ in dati_report)
            sql = f"INSERT INTO report_interventi ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_report.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio del report di intervento nel DB: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_validated_intervention_reports() -> pd.DataFrame:
    """Carica tutti i report di intervento validati dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM report_interventi ORDER BY data_riferimento_attivita DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dei report di intervento: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_validated_reports(table_name: str) -> pd.DataFrame:
    """
    Carica i dati validati da una tabella specifica (es. 'relazioni').
    """
    conn = get_db_connection()
    try:
        # Costruisce la query in modo sicuro per evitare SQL injection sul nome della tabella
        if table_name not in ['relazioni', 'report_validati']: # Whitelist delle tabelle consentite
            raise ValueError("Nome tabella non valido")

        query = f"SELECT * FROM {table_name} WHERE stato = 'Validata' ORDER BY data_intervento DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError, ValueError) as e:
        st.error(f"Errore nel caricamento dei dati dalla tabella {table_name}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def salva_storico_materiali(dati_richiesta: dict) -> bool:
    """Salva una richiesta di materiali approvata nello storico."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_richiesta.keys())
            placeholders = ', '.join('?' for _ in dati_richiesta)
            sql = f"INSERT INTO storico_richieste_materiali ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_richiesta.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio della richiesta materiali nello storico: {e}")
        return False
    finally:
        if conn:
            conn.close()

def salva_storico_assenze(dati_richiesta: dict) -> bool:
    """Salva una richiesta di assenza approvata nello storico."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_richiesta.keys())
            placeholders = ', '.join('?' for _ in dati_richiesta)
            sql = f"INSERT INTO storico_richieste_assenze ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_richiesta.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio della richiesta assenze nello storico: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_storico_richieste_materiali() -> pd.DataFrame:
    """Carica lo storico delle richieste di materiali dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM storico_richieste_materiali ORDER BY timestamp_approvazione DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dello storico materiali: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_storico_richieste_assenze() -> pd.DataFrame:
    """Carica lo storico delle richieste di assenze dal database."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM storico_richieste_assenze ORDER BY timestamp_approvazione DESC"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dello storico assenze: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def salva_relazione(dati_relazione: dict) -> bool:
    """Salva una nuova relazione nel database."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cols = ', '.join(f'"{k}"' for k in dati_relazione.keys())
            placeholders = ', '.join('?' for _ in dati_relazione)
            sql = f"INSERT INTO relazioni ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(dati_relazione.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio della relazione nel DB: {e}")
        return False
    finally:
        if conn:
            conn.close()
def get_validated_intervention_reports(matricola_tecnico: str = None) -> pd.DataFrame:
    """
    Carica i report di intervento validati dal database.
    Se matricola_tecnico è fornita, filtra per quel tecnico.
    """
    conn = get_db_connection()
    try:
        if matricola_tecnico:
            query = "SELECT * FROM report_interventi WHERE matricola_tecnico = ? ORDER BY data_riferimento_attivita DESC"
            df = pd.read_sql_query(query, conn, params=(matricola_tecnico,))
        else:
            query = "SELECT * FROM report_interventi ORDER BY data_riferimento_attivita DESC"
            df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dei report di intervento: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def save_table_data(df: pd.DataFrame, table_name: str):
    """Salva un DataFrame in una tabella del database, sostituendo i dati esistenti."""
    conn = get_db_connection()
    try:
        # Basic validation to prevent SQL injection on table_name
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")

        with conn:
            # Delete existing data
            conn.execute(f"DELETE FROM {table_name}")
            # Append new data
            df.to_sql(table_name, conn, if_exists='append', index=False)
        return True
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore durante il salvataggio dei dati nella tabella {table_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_table_data(table_name: str) -> pd.DataFrame:
    """Carica tutti i dati da una tabella specifica."""
    conn = get_db_connection()
    try:
        # Basic validation to prevent SQL injection on table_name
        if not table_name.isalnum() and '_' not in table_name:
             raise ValueError("Nome tabella non valido.")
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError, ValueError) as e:
        print(f"Errore nel caricare i dati dalla tabella {table_name}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_table_names() -> list:
    """Restituisce una lista con i nomi di tutte le tabelle nel database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    except sqlite3.Error as e:
        print(f"Errore nel recuperare i nomi delle tabelle: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_report_by_id(report_id: str, table_name: str) -> dict:
    """Recupera un singolo report da una tabella specifica per ID."""
    conn = get_db_connection()
    try:
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")
        query = f"SELECT * FROM {table_name} WHERE id_report = ?"
        cursor = conn.cursor()
        cursor.execute(query, (report_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore nel recuperare il report {report_id} da {table_name}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def delete_report_by_id(report_id: str, table_name: str) -> bool:
    """Cancella un singolo report da una tabella specifica per ID."""
    conn = get_db_connection()
    try:
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")
        with conn:
            query = f"DELETE FROM {table_name} WHERE id_report = ?"
            conn.execute(query, (report_id,))
        return True
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore durante la cancellazione del report {report_id} da {table_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def insert_report(report_data: dict, table_name: str) -> bool:
    """Inserisce i dati di un report in una tabella specifica."""
    conn = get_db_connection()
    try:
        if not table_name.isalnum() and '_' not in table_name:
            raise ValueError("Nome tabella non valido.")
        with conn:
            cols = ', '.join(f'"{k}"' for k in report_data.keys())
            placeholders = ', '.join('?' for _ in report_data)
            sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
            conn.execute(sql, list(report_data.values()))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'inserimento del report in {table_name}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def move_report_atomically(report_data: dict, source_table: str, dest_table: str) -> bool:
    """Sposta un report da una tabella all'altra in modo atomico."""
    conn = get_db_connection()
    try:
        if not all(isinstance(name, str) and (name.isalnum() or '_' in name) for name in [source_table, dest_table]):
            raise ValueError("Nomi delle tabelle non validi.")

        with conn:
            # 1. Delete from source
            delete_query = f"DELETE FROM {source_table} WHERE id_report = ?"
            conn.execute(delete_query, (report_data['id_report'],))

            # 2. Insert into destination
            cols = ', '.join(f'"{k}"' for k in report_data.keys())
            placeholders = ', '.join('?' for _ in report_data)
            insert_query = f"INSERT INTO {dest_table} ({cols}) VALUES ({placeholders})"
            conn.execute(insert_query, list(report_data.values()))
        return True
    except (sqlite3.Error, ValueError) as e:
        print(f"Errore durante lo spostamento atomico del report: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_unvalidated_reports_by_technician(matricola_tecnico: str) -> pd.DataFrame:
    """Carica i report inviati da un tecnico ma non ancora validati."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM report_da_validare WHERE matricola_tecnico = ? ORDER BY data_compilazione DESC"
        df = pd.read_sql_query(query, conn, params=(matricola_tecnico,))
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        st.error(f"Errore nel caricamento dei report non validati per il tecnico {matricola_tecnico}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()
