import sqlite3
import os

DB_NAME = r"C:\Users\Coemi\Desktop\SCRIPT\report-attivita-app\report-attivita.db"

def restore_validated_status():
    if not os.path.exists(DB_NAME):
        print(f"Database non trovato in: {DB_NAME}")
        return

    conn = sqlite3.connect(DB_NAME)
    pdls = ['573319/C', '573877/C', '573584/C']
    
    try:
        with conn:
            # Recuperiamo il nome della tabella di programmazione
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%pdl_programmazione%';")
            prog_table = cursor.fetchone()[0]
            
            for pdl_id in pdls:
                # Ripristiniamo lo stato a VALIDATO come richiesto
                sql = f'UPDATE "{prog_table}" SET stato = "VALIDATO" WHERE pdl = ? OR pdl = ?'
                cursor = conn.execute(sql, (pdl_id, f"PdL {pdl_id}"))
                print(f"PdL {pdl_id}: Stato ripristinato a VALIDATO ({cursor.rowcount} righe)")
                
        print("Ripristino completato con successo.")
    except Exception as e:
        print(f"Errore: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    restore_validated_status()
