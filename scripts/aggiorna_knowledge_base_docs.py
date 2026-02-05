"""
Script di sincronizzazione documenti per la Knowledge Base dell'IA.
Copia i file .docx dalle cartelle di rete alla directory locale del progetto.
"""

import shutil
import sys
from pathlib import Path

# Aggiunge la cartella src al path per importare il core logging
sys.path.append(str(Path(__file__).parent.parent / "src"))
from core.logging import get_logger

logger = get_logger(__name__)

# --- CONFIGURAZIONE ---
# Percorso di rete per le relazioni di reperibilità
BASE_NET_PATH = r"\\192.168.11.251\Database_Tecnico_SMI"
REL_PATH = r"Contabilita' strumentale\Relazioni di reperibilita'"
SOURCE_DIR = Path(BASE_NET_PATH) / REL_PATH
DEST_DIR = Path(__file__).parent.parent / "knowledge_base_docs"
FILE_EXTENSIONS = (".docx", ".doc")


def sync_files(src_path: Path, dest_path: Path):
    """
    Sincronizza i file tra sorgente e destinazione, aggiornando solo i modificati.
    """
    try:
        dest_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Impossibile creare cartella destinazione {dest_path}: {e}")
        return

    if not src_path.exists():
        logger.error(f"Percorso di rete non accessibile o inesistente: {src_path}")
        return

    logger.info(f"Sincronizzazione KB avviata da {src_path}")

    copied, skipped, errors = 0, 0, 0

    for src_file in src_path.rglob("*"):
        if src_file.is_file() and src_file.suffix.lower() in FILE_EXTENSIONS:
            relative = src_file.relative_to(src_path)
            dest_file = dest_path / relative
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                if (
                    not dest_file.exists()
                    or src_file.stat().st_mtime > dest_file.stat().st_mtime
                ):
                    shutil.copy2(src_file, dest_file)
                    copied += 1
                    logger.debug(f"Copiato: {relative}")
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Errore copia {relative}: {e}")
                errors += 1

    logger.info("--- Riepilogo Sincronizzazione ---")
    logger.info(f"Aggiornati: {copied} | Saltati: {skipped} | Errori: {errors}")


if __name__ == "__main__":
    sync_files(SOURCE_DIR, DEST_DIR)
