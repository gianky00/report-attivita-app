
import sqlite3
import datetime

DB_NAME = "schedario.db"

def add_test_data():
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Add a user to the 'contatti' table
        cursor.execute("""
            INSERT OR IGNORE INTO contatti (Matricola, "Nome Cognome", Ruolo, PasswordHash)
            VALUES (?, ?, ?, ?)
        """, ('admin', 'Admin User', 'Amministratore', '$2b$12$E6e.gJ4.e/9nJ0.FlzAF8.NO.d.4.e.a.a.a.a.a.a.a.a.a'))

        # Add an intervention report to the 'report_interventi' table
        cursor.execute("""
            INSERT INTO report_interventi (
                id_report, pdl, descrizione_attivita, matricola_tecnico,
                nome_tecnico, stato_attivita, testo_report, data_compilazione,
                data_riferimento_attivita, timestamp_validazione
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'test_report_01',
            'PM:55966005',
            'T98 - PROGRC CONTROLLO FUNZIONALE',
            'admin',
            'Benito Tarsicio',
            'TERMINATA',
            'NESSUNA ANOMALIA RISCONTRATA',
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '2025-10-20',
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
        print("Test data added successfully.")
    except sqlite3.Error as e:
        print(f"Error adding test data: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_test_data()
