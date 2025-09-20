import pandas as pd
import bcrypt

def authenticate_user(username, password, df_contatti):
    """
    Autentica un utente confrontando la password fornita con l'hash salvato.
    Include un fallback al vecchio sistema di password in chiaro per una
    transizione graduale.

    Args:
        username (str): Il nome utente (cognome o cognome e iniziale).
        password (str): La password in chiaro inserita dall'utente.
        df_contatti (pd.DataFrame): Il DataFrame contenente i dati dei contatti.

    Returns:
        tuple: Una tupla (nome_completo, ruolo) se le credenziali sono valide,
               altrimenti (None, None).
    """
    if df_contatti is None or df_contatti.empty or password is None:
        return None, None

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
        return None, None # Utente non trovato

    # --- Logica di autenticazione ---
    password_bytes = str(password).encode('utf-8')
    nome_completo = str(user_row['Nome Cognome']).strip()
    ruolo = user_row.get('Ruolo', 'Tecnico')

    # 1. Prova con il nuovo sistema di hash
    if 'PasswordHash' in user_row and pd.notna(user_row['PasswordHash']):
        hashed_password_bytes = str(user_row['PasswordHash']).encode('utf-8')
        if bcrypt.checkpw(password_bytes, hashed_password_bytes):
            return nome_completo, ruolo

    # 2. Fallback al vecchio sistema con password in chiaro (per sicurezza durante la transizione)
    if 'Password' in user_row and pd.notna(user_row['Password']):
        if str(password) == str(user_row['Password']):
            # Se il login ha successo con la vecchia password, e un hash non esiste,
            # si potrebbe opzionalmente creare l'hash qui "al volo" per migrare l'utente.
            # Per ora, ci limitiamo a consentire l'accesso.
            return nome_completo, ruolo

    # Se nessuna delle due corrisponde
    return None, None
