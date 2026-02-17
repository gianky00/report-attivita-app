"""
Script per l'indicizzazione dello storico schede di manutenzione.
Scansiona ricorsivamente la cartella dell'archivio e salva i metadati nel database.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

# Configurazione percorsi
ARCHIVE_ROOT = r"D:\PC ALLEGRETTI COEMI\STORICO SCHEDE\Archivio Schede Elaborate"
DB_PATH = Path(__file__).parent.parent / "report-attivita.db"


def index_archive():
    """Scansiona la cartella e popola il database con i metadati dei file."""
    archive_path = Path(ARCHIVE_ROOT)
    if not archive_path.exists():
        print(f"ERRORE: Il percorso {ARCHIVE_ROOT} non esiste.")
        return

    print(f"Inizio scansione di: {ARCHIVE_ROOT}...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Pulizia tabella esistente per re-indicizzazione completa (opzionale, ma sicuro per la prima volta)
    # cursor.execute("DELETE FROM maintenance_archive")

    count = 0
    batch_size = 1000
    entries = []

    for root, _, files in os.walk(ARCHIVE_ROOT):
        for file in files:
            if file.endswith((".xls", ".xlsx", ".xlsm")) and not file.startswith("~$"):
                full_path = os.path.join(root, file)
                try:
                    stats = Path(full_path).stat()
                    last_mod = datetime.fromtimestamp(stats.st_mtime).isoformat()

                    # Tentativo di estrarre anno e mese dal percorso
                    # Struttura attesa: ...\2024\01 - GENNAIO\file.xls
                    parts = Path(full_path).parts
                    year = ""
                    month = ""

                    # Cerca una parte che somigli a un anno (4 cifre)
                    for part in parts:
                        if part.isdigit() and len(part) == 4:
                            year = part
                        if " - " in part and any(
                            m in part.upper()
                            for m in (
                                "GENNAIO",
                                "FEBBRAIO",
                                "MARZO",
                                "APRILE",
                                "MAGGIO",
                                "GIUGNO",
                                "LUGLIO",
                                "AGOSTO",
                                "SETTEMBRE",
                                "OTTOBRE",
                                "NOVEMBRE",
                                "DICEMBRE",
                            )
                        ):
                            month = part

                    entries.append((file, full_path, year, month, last_mod))
                    count += 1

                    if len(entries) >= batch_size:
                        cursor.executemany(
                            "INSERT INTO maintenance_archive (filename, full_path, year, month, last_modified) VALUES (?, ?, ?, ?, ?)",
                            entries,
                        )
                        conn.commit()
                        entries = []
                        print(f"Indicizzati {count} file...")
                except Exception as e:
                    print(f"Errore con il file {full_path}: {e}")

    # Inserisce gli ultimi rimasti
    if entries:
        cursor.executemany(
            "INSERT INTO maintenance_archive (filename, full_path, year, month, last_modified) VALUES (?, ?, ?, ?, ?)",
            entries,
        )
        conn.commit()

    conn.close()
    print(f"Scansione completata. Totale file indicizzati: {count}")


if __name__ == "__main__":
    index_archive()
