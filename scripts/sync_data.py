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

# Configurazione percorsi - Adattamento dinamico per Docker
IS_DOCKER = Path("/.dockerenv").exists()
NETWORK_ROOT = "/mnt/network" if IS_DOCKER else r"\\192.168.11.251\Database_Tecnico_SMI"
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
        logger.info(f"Tabella programmazione aggiornata: {count_new} nuovi PDL, {count_rimossi} PDL rimossi/corretti per il {data_str}.")
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
        # Escludiamo i file temporanei generati da Excel (iniziano con ~$)
        files = [f for f in net_giornaliere.glob("*.xlsm") if not f.name.startswith("~$")]
        
        for item in files:
            dest = loc_giornaliere / item.name
            needs_update = False
            
            if not dest.exists():
                needs_update = True
            else:
                try:
                    # In Docker con volumi montati, se dest e item sono hardlink/stesso file,
                    # shutil.copy2 fallirebbe con SameFileError. Evitiamo.
                    if item.resolve() == dest.resolve() or item.samefile(dest):
                        continue
                        
                    # Controlliamo sia la data di modifica che la dimensione
                    item_stat = item.stat()
                    dest_stat = dest.stat()
                    
                    if item_stat.st_mtime > dest_stat.st_mtime or item_stat.st_size != dest_stat.st_size:
                        needs_update = True
                except Exception:
                    # In caso di errori strani di stat, forziamo l'aggiornamento
                    needs_update = True

            if needs_update:
                try:
                    shutil.copy2(item, dest)
                    logger.info(f"File sincronizzato: {item.name}")
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
                if not dest.exists() or p.stat().st_mtime > dest.stat().st_mtime:
                    try:
                        shutil.copy2(p, dest)
                        logger.info(f"File radice sincronizzato: {f}")
                        files_updated = True
                    except Exception as e:
                        logger.error(f"Errore copia file radice {f}: {e}")
                break

    if not files_updated:
        logger.info("Nessun file aggiornato sulla rete. Salto l'estrazione dati.")
        logger.info("--- FINE SINCRONIZZAZIONE (NESSUNA MODIFICA) ---")
        sys.exit(0)

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
