import sqlite3
import pandas as pd
import os
import json

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

def create_validation_session(user_matricola: str, data: list) -> str:
    """Crea una nuova sessione di validazione per un utente, usando la matricola."""
    import uuid
    import datetime

    session_id = str(uuid.uuid4())
    created_at = datetime.datetime.now().isoformat()
    data_json = json.dumps(data)
    status = "active"

    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM validation_sessions WHERE user_matricola = ? AND status = 'active'", (user_matricola,))
            conn.execute(
                "INSERT INTO validation_sessions (session_id, user_matricola, created_at, data, status) VALUES (?, ?, ?, ?, ?)",
                (session_id, user_matricola, created_at, data_json, status)
            )
        return session_id
    except sqlite3.Error as e:
        print(f"Errore durante la creazione della sessione di validazione per {user_matricola}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_active_validation_session(user_matricola: str) -> dict:
    """Recupera la sessione di validazione attiva per una data matricola."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, data FROM validation_sessions WHERE user_matricola = ? AND status = 'active'", (user_matricola,))
        result = cursor.fetchone()

        if result:
            return {
                "session_id": result["session_id"],
                "data": json.loads(result["data"])
            }
        return None
    except (sqlite3.Error, json.JSONDecodeError) as e:
        print(f"Errore nel recuperare la sessione di validazione attiva per {user_matricola}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_validation_session_data(session_id: str, new_data: list):
    """Aggiorna i dati di una sessione di validazione esistente."""
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
    """Elimina una sessione di validazione."""
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
    """Recupera l'ultimo report per ogni attività in attesa di validazione, includendo la matricola."""
    conn = get_db_connection()
    reports_to_validate = []
    try:
        query = "SELECT PdL, Descrizione, Storico, db_last_modified FROM attivita_programmate WHERE db_last_modified IS NOT NULL ORDER BY db_last_modified DESC"
        cursor = conn.cursor()
        cursor.execute(query)
        activities = cursor.fetchall()

        for activity in activities:
            if activity['Storico']:
                try:
                    storico_list = json.loads(activity['Storico'])
                    if storico_list:
                        latest_report = storico_list[0]
                        reports_to_validate.append({
                            'PdL': activity['PdL'],
                            'Descrizione': activity['Descrizione'],
                            'Matricola': latest_report.get('Matricola', 'N/D'),
                            'Tecnico': latest_report.get('Tecnico', 'N/D'),
                            'Stato': latest_report.get('Stato', 'N/D'),
                            'Report': latest_report.get('Report', 'Nessun report.'),
                            'Data_Compilazione': latest_report.get('Data_Compilazione', activity['db_last_modified'])
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
    """Processa i report validati, aggiornandoli nel DB e marcandoli come validati."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            for report in validated_data:
                pdl = report.get('PdL')
                report_text = report.get('Report')
                new_status = report.get('Stato')
                compilation_date = report.get('Data_Compilazione')

                if not all([pdl, report_text, new_status, compilation_date]): continue

                cursor.execute("SELECT Storico FROM attivita_programmate WHERE PdL = ?", (pdl,))
                result = cursor.fetchone()
                if not result or not result['Storico']: continue

                storico_list = json.loads(result['Storico'])
                report_found_and_updated = False
                for i, storico_item in enumerate(storico_list):
                    if storico_item.get('Data_Compilazione') == compilation_date:
                        storico_list[i]['Report'] = report_text
                        storico_list[i]['Stato'] = new_status
                        report_found_and_updated = True
                        break

                if report_found_and_updated:
                    new_storico_json = json.dumps(storico_list)
                    cursor.execute(
                        "UPDATE attivita_programmate SET Storico = ?, Stato = ?, db_last_modified = NULL WHERE PdL = ?",
                        (new_storico_json, new_status, pdl)
                    )
        return True
    except sqlite3.Error as e:
        print(f"Errore durante il salvataggio dei report validati: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_interventions_for_technician(technician_matricola: str, start_date, end_date) -> pd.DataFrame:
    """Recupera tutti gli interventi per una data matricola in un intervallo di tempo."""
    conn = get_db_connection()
    try:
        query = """
        SELECT
          json_extract(value, '$.PdL') AS PdL,
          json_extract(value, '$.Descrizione') AS Descrizione,
          json_extract(value, '$.Stato') AS Stato,
          json_extract(value, '$.Report') AS Report,
          date(json_extract(value, '$.Data_Riferimento_dt')) AS Data_Riferimento_dt,
          json_extract(value, '$.Tecnico') AS Tecnico,
          json_extract(value, '$.Matricola') AS Matricola
        FROM
          attivita_programmate,
          json_each(attivita_programmate.Storico)
        WHERE
          Matricola = ? AND
          date(Data_Riferimento_dt) BETWEEN date(?) AND date(?)
        ORDER BY
          Data_Riferimento_dt DESC;
        """
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        df = pd.read_sql_query(query, conn, params=(technician_matricola, start_date_str, end_date_str))
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel recuperare gli interventi per matricola {technician_matricola}: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_technician_performance_data(start_date, end_date) -> pd.DataFrame:
    """Calcola le metriche di performance per i tecnici interrogando direttamente il DB e raggruppando per Matricola."""
    conn = get_db_connection()
    try:
        query = """
        SELECT
            Matricola,
            Tecnico,
            COUNT(*) AS "Totale Interventi",
            CAST(SUM(CASE WHEN Stato = 'TERMINATA' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS REAL) AS "Tasso Completamento (%)",
            AVG(julianday(Data_Compilazione) - julianday(Data_Riferimento_dt)) AS "Ritardo Medio Compilazione (gg)",
            SUM(CASE WHEN LENGTH(Report) < 20 THEN 1 ELSE 0 END) AS "Report Sbrigativi"
        FROM (
            SELECT
                json_extract(value, '$.Matricola') AS Matricola,
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
            Matricola IS NOT NULL AND
            date(Data_Riferimento_dt) BETWEEN date(?) AND date(?)
        GROUP BY
            Matricola, Tecnico
        ORDER BY
            "Totale Interventi" DESC;
        """
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        df = pd.read_sql_query(query, conn, params=(start_date_str, end_date_str))

        if not df.empty:
            df['Tasso Completamento (%)'] = df['Tasso Completamento (%)'].map('{:.1f}'.format)
            df['Ritardo Medio Compilazione (gg)'] = df['Ritardo Medio Compilazione (gg)'].map('{:.1f}'.format)
            # Usa il Nome Tecnico come indice per la visualizzazione in UI
            return df.set_index('Tecnico')

        return pd.DataFrame(columns=['Matricola', 'Totale Interventi', 'Tasso Completamento (%)', 'Ritardo Medio Compilazione (gg)', 'Report Sbrigativi']).set_index('Tecnico')

    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel calcolo delle performance dei tecnici: {e}")
        return pd.DataFrame(columns=['Matricola', 'Totale Interventi', 'Tasso Completamento (%)', 'Ritardo Medio Compilazione (gg)', 'Report Sbrigativi']).set_index('Tecnico')
    finally:
        if conn:
            conn.close()

def get_on_call_shifts_for_period(start_date, end_date) -> pd.DataFrame:
    """Carica i turni di reperibilità per un dato intervallo di date."""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM turni WHERE Tipo = 'Reperibilità' AND date(Data) BETWEEN date(?) AND date(?) ORDER BY Data ASC"
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare i turni di reperibilità: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_filtered_activities(filters: dict) -> pd.DataFrame:
    """Carica le attività programmate applicando i filtri specificati a livello di query."""
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
        if 'Storico' in df.columns:
            df['Storico'] = df['Storico'].apply(lambda x: json.loads(x) if x else [])
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Errore nel caricare le attività filtrate: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()