import os
import re

files_to_update = [
    r"tests\unit\test_data_integrity.py",
    r"tests\unit\modules\test_db_reports_advanced.py",
    r"tests\unit\modules\test_db_requests_extended.py",
    r"tests\unit\modules\test_db_shifts.py",
    r"tests\unit\modules\test_db_reports.py",
    r"tests\unit\modules\test_db_shifts_extended.py",
    r"tests\unit\modules\test_db_users_complete.py",
    r"tests\unit\modules\test_db_users_extended.py",
    r"tests\unit\modules\test_db_system_extended.py",
    r"tests\unit\modules\test_communications_extended.py",
    r"tests\unit\modules\test_logic_market_advanced.py",
    r"tests\unit\modules\test_logic_market_deep_dive.py",
    r"tests\unit\modules\test_logic_oncall_advanced.py",
    r"tests\unit\core\test_db_advanced.py",
    r"tests\unit\modules\test_logic_shifts_extended.py",
    r"tests\unit\modules\test_notifications.py",
    r"tests\unit\modules\test_notifications_bulk.py",
    r"tests\unit\modules\test_notifications_logic.py",
    r"tests\integration\test_workflow_integration.py",
    r"tests\unit\modules\test_parsing_robustness.py",
    r"tests\unit\modules\test_reports_manager.py",
    r"tests\unit\modules\test_security_auth.py",
    r"tests\unit\modules\test_security_auth_audit.py",
]

# Moduli di produzione che devono essere aggiornati per includere DatabaseEngine
production_modules = [
    r"src\modules\reports_manager.py",
    r"src\modules\notifications.py",
    r"src\modules\auth.py",
    r"src\modules\shifts\logic_market.py",
    r"src\modules\shifts\logic_oncall.py",
    r"src\modules\database\db_reports.py",
    r"src\modules\database\db_requests.py",
    r"src\modules\database\db_shifts.py",
    r"src\modules\database\db_system.py",
    r"src\modules\database\db_users.py",
]

root = r"C:\Users\Coemi\Desktop\SCRIPT\report-attivita-app"

def update_production_file(file_path):
    full_path = os.path.join(root, file_path)
    if not os.path.exists(full_path):
        print(f"File non trovato: {full_path}")
        return

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Aggiungi import se manca
    if "from core.database import DatabaseEngine" not in content:
        # Trova un punto dopo gli import standard
        content = re.sub(r"(import .*?\n|from .*? import .*?\n)", r"\1from core.database import DatabaseEngine\n", content, count=1)
        # Pulisci duplicati se ne sono stati creati
        content = content.replace("from core.database import DatabaseEngine\nfrom core.database import DatabaseEngine\n", "from core.database import DatabaseEngine\n")

    # Sostituisci chiamate
    content = content.replace("get_db_connection()", "DatabaseEngine.get_connection()")
    
    # Rimuovi import vecchio se presente e non più usato (semplificato)
    content = content.replace("from modules.db_manager import get_db_connection", "")
    content = re.sub(r"from modules\..*? import .*?get_db_connection.*?\n", lambda m: m.group(0).replace("get_db_connection,", "").replace(", get_db_connection", "").replace("get_db_connection", ""), content)
    
    # Rimuovi righe di import vuote
    content = re.sub(r"from modules\..*? import \s*\n", "", content)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Aggiornato produzione: {file_path}")

def update_test_file(file_path):
    full_path = os.path.join(root, file_path)
    if not os.path.exists(full_path):
        print(f"File non trovato: {full_path}")
        return

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Sostituisci patch stringhe
    content = content.replace(".get_db_connection\"", ".DatabaseEngine.get_connection\"")
    content = content.replace(".get_db_connection\')", ".DatabaseEngine.get_connection\')")
    
    # Per mocker.patch
    content = content.replace(".get_db_connection,", ".DatabaseEngine.get_connection,")

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Aggiornato test: {file_path}")

# Esecuzione
for p in production_modules:
    update_production_file(p)

for t in files_to_update:
    update_test_file(t)

print("Refactoring completato.")
