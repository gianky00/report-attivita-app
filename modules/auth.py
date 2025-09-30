import pandas as pd
import bcrypt
import pyotp

# --- Funzioni 2FA ---

def generate_2fa_secret():
    """Genera una nuova chiave segreta per la 2FA."""
    return pyotp.random_base32()

def get_provisioning_uri(username, secret):
    """
    Genera l'URI di provisioning per il QR code.
    L'emittente (issuer_name) può essere il nome della tua azienda o dell'app.
    """
    # Rimuovi spazi e caratteri speciali dal nome utente per l'URI
    safe_username = "".join(c for c in username if c.isalnum())
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=safe_username,
        issuer_name="AppManutenzioneSMI"
    )

def verify_2fa_code(secret, code):
    """Verifica un codice 2FA fornito dall'utente."""
    if not secret or not code:
        return False
    try:
        totp = pyotp.totp.TOTP(secret)
        return totp.verify(code)
    except Exception:
        return False


# --- Funzione di Autenticazione Principale ---

def authenticate_user(matricola, password, df_contatti):
    """
    Autentica un utente tramite Matricola e gestisce il flusso 2FA.
    Questa è la nuova logica robusta.

    Returns:
        tuple: (status, data) dove lo status può essere:
               - 'FIRST_LOGIN_SETUP': L'utente esiste ma non ha una password. `data` = (nome_completo, ruolo, password_fornisca)
               - '2FA_REQUIRED': Password corretta, serve il codice 2FA. `data` = nome_completo
               - '2FA_SETUP_REQUIRED': Password corretta, serve configurare la 2FA. `data` = (nome_completo, ruolo)
               - 'FAILED': Credenziali non valide. `data` = None
    """
    if df_contatti is None or df_contatti.empty or not matricola or not password:
        return 'FAILED', None

    # Cerca l'utente direttamente tramite Matricola (case-insensitive)
    user_row_series = df_contatti[df_contatti['Matricola'].str.lower() == str(matricola).lower()]

    if user_row_series.empty:
        return 'FAILED', None # Utente non trovato

    user_row = user_row_series.iloc[0]
    nome_completo = str(user_row['Nome Cognome']).strip()
    ruolo = user_row.get('Ruolo', 'Tecnico')
    password_bytes = str(password).encode('utf-8')

    # --- Logica di autenticazione ---

    # 1. Caso speciale: primo login in assoluto (PasswordHash è vuoto)
    # Controlliamo se 'PasswordHash' non esiste, è None, o una stringa vuota.
    has_hash = 'PasswordHash' in user_row and pd.notna(user_row['PasswordHash']) and user_row['PasswordHash']
    has_plain_password = 'Password' in user_row and pd.notna(user_row['Password']) and user_row['Password']

    if not has_hash and not has_plain_password:
        # Questo è il primo login. L'utente ha fornito una password che dobbiamo impostare.
        return 'FIRST_LOGIN_SETUP', (nome_completo, ruolo, password)

    # 2. Autenticazione Standard
    password_valid = False
    if has_hash:
        hashed_password_bytes = str(user_row['PasswordHash']).encode('utf-8')
        if bcrypt.checkpw(password_bytes, hashed_password_bytes):
            password_valid = True
    elif has_plain_password: # Fallback al vecchio sistema
        if str(password) == str(user_row['Password']):
            password_valid = True

    if not password_valid:
        return 'FAILED', None

    # --- Gestione 2FA ---
    # Se la password è valida, controlla se la 2FA è configurata.
    if '2FA_Secret' in user_row and pd.notna(user_row['2FA_Secret']) and user_row['2FA_Secret']:
        return '2FA_REQUIRED', nome_completo
    else:
        # Se la 2FA non è configurata, l'utente deve impostarla.
        return '2FA_SETUP_REQUIRED', (nome_completo, ruolo)

def log_access_attempt(gestionale_data, username, status):
    """
    Registra un tentativo di accesso nella cronologia (DataFrame-based).
    """
    import datetime
    import pandas as pd

    # Assicura che il DataFrame dei log esista
    if 'access_logs' not in gestionale_data or not isinstance(gestionale_data.get('access_logs'), pd.DataFrame):
        logs_df = pd.DataFrame(columns=["timestamp", "username", "status"])
    else:
        logs_df = gestionale_data['access_logs']

    # Crea il nuovo record di log come un DataFrame
    new_log_entry_df = pd.DataFrame([{
        "timestamp": datetime.datetime.now().isoformat(),
        "username": username,
        "status": status,
    }])

    # Concatena il nuovo log al DataFrame esistente, gestendo il caso di DataFrame vuoto
    if logs_df.empty:
        gestionale_data['access_logs'] = new_log_entry_df
    else:
        gestionale_data['access_logs'] = pd.concat([logs_df, new_log_entry_df], ignore_index=True)
