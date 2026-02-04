"""
Script subprocess per la gestione dell'invio email e creazione bozze via Outlook COM.
Utilizzato per evitare blocchi del thread principale di Streamlit.
"""

import re
import sys
from pathlib import Path

import pythoncom
import win32com.client as win32

# Aggiunge la cartella src al path per importare il core logging
sys.path.append(str(Path(__file__).parent.parent))
from src.core.logging import get_logger

logger = get_logger(__name__)


def remove_signature(html_body: str) -> str:
    """Rimuove la firma predefinita dal corpo dell'email per evitare duplicazioni."""
    signature_patterns = [
        re.compile(
            r"<p><strong>Gianky Allegretti</strong><br>Direttore Tecnico</p>",
            re.IGNORECASE,
        ),
        re.compile(r"Gianky Allegretti\s*<br>\s*Direttore Tecnico", re.IGNORECASE),
    ]
    for pattern in signature_patterns:
        html_body = pattern.sub("", html_body)
    return html_body


def send_email(
    subject: str,
    html_body: str,
    attachment_path: str | None = None,
    is_pdf_export: bool = False,
):
    """Interfaccia con Outlook per l'invio o la visualizzazione di email."""
    pythoncom.CoInitialize()
    try:
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)

        # 1. Pulizia corpo
        html_body = remove_signature(html_body)

        # 2. Destinatari
        if is_pdf_export:
            mail.To = "ciro.scaravelli@coemi.it"
            mail.CC = "francesco.millo@coemi.it"
        else:
            mail.To = "francesco.millo@coemi.it; gianky.allegretti@gmail.com"

        mail.Subject = subject
        mail.HTMLBody = html_body

        # 3. Allegato
        if attachment_path:
            path_obj = Path(attachment_path).resolve()
            if path_obj.exists():
                mail.Attachments.Add(str(path_obj))
            else:
                logger.error(f"Allegato non trovato: {path_obj}")

        # 4. Azione finale
        if is_pdf_export:
            mail.Save()
            mail.Display()
            logger.info(f"Bozza email '{subject}' creata ed aperta in Outlook.")
        else:
            mail.Send()
            logger.info(f"Email '{subject}' inviata con successo.")

    except Exception as e:
        logger.error(f"Errore critico durante l'invio email: {e}", exc_info=True)
        sys.exit(1)
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python send_email_subprocess.py <subject> <body> "
            "[attachment_path] [--pdf-export]"
        )
        sys.exit(1)

    subject_arg = sys.argv[1]
    body_arg = sys.argv[2]
    attachment_arg = None
    is_pdf_export_arg = False

    # Parsing argomenti
    if len(sys.argv) > 3:
        if sys.argv[3] == "--pdf-export":
            is_pdf_export_arg = True
        else:
            attachment_arg = sys.argv[3]
            if len(sys.argv) > 4 and sys.argv[4] == "--pdf-export":
                is_pdf_export_arg = True

    send_email(subject_arg, body_arg, attachment_arg, is_pdf_export_arg)
