"""
Script subprocess per l'esecuzione di macro VBA in Excel.
Utilizzato per la sincronizzazione dei report attività nel database Excel centralizzato.
"""

import sys
from pathlib import Path

import pythoncom
import win32com.client as win32

# Aggiunge la cartella src al path per importare il core logging
sys.path.append(str(Path(__file__).parent.parent))
from src.core.logging import get_logger

logger = get_logger(__name__)


def run_macro():
    """Apre il workbook dei report ed esegue la macro di aggiornamento."""
    excel = None
    workbook = None
    try:
        # Percorso del file Excel (situato nella root, un livello sopra scripts/)
        excel_file_path = Path(__file__).parent.parent / "Database_Report_Attivita.xlsm"

        if not excel_file_path.exists():
            logger.error(f"File Excel non trovato: {excel_file_path}")
            sys.exit(1)

        pythoncom.CoInitialize()
        excel = win32.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False  # Evita popup bloccanti

        logger.info(f"Apertura workbook: {excel_file_path.name}...")
        workbook = excel.Workbooks.Open(str(excel_file_path.resolve()))

        logger.info("Esecuzione macro 'AggiornaRisposte'...")
        excel.Application.Run("AggiornaRisposte")

        workbook.Save()
        workbook.Close(SaveChanges=True)
        logger.info("Macro completata e file salvato con successo.")

    except Exception as e:
        logger.error(
            f"Eccezione durante l'esecuzione della macro Excel: {e}", exc_info=True
        )
        if excel:
            excel.Quit()
        sys.exit(1)

    finally:
        if excel:
            excel.Quit()
        # Rilascio risorse COM
        del workbook
        del excel
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    run_macro()
