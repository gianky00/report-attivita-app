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


def validate_report(pdl: str):
    """
    Marca un report come validato impostando 'db_last_modified' a NULL.
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE attivita_programmate SET db_last_modified = NULL WHERE PdL = ?",
                (pdl,)
            )
        return True
    except sqlite3.Error as e:
        print(f"Errore durante la validazione del report per PdL {pdl}: {e}")
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