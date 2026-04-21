import os
import re

production_modules = [
    r"src\modules\database\db_reports.py",
    r"src\modules\database\db_requests.py",
    r"src\modules\database\db_shifts.py",
    r"src\modules\database\db_system.py",
    r"src\modules\database\db_users.py",
]

root = r"C:\Users\Coemi\Desktop\SCRIPT\report-attivita-app"

def fix_production_file(file_path):
    full_path = os.path.join(root, file_path)
    if not os.path.exists(full_path):
        return

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Rimuovi la definizione errata della funzione wrapper
    content = re.sub(r"def DatabaseEngine\.get_connection\(\) -> sqlite3\.Connection:\n\s+\"\"\"Restituisce una connessione al database core\.\"\"\"\n\s+return DatabaseEngine\.get_connection\(\)\n\n", "", content)
    
    # Se per qualche motivo è rimasta una definizione di get_db_connection che non è stata catturata bene o è stata storpiata
    content = re.sub(r"def get_db_connection\(\) -> sqlite3\.Connection:\n\s+\"\"\"Restituisce una connessione al database core\.\"\"\"\n\s+return DatabaseEngine\.get_connection\(\)\n\n", "", content)

    # Assicurati che non ci siano riferimenti a get_db_connection() residui nelle chiamate
    content = content.replace("get_db_connection()", "DatabaseEngine.get_connection()")

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Corretto: {file_path}")

for p in production_modules:
    fix_production_file(p)

print("Correzione completata.")
