
import sys
import toml
import pythoncom
import win32com.client as win32

def send_email(subject, html_body):
    """
    This function runs in a separate process to send an email via Outlook,
    avoiding COM threading issues with the main Streamlit application.
    """
    pythoncom.CoInitialize()
    outlook = None
    mail = None
    try:
        # Load email configuration
        secrets = toml.load(".streamlit/secrets.toml")
        email_to = secrets.get("email_destinatario", "")
        email_cc_string = secrets.get("email_cc", "")
        email_cc = [email.strip() for email in email_cc_string.split(',') if email.strip()]

        if not email_to:
            print("Error: Email recipient is not configured in secrets.toml.")
            return

        outlook = win32.Dispatch('outlook.application')
        mail = outlook.CreateItem(0)
        mail.To = email_to
        mail.CC = ";".join(email_cc)  # Outlook expects a semicolon-separated string for CC
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.Send()
        print(f"Subprocess: Email '{subject}' sent successfully.")
    except Exception as e:
        # Log the error to a file for better debugging
        with open("email_error.log", "a") as f:
            f.write(f"Error sending email: {e}\n")
        print(f"Subprocess Error: Could not send email. Details logged to email_error.log.")
    finally:
        if mail:
            del mail
        if outlook:
            del outlook
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python send_email_subprocess.py <subject> <body>")
        sys.exit(1)

    subject_arg = sys.argv[1]
    body_arg = sys.argv[2]
    send_email(subject_arg, body_arg)
