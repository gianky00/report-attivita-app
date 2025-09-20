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

def authenticate_user(username, password, df_contatti):
    """
    Autentica un utente e gestisce il flusso 2FA.

    Returns:
        tuple: (status, data) dove lo status può essere:
               - 'SUCCESS': Login completo. data = (nome_completo, ruolo)
               - '2FA_REQUIRED': Password corretta, serve il codice 2FA. data = nome_completo
               - '2FA_SETUP_REQUIRED': Password corretta, serve configurare la 2FA. data = (nome_completo, ruolo)
               - 'FAILED': Credenziali non valide. data = None
    """
    if df_contatti is None or df_contatti.empty or password is None:
        return 'FAILED', None

    user_row = None
    # Trova la riga dell'utente in base al nome utente fornito
    for _, riga in df_contatti.iterrows():
        nome_completo = str(riga['Nome Cognome']).strip()
        user_param_corretto = nome_completo.split()[-1]
        if "Garro" in nome_completo:
            user_param_corretto = "Garro L"

        if username.lower() == user_param_corretto.lower():
            user_row = riga
            break

    if user_row is None:
        return 'FAILED', None # Utente non trovato

    # --- Logica di autenticazione ---
    password_bytes = str(password).encode('utf-8')
    nome_completo = str(user_row['Nome Cognome']).strip()
    ruolo = user_row.get('Ruolo', 'Tecnico')

    password_valid = False

    # 1. Prova con il nuovo sistema di hash
    if 'PasswordHash' in user_row and pd.notna(user_row['PasswordHash']):
        hashed_password_bytes = str(user_row['PasswordHash']).encode('utf-8')
        if bcrypt.checkpw(password_bytes, hashed_password_bytes):
            password_valid = True

    # 2. Fallback al vecchio sistema con password in chiaro
    if not password_valid and 'Password' in user_row and pd.notna(user_row['Password']):
        if str(password) == str(user_row['Password']):
            password_valid = True

    if not password_valid:
        return 'FAILED', None

    # --- Gestione 2FA ---
    # Se la password è valida, controlla se la 2FA è configurata.
    if '2FA_Secret' in user_row and pd.notna(user_row['2FA_Secret']) and user_row['2FA_Secret']:
        return '2FA_REQUIRED', nome_completo
    else:
        # L'utente non ha una 2FA, deve configurarla.
        return '2FA_SETUP_REQUIRED', (nome_completo, ruolo)
