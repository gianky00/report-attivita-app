import threading
import os

# --- PATHS ---
# Questa logica permette di usare percorsi diversi per l'ambiente di produzione e quello di sviluppo.
# Se esiste un file/directory locale con il nome di sviluppo, viene usato quello.
# Altrimenti, viene usato il percorso di produzione.

# Percorso Gestionale
PROD_PATH_GESTIONALE = r'C:\Users\Coemi\Desktop\SCRIPT\progetto_questionario_attivita\Gestionale_Tecnici.xlsx'
DEV_PATH_GESTIONALE = 'Gestionale_Tecnici.xlsx'
PATH_GESTIONALE = DEV_PATH_GESTIONALE if os.path.exists(DEV_PATH_GESTIONALE) else PROD_PATH_GESTIONALE

# Percorso Storico DB
PROD_PATH_STORICO_DB = r'\\192.168.11.251\Database_Tecnico_SMI\cartella strumentale condivisa\ALLEGRETTI\Database_Report_Attivita.xlsm'
DEV_PATH_STORICO_DB = 'Database_Report_Attivita.xlsm'
PATH_STORICO_DB = DEV_PATH_STORICO_DB if os.path.exists(DEV_PATH_STORICO_DB) else PROD_PATH_STORICO_DB

# Percorso Knowledge Core (solo locale)
PATH_KNOWLEDGE_CORE = "knowledge_core.json"

# Percorso Giornaliere
PROD_PATH_GIORNALIERA_BASE = r'\\192.168.11.251\Database_Tecnico_SMI\Giornaliere\Giornaliere 2025'
DEV_PATH_GIORNALIERA_BASE = "Giornaliere" # Directory fittizia
PATH_GIORNALIERA_BASE = DEV_PATH_GIORNALIERA_BASE if os.path.exists(DEV_PATH_GIORNALIERA_BASE) else PROD_PATH_GIORNALIERA_BASE


# --- SPREADSHEET & EMAIL ---
NOME_FOGLIO_RISPOSTE = "Report Attività Giornaliera (Risposte)"
EMAIL_DESTINATARIO = "gianky.allegretti@gmail.com"
EMAIL_CC = "francesco.millo@coemi.it"

# --- THREADING LOCKS ---
EXCEL_LOCK = threading.Lock()
OUTLOOK_LOCK = threading.Lock()
