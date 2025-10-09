import pandas as pd
import os
import warnings

# Sopprime il warning specifico di openpyxl relativo alla "Print area"
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl.reader.workbook",
    message="Print area cannot be set to Defined name: .*."
)

# --- CONFIGURAZIONE ---
EXCEL_FILE = "Gestionale_Tecnici.xlsx"

# Definisce lo schema completo che il file Excel dovrebbe avere.
# Le colonne sono definite come dovrebbero essere nel file Excel,
# prima di qualsiasi trasformazione (es. usando 'Richiedente' invece di 'Richiedente_Matricola').
FULL_SCHEMA = {
    "Contatti": ["Matricola", "Nome Cognome", "Ruolo", "PasswordHash", "Link Attività", "2FA_Secret"],
    "Turni": ["ID_Turno", "Descrizione", "Data", "OrarioInizio", "OrarioFine", "PostiTecnico", "PostiAiutante", "Tipo"],
    "Prenotazioni": ["ID_Prenotazione", "ID_Turno", "Nome Cognome", "RuoloOccupato", "Timestamp"],
    "Sostituzioni": ["ID_Richiesta", "ID_Turno", "Richiedente", "Ricevente", "Timestamp"],
    "Notifiche": ["ID_Notifica", "Timestamp", "Destinatario", "Messaggio", "Stato", "Link_Azione"],
    "Bacheca": ["ID_Bacheca", "ID_Turno", "Tecnico_Originale", "Ruolo_Originale", "Timestamp_Pubblicazione", "Stato", "Tecnico_Subentrante", "Timestamp_Assegnazione"],
    "Richieste Materiali": ["ID_Richiesta", "Richiedente", "Timestamp", "Stato", "Dettagli"],
    "Richieste Assenze": ["ID_Richiesta", "Richiedente", "Timestamp", "Tipo_Assenza", "Data_Inizio", "Data_Fine", "Note", "Stato"],
    "Access Logs": ["timestamp", "username", "status"]
}

def populate_excel_file():
    """
    Assicura che il file Gestionale_Tecnici.xlsx contenga tutti i fogli e le intestazioni
    necessarie, preservando i dati esistenti.
    """
    print(f"Avvio della procedura di popolamento per '{EXCEL_FILE}'...")

    # Passo 1: Leggere tutti i fogli esistenti in memoria per preservare i dati.
    try:
        if os.path.exists(EXCEL_FILE):
            existing_sheets = pd.read_excel(EXCEL_FILE, sheet_name=None)
            print(f"Trovati {len(existing_sheets)} fogli esistenti: {list(existing_sheets.keys())}")
        else:
            existing_sheets = {}
            print(f"File '{EXCEL_FILE}' non trovato. Verrà creato da zero.")

    except Exception as e:
        print(f"Errore durante la lettura del file Excel '{EXCEL_FILE}': {e}")
        print("L'operazione non può continuare per non rischiare la corruzione dei dati.")
        return

    # Passo 2: Aggiungere i fogli mancanti con le relative intestazioni.
    sheets_to_write = existing_sheets.copy()
    sheet_added = False

    for sheet_name, columns in FULL_SCHEMA.items():
        if sheet_name not in sheets_to_write:
            print(f"-> Foglio mancante '{sheet_name}'. Creazione in corso con le intestazioni corrette.")
            sheets_to_write[sheet_name] = pd.DataFrame(columns=columns)
            sheet_added = True

    if not sheet_added:
        print("Nessun foglio mancante. Il file è già strutturalmente completo.")
        return

    # Passo 3: Scrivere tutti i fogli (vecchi e nuovi) nel file in un unico passaggio.
    # Questo è il modo più sicuro per evitare la corruzione del file.
    try:
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            for sheet_name, df in sheets_to_write.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"\nFile '{EXCEL_FILE}' aggiornato con successo!")
        print("Tutti i fogli richiesti e le relative intestazioni sono ora presenti.")

    except Exception as e:
        print(f"\nErrore critico durante la scrittura del file Excel: {e}")
        print("Il file potrebbe non essere stato aggiornato correttamente.")


if __name__ == "__main__":
    populate_excel_file()