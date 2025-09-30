import threading

# --- Nome del Database ---
# Usato in tutta l'applicazione per connettersi al database SQLite.
DB_NAME = "schedario.db"

# --- Lock per la Concorrenza ---
# Un "semaforo" per prevenire che l'applicazione legga e scriva sul database
# contemporaneamente, evitando race conditions e corruzione dei dati.
EXCEL_LOCK = threading.Lock()