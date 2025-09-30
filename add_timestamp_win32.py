import os
import sys

try:
    # Importazione chiave per controllare l'applicazione Excel
    import win32com.client
except ImportError:
    print("ERRORE: La libreria 'pywin32' non è stata trovata.")
    print("Per favore, installala dal tuo terminale (es. CMD o PowerShell) con il comando:")
    print("pip install pywin32")
    sys.exit(1)

# --- CONFIGURAZIONE ---
# Usa una stringa raw (r"...") per gestire correttamente i backslash nei percorsi di rete Windows.
# ATTENZIONE: Assicurati che questo percorso sia corretto e accessibile dalla macchina Windows su cui eseguirai lo script.
FILE_PATH = r"\\192.168.11.251\Database_Tecnico_SMI\cartella strumentale condivisa\ALLEGRETTI\ATTIVITA_PROGRAMMATE.xlsm"

# Fogli da modificare
SHEETS_TO_MODIFY = ["A1", "A2", "A3", "BLENDING", "CTE"]

# Dettagli della colonna da aggiungere
COLUMN_NAME = "DataUltimaModifica"
HEADER_ROW = 3
DATA_START_ROW = 4
TIMESTAMP_VALUE = "2025-09-30 20:00:00"

def add_timestamp_with_win32():
    """
    Aggiunge in modo sicuro una colonna di timestamp a un file .xlsm utilizzando
    l'automazione dell'applicazione Excel per garantire l'integrità del file.
    """
    if not os.path.exists(FILE_PATH):
        print(f"ERRORE: Il file specificato non è stato trovato al percorso:")
        print(FILE_PATH)
        print("Controlla che il percorso di rete sia corretto e che tu abbia accesso.")
        return

    excel = None
    workbook = None

    print("Avvio dell'automazione di Excel. Questo potrebbe richiedere alcuni istanti...")

    # Il blocco try...finally è fondamentale per garantire che l'applicazione Excel
    # venga chiusa correttamente anche in caso di errori.
    try:
        # Avvia una nuova istanza di Excel in background
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False  # L'applicazione non sarà visibile
        excel.DisplayAlerts = False  # Non mostrare pop-up di Excel

        # Apri il workbook
        print(f"Apertura del file: {os.path.basename(FILE_PATH)}...")
        workbook = excel.Workbooks.Open(FILE_PATH)

        # Disabilita l'aggiornamento dello schermo per velocizzare le operazioni
        excel.ScreenUpdating = False

        # Itera sui fogli da modificare
        for sheet_name in SHEETS_TO_MODIFY:
            try:
                sheet = workbook.Sheets(sheet_name)
                print(f"\nAnalisi del foglio: '{sheet_name}'...")

                # --- Verifica se la colonna esiste già ---
                col_exists = False
                for cell in sheet.Rows(HEADER_ROW).Cells:
                    if cell.Value == COLUMN_NAME:
                        col_exists = True
                        break

                if col_exists:
                    print(f"La colonna '{COLUMN_NAME}' esiste già. Salto questo foglio.")
                    continue

                # --- Aggiunta della colonna e dei dati ---
                # Trova la prima colonna libera sulla riga dell'intestazione
                new_col_idx = sheet.Cells(HEADER_ROW, sheet.Columns.Count).End(-4159).Column + 1 # -4159 è xlToLeft

                # Aggiungi l'intestazione
                sheet.Cells(HEADER_ROW, new_col_idx).Value = COLUMN_NAME
                print(f"Aggiunta intestazione '{COLUMN_NAME}' alla colonna {new_col_idx}.")

                # Trova l'ultima riga con dati nella colonna A (o 1)
                last_row = sheet.Cells(sheet.Rows.Count, 1).End(-4162).Row # -4162 è xlUp

                # Popola la nuova colonna con il timestamp
                # Usiamo un range per un'operazione più veloce invece di un ciclo riga per riga
                if last_row >= DATA_START_ROW:
                    target_range = sheet.Range(
                        sheet.Cells(DATA_START_ROW, new_col_idx),
                        sheet.Cells(last_row, new_col_idx)
                    )
                    target_range.Value = TIMESTAMP_VALUE
                    print(f"Popolate {last_row - DATA_START_ROW + 1} righe con il timestamp.")
                else:
                    print("Nessuna riga di dati trovata da popolare.")

            except Exception as e:
                print(f"ATTENZIONE: Impossibile processare il foglio '{sheet_name}'. Errore: {e}")

        # Salva il workbook con le modifiche
        print("\nSalvataggio del file in corso... (potrebbe richiedere tempo)")
        workbook.Save()
        print("File salvato con successo!")

    except Exception as e:
        print(f"\nERRORE CRITICO durante l'automazione di Excel: {e}")
        print("Le modifiche potrebbero non essere state salvate.")
    finally:
        # --- Pulizia ---
        # Questo è il passaggio più importante per evitare processi Excel "fantasma"
        if workbook:
            workbook.Close(SaveChanges=False) # Chiudi senza salvare di nuovo
        if excel:
            excel.Quit()

        # Rilascia le risorse COM
        workbook = None
        excel = None
        print("\nOperazione completata. Risorse di Excel rilasciate.")


if __name__ == "__main__":
    add_timestamp_with_win32()