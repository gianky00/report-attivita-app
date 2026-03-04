
import sqlite3
from pathlib import Path

DB_NAME = Path("report-attivita.db")

def add_team_column():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    tables = ["report_da_validare", "report_interventi"]
    for table in tables:
        try:
            print(f"Aggiornamento tabella {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN team TEXT;")
            print(f"Colonna 'team' aggiunta a {table}.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Colonna 'team' già presente in {table}.")
            else:
                print(f"Errore su {table}: {e}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    add_team_column()
