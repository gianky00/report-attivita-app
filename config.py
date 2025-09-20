import threading

# --- PATHS ---
# I percorsi di rete e locali sono stati commentati per permettere l'esecuzione in un ambiente di sviluppo standard.
# Verranno usati file fittizi o locali.
# PATH_GIORNALIERA_BASE = r'\\192.168.11.251\Database_Tecnico_SMI\Giornaliere\Giornaliere 2025'
PATH_GESTIONALE = 'Gestionale_Tecnici.xlsx' # Usiamo un percorso relativo
# PATH_STORICO_DB = r'\\192.168.11.251\Database_Tecnico_SMI\cartella strumentale condivisa\ALLEGRETTI\Database_Report_Attivita.xlsm'
PATH_STORICO_DB = 'Database_Report_Attivita.xlsm' # Usiamo un percorso relativo
PATH_KNOWLEDGE_CORE = "knowledge_core.json"
PATH_GIORNALIERA_BASE = "Giornaliere" # Usiamo una directory locale per i file giornalieri

# --- SPREADSHEET & EMAIL ---
NOME_FOGLIO_RISPOSTE = "Report Attività Giornaliera (Risposte)"
EMAIL_DESTINATARIO = "gianky.allegretti@gmail.com"
EMAIL_CC = "francesco.millo@coemi.it"

# --- THREADING LOCKS ---
EXCEL_LOCK = threading.Lock()
OUTLOOK_LOCK = threading.Lock()
