import threading

# Lock per l'accesso al file Excel
EXCEL_LOCK = threading.Lock()
OUTLOOK_LOCK = threading.Lock()

# Costanti non segrete
PATH_KNOWLEDGE_CORE = "knowledge_core.json"
