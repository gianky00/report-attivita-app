
import threading
import subprocess
import sys

def _send_email_subprocess(subject, html_body):
    """
    Executes the email sending script in a separate process.
    """
    try:
        # We need to use the same Python executable that's running the Streamlit app.
        python_executable = sys.executable

        # Pass the subject and body as command-line arguments.
        # Using a list of arguments is safer than a single string.
        command = [python_executable, "send_email_subprocess.py", subject, html_body]

        # Execute the command. We capture the output for debugging.
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False  # We check the return code manually
        )

        if result.returncode == 0:
            print(f"Email sending process for '{subject}' completed successfully.")
            if result.stdout:
                print("Subprocess output:", result.stdout)
        else:
            # Log the error from the subprocess
            print(f"Error in email sending subprocess for '{subject}'.")
            if result.stderr:
                print("Subprocess error output:", result.stderr)
            with open("email_error.log", "a") as f:
                f.write(f"Subprocess failed with return code {result.returncode}.\n")
                f.write(f"Stderr: {result.stderr}\n")

    except FileNotFoundError:
        print("Error: 'send_email_subprocess.py' not found. Make sure the script is in the root directory.")
    except Exception as e:
        # Catch any other exceptions during the subprocess call
        print(f"An unexpected error occurred while trying to send email: {e}")
        with open("email_error.log", "a") as f:
            f.write(f"Python script exception: {e}\n")


def invia_email_con_outlook_async(subject, html_body):
    """
    Starts the email sending subprocess in a separate thread to avoid blocking the UI.
    """
    thread = threading.Thread(target=_send_email_subprocess, args=(subject, html_body))
    thread.start()
