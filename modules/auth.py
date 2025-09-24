import pandas as pd
import bcrypt
import pyotp
import time
from streamlit.runtime.scriptrunner import get_script_run_ctx
import geoip2.database
from geolite2 import geolite2
import os
import datetime
from modules.email_sender import invia_email_con_outlook_async

# --- Rate Limiting Globals ---
login_attempts = {}
MAX_ATTEMPTS = 4
LOCKOUT_PERIOD_MINUTES = 2

# --- Geolocalizzazione ---
GEO_READER = geolite2.reader()
TRUSTED_COUNTRY = 'IT'
TRUSTED_SUBDIVISION = 'Sicilia'

def get_client_ip():
    """Ottiene l'indirizzo IP del client."""
    try:
        ctx = get_script_run_ctx()
        if ctx is None: return "127.0.0.1" # Fallback per test locali
        session_info = ctx.session_info
        # Per test locali, l'IP potrebbe essere privato. Usiamo un IP pubblico fittizio.
        if session_info.client_ip in ["127.0.0.1", "localhost"]:
            return "87.18.217.132" # IP di esempio (Milano)
        return session_info.client_ip
    except Exception:
        return "127.0.0.1"

def check_anomalous_login(ip, username):
    """Controlla se un login è anomalo e invia una notifica."""
    try:
        match = GEO_READER.get(ip)
        if match and 'country' in match and 'subdivisions' in match:
            country = match['country']['names']['en']
            subdivision = match['subdivisions'][0]['names'].get('en', 'N/A')

            if country != TRUSTED_COUNTRY or subdivision != TRUSTED_SUBDIVISION:
                titolo_email = f"⚠️ Allerta Sicurezza: Accesso Sospetto per {username}"
                html_body = f"""
                <h3>Allerta di Sicurezza</h3>
                <p>È stato registrato un accesso al tuo account da una posizione anomala.</p>
                <ul>
                    <li><strong>Utente:</strong> {username}</li>
                    <li><strong>Indirizzo IP:</strong> {ip}</li>
                    <li><strong>Posizione Stimata:</strong> {match.get('city', {}).get('names', {}).get('en', 'N/A')}, {subdivision}, {country}</li>
                    <li><strong>Data e Ora:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</li>
                </ul>
                <p>Se non sei stato tu a effettuare questo accesso, contatta immediatamente un amministratore per mettere in sicurezza il tuo account.</p>
                """
                invia_email_con_outlook_async(titolo_email, html_body)
    except Exception:
        # Ignora errori di geolocalizzazione per non bloccare il login
        pass

def is_ip_locked(ip):
    """Controlla se un IP è attualmente bloccato."""
    if ip in login_attempts:
        attempts, lockout_time = login_attempts[ip]
        if attempts >= MAX_ATTEMPTS and time.time() < lockout_time:
            return True
    return False

def record_failed_login(ip):
    """Registra un tentativo di login fallito."""
    if ip not in login_attempts or time.time() > login_attempts[ip][1]:
        login_attempts[ip] = (1, time.time() + LOCKOUT_PERIOD_MINUTES * 60)
    else:
        current_attempts, lockout_time = login_attempts[ip]
        login_attempts[ip] = (current_attempts + 1, lockout_time)

def clear_login_attempts(ip):
    """Pulisce i tentativi di login per un IP dopo un successo."""
    if ip in login_attempts:
        del login_attempts[ip]

# --- Funzioni 2FA ---

def generate_2fa_secret():
    """Genera una nuova chiave segreta per la 2FA."""
    return pyotp.random_base32()

def get_provisioning_uri(username, secret):
    """Genera l'URI di provisioning per il QR code."""
    safe_username = "".join(c for c in username if c.isalnum())
    return pyotp.totp.TOTP(secret).provisioning_uri(name=safe_username, issuer_name="AppManutenzioneSMI")

def verify_2fa_code(secret, code):
    """Verifica un codice 2FA fornito dall'utente."""
    if not secret or not code: return False
    try:
        return pyotp.totp.TOTP(secret).verify(code)
    except Exception:
        return False

# --- Funzione di Autenticazione Principale ---

def authenticate_user(username, password, df_contatti):
    """
    Autentica un utente, gestisce il flusso 2FA, il rate limiting e il controllo accessi anomali.
    Restituisce sempre un messaggio di errore generico.
    """
    ip = get_client_ip()
    if ip and is_ip_locked(ip):
        return 'LOCKED', "Troppi tentativi falliti. Riprova più tardi."

    if df_contatti is None or df_contatti.empty or not username or not password:
        if ip: record_failed_login(ip)
        return 'FAILED', "Credenziali non valide."

    user_row = None
    for _, riga in df_contatti.iterrows():
        nome_completo = str(riga['Nome Cognome']).strip()
        user_param_corretto = nome_completo.split()[-1]
        if "Garro" in nome_completo:
            user_param_corretto = "Garro L"

        if username.lower() == user_param_corretto.lower():
            user_row = riga
            break

    if user_row is None:
        if ip: record_failed_login(ip)
        return 'FAILED', "Credenziali non valide."

    password_bytes = str(password).encode('utf-8')
    nome_completo = str(user_row['Nome Cognome']).strip()
    ruolo = user_row.get('Ruolo', 'Tecnico')
    password_valid = False

    if 'PasswordHash' in user_row and pd.notna(user_row['PasswordHash']):
        hashed_password_bytes = str(user_row['PasswordHash']).encode('utf-8')
        if bcrypt.checkpw(password_bytes, hashed_password_bytes):
            password_valid = True

    if not password_valid and 'Password' in user_row and pd.notna(user_row['Password']):
        if str(password) == str(user_row['Password']):
            password_valid = True

    if not password_valid:
        if ip: record_failed_login(ip)
        return 'FAILED', "Credenziali non valide."

    if ip:
        clear_login_attempts(ip)
        # Controlla l'accesso anomalo solo dopo un login completamente riuscito (password corretta)
        check_anomalous_login(ip, nome_completo)

    if '2FA_Secret' in user_row and pd.notna(user_row['2FA_Secret']) and user_row['2FA_Secret']:
        return '2FA_REQUIRED', nome_completo
    else:
        return '2FA_SETUP_REQUIRED', (nome_completo, ruolo)