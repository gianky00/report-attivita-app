import sqlite3
import pandas as pd
import os

DB_NAME = "schedario.db"

def get_db_connection():
    """Crea e restituisce una connessione al database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Permette l'accesso ai dati per nome di colonna
    return conn

def get_shifts_by_type(shift_type: str) -> pd.DataFrame:
    """
    Carica i turni di un tipo specifico direttamente dal database.

    Args:
        shift_type (str): Il tipo di turno da caricare (es. 'Assistenza', 'Straordinario').

    Returns:
        pd.DataFrame: Un DataFrame contenente solo i turni del tipo specificato.
    """
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

# --- NUOVE FUNZIONI PER LA GESTIONE DELLE SESSIONI DI VALIDAZIONE ---

def create_validation_session(user_name: str, data: list) -> str:
    """
    Crea una nuova sessione di validazione per un utente.
    Se esiste già una sessione attiva per l'utente, la sovrascrive.

    Args:
        user_name (str): Il nome dell'utente che avvia la sessione.
        data (list): La lista di dizionari dei report da validare.

    Returns:
        str: L'ID della sessione creata.
    """
    import uuid
    import json
    import datetime

    session_id = str(uuid.uuid4())
    created_at = datetime.datetime.now().isoformat()
    data_json = json.dumps(data)
    status = "active"

    conn = get_db_connection()
    try:
        with conn:
            # Rimuove eventuali vecchie sessioni attive per lo stesso utente
            conn.execute("DELETE FROM validation_sessions WHERE user_name = ? AND status = 'active'", (user_name,))
            # Inserisce la nuova sessione
            conn.execute(
                "INSERT INTO validation_sessions (session_id, user_name, created_at, data, status) VALUES (?, ?, ?, ?, ?)",
                (session_id, user_name, created_at, data_json, status)
            )
        return session_id
    except sqlite3.Error as e:
        print(f"Errore durante la creazione della sessione di validazione per {user_name}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_active_validation_session(user_name: str) -> dict:
    """
    Recupera la sessione di validazione attiva per un dato utente.

    Args:
        user_name (str): Il nome dell'utente.

    Returns:
        dict: I dati della sessione (incluso l'ID e i dati dei report), o None se non trovata.
    """
    import json
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, data FROM validation_sessions WHERE user_name = ? AND status = 'active'", (user_name,))
        result = cursor.fetchone()

        if result:
            return {
                "session_id": result["session_id"],
                "data": json.loads(result["data"])
            }
        return None
    except (sqlite3.Error, json.JSONDecodeError) as e:
        print(f"Errore nel recuperare la sessione di validazione attiva per {user_name}: {e}")
        return None
    finally:
        if conn:
            conn.close()


def update_validation_session_data(session_id: str, new_data: list):
    """
    Aggiorna i dati di una sessione di validazione esistente.

    Args:
        session_id (str): L'ID della sessione da aggiornare.
        new_data (list): La nuova lista di report (come lista di dizionari).

    Returns:
        bool: True se l'aggiornamento ha avuto successo, altrimenti False.
    """
    import json
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE validation_sessions SET data = ? WHERE session_id = ?",
                (json.dumps(new_data), session_id)
            )
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiornamento della sessione {session_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def delete_validation_session(session_id: str):
    """
    Elimina una sessione di validazione. Da usare dopo aver validato o cancellato.

    Args:
        session_id (str): L'ID della sessione da eliminare.

    Returns:
        bool: True se l'eliminazione ha avuto successo, altrimenti False.
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM validation_sessions WHERE session_id = ?", (session_id,))
        return True
    except sqlite3.Error as e:
        print(f"Errore durante l'eliminazione della sessione {session_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_unvalidated_reports():
    """
    Recupera l'ultimo report per ogni attività in attesa di validazione.
    Un report è considerato "in attesa" se `db_last_modified` non è NULL.
    """
    import json
    conn = get_db_connection()
    reports_to_validate = []
    try:
        query = """
            SELECT PdL, Descrizione, Storico, db_last_modified
            FROM attivita_programmate
            WHERE db_last_modified IS NOT NULL
            ORDER BY db_last_modified DESC
        """
        cursor = conn.cursor()
        cursor.execute(query)
        activities = cursor.fetchall()

        for activity in activities:
            pdl = activity['PdL']
            descrizione_attivita = activity['Descrizione']
            storico_json = activity['Storico']
            mod_time = activity['db_last_modified']

            if storico_json:
                try:
                    storico_list = json.loads(storico_json)
                    if storico_list:
                        latest_report = storico_list[0]
                        reports_to_validate.append({
                            'PdL': pdl,
                            'Descrizione': descrizione_attivita,
                            'Tecnico': latest_report.get('Tecnico', 'N/D'),
                            'Stato': latest_report.get('Stato', 'N/D'),
                            'Report': latest_report.get('Report', 'Nessun report.'),
                            'Data_Compilazione': latest_report.get('Data_Compilazione', mod_time)
                        })
                except json.JSONDecodeError:
                    continue
        return reports_to_validate
    except sqlite3.Error as e:
        print(f"Errore nel recuperare i report da validare: {e}")
        return []
    finally:
        if conn:
            conn.close()


def process_and_commit_validated_reports(validated_data: list):
    """
    Processa i report validati, aggiornandoli nel DB e marcandoli come validati.
    Questa funzione è atomica: o tutti i report vengono aggiornati, o nessuno.

    Args:
        validated_data (list): Una lista di dizionari, dove ogni dizionario
                               rappresenta un report validato (e potenzialmente modificato).
    """
    import json
    conn = get_db_connection()
    try:
        with conn: # Inizia una transazione
            cursor = conn.cursor()
            for report in validated_data:
                pdl = report.get('PdL')
                report_text = report.get('Report')
                new_status = report.get('Stato')
                compilation_date = report.get('Data_Compilazione')

                if not all([pdl, report_text, new_status, compilation_date]):
                    print(f"Skipping report due to missing data: {report}")
                    continue

                # 1. Leggi lo storico attuale
                cursor.execute("SELECT Storico FROM attivita_programmate WHERE PdL = ?", (pdl,))
                result = cursor.fetchone()
                if not result or not result['Storico']:
                    continue

                storico_list = json.loads(result['Storico'])

                # 2. Trova e aggiorna il report specifico nello storico
                report_found_and_updated = False
                for i, storico_item in enumerate(storico_list):
                    if storico_item.get('Data_Compilazione') == compilation_date:
                        storico_list[i]['Report'] = report_text
                        storico_list[i]['Stato'] = new_status
                        report_found_and_updated = True
                        break

                # 3. Se il report è stato aggiornato, salva le modifiche e azzera il flag
                if report_found_and_updated:
                    new_storico_json = json.dumps(storico_list)
                    cursor.execute(
                        "UPDATE attivita_programmate SET Storico = ?, Stato = ?, db_last_modified = NULL WHERE PdL = ?",
                        (new_storico_json, new_status, pdl)
                    )
        return True # Se la transazione ha successo
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio dei report validati: {e}")
        # La transazione verrà automaticamente annullata dal blocco 'with'
        return False
    finally:
        if conn:
            conn.close()

def get_interventions_for_technician(technician_name: str, start_date, end_date) -> pd.DataFrame:
    """
    Recupera tutti gli interventi per un dato tecnico in un intervallo di tempo,
    estraendo i dati dal campo JSON 'Storico'.
    """
    conn = get_db_connection()
    try:
        # Query per estrarre e filtrare i dati dal JSON
        query = """
        SELECT
          json_extract(value, '$.PdL') AS PdL,
          json_extract(value, '$.Descrizione') AS Descrizione,
          json_extract(value, '$.Stato') AS Stato,
          json_extract(value, '$.Report') AS Report,
          date(json_extract(value, '$.Data_Riferimento_dt')) AS Data_Riferimento_dt,
          json_extract(value, '$.Tecnico') AS Tecnico
        FROM
          attivita_programmate,
          json_each(attivita_programmate.Storico)
        WHERE
          Tecnico = ? AND
          date(Data_Riferimento_dt) BETWEEN date(?) AND date(?)
        ORDER BY
          Data_Riferimento_dt DESC;
        """
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        df = pd.read_sql_query(query, conn, params=(technician_name, start_date_str, end_date_str))
        return df

    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel recuperare gli interventi per {technician_name}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_technician_performance_data(start_date, end_date) -> pd.DataFrame:
    """
    Calcola le metriche di performance per i tecnici interrogando direttamente il DB.
    Utilizza json_each per espandere lo storico JSON e aggregare i risultati.
    """
    conn = get_db_connection()
    try:
        query = """
        SELECT
            Tecnico,
            COUNT(*) AS "Totale Interventi",
            CAST(SUM(CASE WHEN Stato = 'TERMINATA' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS REAL) AS "Tasso Completamento (%)",
            AVG(julianday(Data_Compilazione) - julianday(Data_Riferimento_dt)) AS "Ritardo Medio Compilazione (gg)",
            SUM(CASE WHEN LENGTH(Report) < 20 THEN 1 ELSE 0 END) AS "Report Sbrigativi"
        FROM (
            SELECT
                json_extract(value, '$.Tecnico') AS Tecnico,
                json_extract(value, '$.Stato') AS Stato,
                json_extract(value, '$.Report') AS Report,
                json_extract(value, '$.Data_Riferimento_dt') AS Data_Riferimento_dt,
                json_extract(value, '$.Data_Compilazione') AS Data_Compilazione
            FROM
                attivita_programmate,
                json_each(attivita_programmate.Storico)
        )
        WHERE
            Tecnico IS NOT NULL AND
            date(Data_Riferimento_dt) BETWEEN date(?) AND date(?)
        GROUP BY
            Tecnico
        ORDER BY
            "Totale Interventi" DESC;
        """
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        df = pd.read_sql_query(query, conn, params=(start_date_str, end_date_str))

        if not df.empty:
            df['Tasso Completamento (%)'] = df['Tasso Completamento (%)'].map('{:.1f}'.format)
            df['Ritardo Medio Compilazione (gg)'] = df['Ritardo Medio Compilazione (gg)'].map('{:.1f}'.format)

        return df.set_index('Tecnico')

    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel calcolo delle performance dei tecnici: {e}")
        return pd.DataFrame(columns=['Totale Interventi', 'Tasso Completamento (%)', 'Ritardo Medio Compilazione (gg)', 'Report Sbrigativi']).set_index('Tecnico')
    finally:
        if conn:
            conn.close()

def get_on_call_shifts_for_period(start_date, end_date) -> pd.DataFrame:
    """
    Carica i turni di reperibilità per un dato intervallo di date.
    """
    conn = get_db_connection()
    try:
        query = """
            SELECT * FROM turni
            WHERE Tipo = 'Reperibilità' AND date(Data) BETWEEN date(?) AND date(?)
            ORDER BY Data ASC
        """
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare i turni di reperibilità: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_filtered_activities(filters: dict) -> pd.DataFrame:
    """
    Carica le attività programmate applicando i filtri specificati a livello di query.

    Args:
        filters (dict): Un dizionario con i filtri da applicare.
                        Chiavi possibili: 'tcl', 'area', 'stato', 'pdl_search', 'day_filter'.

    Returns:
        pd.DataFrame: Un DataFrame con le attività filtrate.
    """
    conn = get_db_connection()
    base_query = "SELECT * FROM attivita_programmate"
    conditions = []
    params = []

    if filters.get('tcl'):
        placeholders = ','.join('?' for _ in filters['tcl'])
        conditions.append(f"TCL IN ({placeholders})")
        params.extend(filters['tcl'])

    if filters.get('area'):
        placeholders = ','.join('?' for _ in filters['area'])
        conditions.append(f"Area IN ({placeholders})")
        params.extend(filters['area'])

    if filters.get('stato'):
        placeholders = ','.join('?' for _ in filters['stato'])
        conditions.append(f"Stato IN ({placeholders})")
        params.extend(filters['stato'])

    if filters.get('pdl_search'):
        conditions.append("PdL LIKE ?")
        params.append(f"%{filters['pdl_search']}%")

    if filters.get('day_filter'):
        day_conditions = []
        for day in filters['day_filter']:
            day_conditions.append("GiorniProgrammati LIKE ?")
            params.append(f"%{day}%")
        if day_conditions:
            conditions.append(f"({' OR '.join(day_conditions)})")

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    try:
        df = pd.read_sql_query(base_query, conn, params=params)
        # La colonna 'Storico' è JSON, va parsata dopo il caricamento
        if 'Storico' in df.columns:
            import json
            df['Storico'] = df['Storico'].apply(lambda x: json.loads(x) if x else [])
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare le attività filtrate: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()