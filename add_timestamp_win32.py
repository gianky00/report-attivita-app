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

# Nome del file Excel da modificare
FILE_NAME = "ATTIVITA_PROGRAMMATE.xlsm"

# Costruisce il percorso completo del file, assumendo che si trovi
# nella stessa cartella dello script Python.
# __file__ è una variabile speciale che contiene il percorso dello script corrente.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(BASE_DIR, FILE_NAME)


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
    l'automazione dell'applicazione Excel. Gestisce i fogli di lavoro protetti
    rimuovendo e riapplicando la protezione.
    """
    if not os.path.exists(FILE_PATH):
        print(f"ERRORE: Il file '{FILE_NAME}' non è stato trovato nella cartella dello script.")
        print(f"Percorso cercato: {FILE_PATH}")
        print("Assicurati che il file si trovi nella stessa directory del programma Python.")
        return

    excel = None
    workbook = None

    print("Avvio dell'automazione di Excel. Questo potrebbe richiedere alcuni istanti...")

    # Il blocco try...finally è fondamentale per garantire che l'applicazione Excel
    # venga chiusa correttamente anche in caso di errori.
    try:
        # Avvia una nuova istanza di Excel in background
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        # Apri il workbook
        print(f"Apertura del file: {os.path.basename(FILE_PATH)}...")
        workbook = excel.Workbooks.Open(FILE_PATH)
        excel.ScreenUpdating = False # Disabilita l'aggiornamento dello schermo per velocità

        # Itera sui fogli da modificare
        for sheet_name in SHEETS_TO_MODIFY:
            sheet = None # Resetta la variabile sheet per ogni ciclo
            try:
                sheet = workbook.Sheets(sheet_name)
                print(f"\nAnalisi del foglio: '{sheet_name}'...")

                # --- CORREZIONE CHIAVE: GESTIONE DELLA PROTEZIONE ---
                # 1. Rimuovi la protezione per permettere le modifiche
                # Se i fogli hanno una password, usala qui:
                # sheet.Unprotect(Password="la_tua_password") # AGGIUNGI PASSWORD QUI
                sheet.Unprotect()
                print(f"Protezione temporaneamente rimossa dal foglio '{sheet_name}'.")

                # --- Verifica se la colonna esiste già ---
                col_exists = False
                header_range = sheet.Range(sheet.Cells(HEADER_ROW, 1), sheet.Cells(HEADER_ROW, sheet.Columns.Count).End(-4159)) # -4159 è xlToLeft
                for cell in header_range:
                    if cell.Value == COLUMN_NAME:
                        col_exists = True
                        break

                if col_exists:
                    print(f"La colonna '{COLUMN_NAME}' esiste già. Salto questo foglio.")
                    # Passiamo alla sezione 'finally' per ri-proteggere il foglio
                    continue

                # --- Aggiunta della colonna e dei dati ---
                new_col_idx = sheet.Cells(HEADER_ROW, sheet.Columns.Count).End(-4159).Column + 1
                sheet.Cells(HEADER_ROW, new_col_idx).Value = COLUMN_NAME
                print(f"Aggiunta intestazione '{COLUMN_NAME}' alla colonna {new_col_idx}.")

                last_row = sheet.Cells(sheet.Rows.Count, 1).End(-4162).Row # -4162 è xlUp

                if last_row >= DATA_START_ROW:
                    target_range = sheet.Range(
                        sheet.Cells(DATA_START_ROW, new_col_idx),
                        sheet.Cells(last_row, new_col_idx)
                    )
                    target_range.Value = TIMESTAMP_VALUE
                    # Questa riga ora funzionerà perché il foglio non è protetto
                    target_range.NumberFormat = "dd/mm/yyyy hh:mm:ss"
                    print(f"Popolate {last_row - DATA_START_ROW + 1} righe con il timestamp.")
                else:
                    print("Nessuna riga di dati trovata da popolare.")

            except Exception as e:
                # Stampa un errore specifico se qualcosa va storto durante la modifica
                print(f"ATTENZIONE: Impossibile processare il foglio '{sheet_name}'. Errore: {e}")
            finally:
                # --- CORREZIONE CHIAVE: RIPRISTINO DELLA PROTEZIONE ---
                # 2. Questo blocco viene eseguito SEMPRE (sia in caso di successo che di errore),
                # garantendo che il foglio venga ri-protetto.
                if sheet:
                    # Se i fogli avevano una password, ri-proteggili con la stessa password:
                    # sheet.Protect(Password="la_tua_password") # AGGIUNGI PASSWORD QUI
                    sheet.Protect()
                    print(f"Protezione ripristinata sul foglio '{sheet_name}'.")

        print("\nSalvataggio del file in corso... (potrebbe richiedere tempo)")
        workbook.Save()
        print("File salvato con successo!")

    except Exception as e:
        print(f"\nERRORE CRITICO durante l'automazione di Excel: {e}")
        print("Le modifiche potrebbero non essere state salvate.")
    finally:
        # --- Pulizia finale per evitare processi Excel "fantasma" ---
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