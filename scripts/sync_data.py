"""
Script per la sincronizzazione dei dati dal server di rete alla cartella locale
e popolamento della tabella 'pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot' nel database SQLite.
"""

import datetime
import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path

# Aggiunge la cartella src al path per importare i moduli interni
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR / "src"))

import config
from modules.importers.excel_giornaliera import estrai_tutte_le_attivita_giorno
from core.logging import get_logger

logger = get_logger(__name__)

# Configurazione percorsi - Adattamento dinamico per Docker
IS_DOCKER = Path("/.dockerenv").exists()
NETWORK_ROOT = "/mnt/network" if IS_DOCKER else r"\\192.168.11.251\Database_Tecnico_SMI"
LOCAL_SYNC_DIR = Path(__file__).parent.parent / "data_sync"
DB_NAME = BASE_DIR / "report-attivita.db"
CURRENT_YEAR = datetime.date.today().year

def get_file_hash(path: Path) -> str:
    """Calcola l'hash MD5 di un file per verificare cambiamenti reali nel contenuto."""
    hasher = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""

def update_db_pdl_programmazione(attivita: list[dict], data_rif: datetime.date):
    """Aggiorna la tabella pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot nel database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        timestamp = datetime.datetime.now().isoformat()
        data_str = data_rif.isoformat()
        
        # 1. Recupera tutte le attività PIANIFICATE attualmente a DB per questa data
        cursor.execute("""
            SELECT pdl, tecnico_assegnato 
            FROM "pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot"
            WHERE data_intervento = ? AND stato = 'PIANIFICATO'
        """, (data_str,))
        
        db_pianificati = {(row[0], row[1]) for row in cursor.fetchall()}
        
        # 2. Ottieni l'elenco delle attività correnti dall'Excel
        excel_correnti = {(task['pdl'], task['tecnico_assegnato']) for task in attivita}
        
        # 3. Identifica le attività da rimuovere (presenti nel DB come PIANIFICATO, ma rimosse dall'Excel)
        da_rimuovere = db_pianificati - excel_correnti
        
        count_rimossi = 0
        for pdl, tecnico in da_rimuovere:
            cursor.execute("""
                DELETE FROM "pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot"
                WHERE pdl = ? AND data_intervento = ? AND tecnico_assegnato = ? AND stato = 'PIANIFICATO'
            """, (pdl, data_str, tecnico))
            count_rimossi += cursor.rowcount
        
        count_new = 0
        for task in attivita:
            cursor.execute("""
                INSERT OR IGNORE INTO "pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot" 
                (pdl, data_intervento, tecnico_assegnato, descrizione, team, stato, tipo, timestamp_pianificazione)
                VALUES (?, ?, ?, ?, ?, 'PIANIFICATO', 'ORDINARIO', ?)
            """, (
                task['pdl'], 
                data_str, 
                task['tecnico_assegnato'], 
                task['attivita'], 
                task['team'], 
                timestamp
            ))
            if cursor.rowcount > 0:
                count_new += 1
                
        conn.commit()
        if count_new > 0 or count_rimossi > 0:
            logger.info(f"Tabella programmazione aggiornata: {count_new} nuovi PDL, {count_rimossi} PDL rimossi per il {data_str}.")
    except Exception as e:
        logger.error(f"Errore durante l'aggiornamento della tabella programmazione: {e}")
    finally:
        if conn:
            conn.close()

def sync():
    logger.info("--- AVVIO SINCRONIZZAZIONE ---")
    
    network_path = Path(NETWORK_ROOT)
    if not network_path.exists():
        logger.error(f"Server Rete {NETWORK_ROOT} non raggiungibile.")
        return False

    LOCAL_SYNC_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today()
    
    files_updated = False

    # Sincronizzazione file Giornaliere
    net_giornaliere = network_path / "Giornaliere" / f"Giornaliere {CURRENT_YEAR}"
    loc_giornaliere = LOCAL_SYNC_DIR / "Giornaliere" / f"Giornaliere {CURRENT_YEAR}"

    if net_giornaliere.exists():
        loc_giornaliere.mkdir(parents=True, exist_ok=True)
        files = [f for f in net_giornaliere.glob("*.xlsm") if not f.name.startswith("~$")]
        
        for item in files:
            dest = loc_giornaliere / item.name
            needs_update = False
            
            if not dest.exists():
                needs_update = True
            else:
                # Confronto Hash invece di mtime per evitare falsi positivi
                if get_file_hash(item) != get_file_hash(dest):
                    needs_update = True

            if needs_update:
                try:
                    shutil.copy2(item, dest)
                    logger.info(f"File sincronizzato (Cambio contenuto): {item.name}")
                    files_updated = True
                except Exception as e:
                    logger.error(f"Errore copia {item.name}: {e}")
    else:
        logger.warning(f"Cartella remota Giornaliere non trovata.")

    # Sincronizzazione file radice
    for f in ("Database_Report_Attivita.xlsm", "ATTIVITA_PROGRAMMATE.xlsm"):
        paths = [
            network_path / "cartella strumentale condivisa" / "ALLEGRETTI" / f,
            network_path / f,
        ]
        for p in paths:
            if p.exists():
                dest = LOCAL_SYNC_DIR / f
                if not dest.exists() or get_file_hash(p) != get_file_hash(dest):
                    try:
                        shutil.copy2(p, dest)
                        logger.info(f"File radice sincronizzato: {f}")
                        files_updated = True
                    except Exception as e:
                        logger.error(f"Errore copia file radice {f}: {e}")
                break

    # Se non ci sono file aggiornati, controlliamo se il DB ha già i dati futuri necessari
    # In caso contrario, forziamo comunque l'estrazione per popolare i giorni mancanti.
    # Questo risolve il problema del "0" in programmazione se il file era già locale ma non estratto.
    
    logger.info("Verifica estrazione PDL...")
    # Estraiamo per un range temporale (2 gg passati, Oggi, 5 gg futuri)
    for i in range(-5, 3):
        d = today - datetime.timedelta(days=i)
        attivita = estrai_tutte_le_attivita_giorno(d.day, d.month, d.year)
        if attivita:
            update_db_pdl_programmazione(attivita, d)

    logger.info("--- FINE SINCRONIZZAZIONE ---")
    return True

if __name__ == "__main__":
    sync()
