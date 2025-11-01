
import sys
import toml
import pythoncom
import win32com.client as win32
import os

def send_email(subject, html_body, attachment_path=None):
    """
    This function runs in a separate process to send an email via Outlook,
    avoiding COM threading issues with the main Streamlit application.
    """
    pythoncom.CoInitialize()
    outlook = None
    mail = None
    try:
        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)

        # Imposta i destinatari
        mail.To = "ciro.scaravelli@coemi.it"
        mail.CC = "francesco.millo@coemi.it"

        mail.Subject = subject

        # Per includere la firma, prima visualizziamo l'email e poi impostiamo il corpo
        # In questo modo Outlook aggiunge la firma predefinita
        mail.Display()

        # Ora che la firma è (presumibilmente) inserita, aggiungiamo il nostro corpo HTML prima della firma
        # Troviamo il tag <body> e inseriamo il nostro contenuto dopo di esso
        # Questo è un approccio comune per preservare la firma
        if mail.HTMLBody:
            signature_starts_at = mail.HTMLBody.find('<body')
            if signature_starts_at != -1:
                # Inserisci il corpo del testo dopo il tag body
                body_tag_end = mail.HTMLBody.find('>', signature_starts_at) + 1
                original_body_content = mail.HTMLBody[body_tag_end:]
                mail.HTMLBody = mail.HTMLBody[:body_tag_end] + html_body + original_body_content
            else:
                mail.HTMLBody = html_body + mail.HTMLBody
        else:
            mail.HTMLBody = html_body

        if attachment_path and os.path.exists(attachment_path):
            mail.Attachments.Add(os.path.abspath(attachment_path))

        mail.Save()
        # Non è necessario chiamare di nuovo Display() perché lo abbiamo già fatto

        print(f"Subprocess: Email draft '{subject}' created successfully.")

    except Exception as e:
        # Log the error to a file for better debugging
        with open("email_error.log", "a") as f:
            f.write(f"Error creating email draft: {e}\\n")
        print(f"Subprocess Error: Could not create email draft. Details logged to email_error.log.")

    finally:
        # Non rilasciare `mail` e `outlook` immediatamente
        # Lascia che Python li gestisca alla fine dello script
        # per evitare che la finestra di Outlook si chiuda
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python send_email_subprocess.py <subject> <body> [attachment_path]")
        sys.exit(1)

    subject_arg = sys.argv[1]
    body_arg = sys.argv[2]
    attachment_arg = sys.argv[3] if len(sys.argv) > 3 else None

    send_email(subject_arg, body_arg, attachment_arg)
