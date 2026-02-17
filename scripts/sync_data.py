"""
Script per la sincronizzazione dei dati dal server di rete alla cartella locale
e popolamento della tabella 'pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot' nel database SQLite.
"""

import datetime
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

# Configurazione percorsi - PERCORSO FORNITO DALL'UTENTE
NETWORK_ROOT = r"\\192.168.11.251\Database_Tecnico_SMI"
LOCAL_SYNC_DIR = Path(__file__).parent.parent / "data_sync"
DB_NAME = BASE_DIR / "report-attivita.db"
CURRENT_YEAR = datetime.date.today().year


def update_db_pdl_programmazione(attivita: list[dict], data_rif: datetime.date):
    """Aggiorna la tabella pdl_programmazione_syncrojob.SafeWorkProgrammazioneBot nel database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        timestamp = datetime.datetime.now().isoformat()
        data_str = data_rif.isoformat()
        
        count_new = 0
        for task in attivita:
            # Usiamo INSERT OR IGNORE per non sovrascrivere PDL che hanno già stati avanzati (INVIATO/VALIDATO)
            # Se il PDL per quel giorno/tecnico esiste già, non facciamo nulla (manteniamo lo stato corrente)
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
        logger.info(f"Tabella programmazione aggiornata: {count_new} nuovi PDL per il {data_str}.")
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

    # Sincronizzazione file Giornaliere
    net_giornaliere = network_path / "Giornaliere" / f"Giornaliere {CURRENT_YEAR}"
    loc_giornaliere = LOCAL_SYNC_DIR / "Giornaliere" / f"Giornaliere {CURRENT_YEAR}"

    if net_giornaliere.exists():
        loc_giornaliere.mkdir(parents=True, exist_ok=True)
        files = list(net_giornaliere.glob("*.xlsm"))
        
        for item in files:
            dest = loc_giornaliere / item.name
            if not dest.exists() or item.stat().st_mtime > dest.stat().st_mtime:
                try:
                    shutil.copy2(item, dest)
                    logger.info(f"File sincronizzato: {item.name}")
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
                if not dest.exists() or p.stat().st_mtime > dest.stat().st_mtime:
                    shutil.copy2(p, dest)
                    logger.info(f"File radice sincronizzato: {f}")
                break

    # --- ESTRAZIONE PDL NELLA TABELLA DI PROGRAMMAZIONE ---
    logger.info("Estrazione PDL in corso...")
    # Estraiamo per Oggi e Ieri
    for i in range(2):
        d = today - datetime.timedelta(days=i)
        attivita = estrai_tutte_le_attivita_giorno(d.day, d.month, d.year)
        if attivita:
            update_db_pdl_programmazione(attivita, d)

    logger.info("--- FINE SINCRONIZZAZIONE ---")
    return True


if __name__ == "__main__":
    sync()
