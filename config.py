import threading
import toml
import sys

# --- CARICAMENTO CONFIGURAZIONE ---
# Carica le configurazioni dal file 'secrets.toml'.
# Questo file è locale e non viene tracciato da Git per motivi di sicurezza.
# Assicurati di aver creato un file 'secrets.toml' a partire da 'secrets.toml.example'.

try:
    # Percorso unificato per la configurazione, standard per Streamlit
    secrets = toml.load(".streamlit/secrets.toml")
except FileNotFoundError:
    # Termina l'applicazione se il file di configurazione essenziale non è presente.
    # In un ambiente Streamlit, st.error() sarebbe meglio, ma questo file viene
    # importato prima che Streamlit sia necessariamente attivo.
    print("ERRORE CRITICO: File 'secrets.toml' non trovato. L'applicazione non può partire.")
    print("Per favore, crea il file 'secrets.toml' copiando 'secrets.toml.example' e inserendo i percorsi corretti.")
    sys.exit(1) # Esce dal programma

# --- PATHS ---
# I percorsi vengono ora letti in modo sicuro dal file di configurazione.
# Se una chiave non è presente nel file, il programma si fermerà con un errore chiaro.
try:
    PATH_STORICO_DB = secrets["path_storico_db"]
    PATH_GESTIONALE = secrets["path_gestionale"]
    PATH_GIORNALIERA_BASE = secrets["path_giornaliera_base"]
    PATH_ATTIVITA_PROGRAMMATE = secrets["path_attivita_programmate"]
except KeyError as e:
    print(f"ERRORE CRITICO: Chiave di configurazione mancante in 'secrets.toml': {e}")
    sys.exit(1)


# Percorso Knowledge Core (rimane locale al progetto)
PATH_KNOWLEDGE_CORE = "knowledge_core.json"


# --- SPREADSHEET & EMAIL ---
NOME_FOGLIO_RISPOSTE = secrets.get("nome_foglio_risposte", "Report Attività Giornaliera (Risposte)")
EMAIL_DESTINATARIO = "gianky.allegretti@gmail.com"
EMAIL_CC = "francesco.millo@coemi.it"

# --- THREADING LOCKS ---
EXCEL_LOCK = threading.Lock()
OUTLOOK_LOCK = threading.Lock()

# --- FUNZIONI HELPER PER I PERCORSI ---
# Aggiunte per compatibilità con il modulo data_manager.
def get_attivita_programmate_path():
    """Restituisce il percorso al file delle attività programmate."""
    return PATH_ATTIVITA_PROGRAMMATE

def get_storico_db_path():
    """Restituisce il percorso allo storico DB."""
    return PATH_STORICO_DB

def get_gestionale_path():
    """Restituisce il percorso al file gestionale."""
    return PATH_GESTIONALE