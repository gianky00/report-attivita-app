"""
Modulo per l'invio asincrono di email tramite Outlook.
Utilizza un subprocess per interfacciarsi con le API COM di Windows senza bloccare Streamlit.
"""

import subprocess
import sys
import threading
from pathlib import Path

from src.core.logging import get_logger

logger = get_logger(__name__)


def _send_email_subprocess(subject: str, html_body: str):
    """
    Esegue lo script di invio email in un processo separato.
    """
    try:
        python_exe = sys.executable
        # Percorso assoluto allo script nella cartella scripts/
        script_path = (
            Path(__file__).parent.parent.parent / "scripts" / "send_email_subprocess.py"
        )

        if not script_path.exists():
            logger.error(f"Script di invio email non trovato: {script_path}")
            return

        command = [python_exe, str(script_path), subject, html_body]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            logger.info(f"Processo email completato per: {subject}")
        else:
            logger.error(
                f"Fallimento subprocess email ({result.returncode}): {result.stderr}"
            )

    except Exception as e:
        logger.error(
            f"Errore imprevisto durante il lancio del subprocess email: {e}",
            exc_info=True,
        )


def invia_email_con_outlook_async(subject: str, html_body: str):
    """
    Avvia l'invio dell'email in un thread separato per garantire la reattività della UI.
    """
    thread = threading.Thread(
        target=_send_email_subprocess,
        args=(subject, html_body),
        daemon=True,  # Il thread non blocca la chiusura dell'app
    )
    thread.start()
    logger.debug(f"Thread di invio email avviato per: {subject}")
