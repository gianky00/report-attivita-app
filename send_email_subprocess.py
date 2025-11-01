
import sys
import toml
import pythoncom
import win32com.client as win32
import os
import re

def remove_signature(html_body):
    """Rimuove una firma specifica dal corpo di un'email HTML."""
    # Definisci la firma da rimuovere, sia come testo semplice che come HTML
    signature_patterns = [
        re.compile(r'<p><strong>Gianky Allegretti</strong><br>Direttore Tecnico</p>', re.IGNORECASE),
        re.compile(r'Gianky Allegretti\s*<br>\s*Direttore Tecnico', re.IGNORECASE)
    ]

    for pattern in signature_patterns:
        html_body = pattern.sub('', html_body)

    return html_body

def send_email(subject, html_body, attachment_path=None, is_pdf_export=False):
    """
    Gestisce l'invio o la creazione di bozze di email tramite Outlook.
    """
    pythoncom.CoInitialize()
    outlook = None
    mail = None
    try:
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)

        # 1. Modifica Corpo Email: Rimuovi la firma
        html_body = remove_signature(html_body)

        # 2. Logica di Invio
        if is_pdf_export:
            # Scenario A: Creazione Bozza (Esportazione PDF)
            mail.To = "ciro.scaravelli@coemi.it"
            mail.CC = "francesco.millo@coemi.it"
        else:
            # Scenario B: Invio Diretto (Tutti gli altri casi)
            mail.To = "francesco.millo@coemi.it; gianky.allegretti@gmail.com"

        mail.Subject = subject
        mail.HTMLBody = html_body

        if attachment_path and os.path.exists(attachment_path):
            mail.Attachments.Add(os.path.abspath(attachment_path))

        if is_pdf_export:
            mail.Save()
            mail.Display() # Mostra la bozza
            print(f"Subprocess: Email draft '{subject}' created successfully.")
        else:
            mail.Send()
            print(f"Subprocess: Email '{subject}' sent successfully.")

    except Exception as e:
        with open("email_error.log", "a") as f:
            f.write(f"Error processing email: {e}\\n")
        print(f"Subprocess Error: Could not process email. Details logged to email_error.log.")

    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python send_email_subprocess.py <subject> <body> [attachment_path] [--pdf-export]")
        sys.exit(1)

    subject_arg = sys.argv[1]
    body_arg = sys.argv[2]
    attachment_arg = None
    is_pdf_export_arg = False

    # Parsing degli argomenti opzionali
    if len(sys.argv) > 3:
        if sys.argv[3] == '--pdf-export':
            is_pdf_export_arg = True
        else:
            attachment_arg = sys.argv[3]
            if len(sys.argv) > 4 and sys.argv[4] == '--pdf-export':
                is_pdf_export_arg = True

    send_email(subject_arg, body_arg, attachment_arg, is_pdf_export_arg)
