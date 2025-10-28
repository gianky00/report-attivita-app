
import threading
import config

try:
    import pythoncom
    import win32com.client as win32
    outlook_enabled = True
except ImportError:
    outlook_enabled = False
    pythoncom = None
    win32 = None

def _invia_email_con_outlook_backend(subject, html_body):
    """Funzione sicura per essere eseguita in un thread, gestisce CoInitialize."""
    if not outlook_enabled:
        print("ATTENZIONE: Modulo pywin32 non trovato. Invio email disabilitato.")
        return

    pythoncom.CoInitialize()
    outlook = None
    mail = None
    try:
        with config.OUTLOOK_LOCK:
            outlook = win32.Dispatch('outlook.application')
            mail = outlook.CreateItem(0)
            mail.To = config.EMAIL_DESTINATARIO
            mail.CC = config.EMAIL_CC
            mail.Subject = subject
            mail.HTMLBody = html_body
            mail.Send()
            print(f"Email '{subject}' inviata con successo in background.")
    except Exception as e:
        print(f"ATTENZIONE: Impossibile inviare l'email con Outlook in background: {e}.")
    finally:
        # Rilascia esplicitamente gli oggetti COM
        if mail:
            del mail
        if outlook:
            del outlook
        pythoncom.CoUninitialize()

def invia_email_con_outlook_async(subject, html_body):
    """Avvia l'invio dell'email in un thread separato per non bloccare l'UI."""
    thread = threading.Thread(target=_invia_email_con_outlook_backend, args=(subject, html_body))
    thread.start()
