import threading
import os

# --- Nome del Database ---
# Usato in tutta l'applicazione per connettersi al database SQLite.
DB_NAME = "schedario.db"

# --- Lock per la Concorrenza ---
# Un "semaforo" per prevenire che l'applicazione legga e scriva sul database
# contemporaneamente, evitando race conditions e corruzione dei dati.
EXCEL_LOCK = threading.Lock()

# --- Percorsi File Essenziali ---
# Definisce i percorsi per i file di dati principali usati dall'app.
PATH_KNOWLEDGE_CORE = "knowledge_core.json"
PATH_GIORNALIERA_BASE = "." # Assumiamo che i file "Giornaliera" siano nella root

# --- Funzioni Helper per i Percorsi (per coerenza) ---
# Queste funzioni forniscono un modo standard per ottenere i percorsi dei file.

def get_attivita_programmate_path():
    """Restituisce il percorso del file Excel delle attività programmate."""
    return "ATTIVITA_PROGRAMMATE.xlsm"

def get_gestionale_path():
    """Restituisce il percorso del file Excel gestionale."""
    return "Gestionale_Tecnici.xlsx"

def get_storico_db_path():
    """Restituisce il percorso del file storico JSON (deprecato ma mantenuto per compatibilità)."""
    return "storico_db.json"