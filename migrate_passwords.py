import pandas as pd
import bcrypt
import config
import os

def migrate_passwords():
    """
    Legge le password in chiaro dal file gestionale, crea un hash sicuro
    e le salva in una nuova colonna 'PasswordHash'.
    Questo script è pensato per essere eseguito UNA SOLA VOLTA.
    """
    print("--- Inizio Migrazione Password ---")

    # 2. Caricamento del file gestionale
    file_path = config.PATH_GESTIONALE
    if not os.path.exists(file_path):
        print(f"ERRORE: Il file '{file_path}' non è stato trovato.")
        return

    print(f"Caricamento del file: '{file_path}'...")
    try:
        # Carichiamo l'intero file per preservare gli altri fogli
        xls = pd.ExcelFile(file_path)
        df_contatti = pd.read_excel(xls, sheet_name='Contatti')
        other_sheets = {sheet_name: pd.read_excel(xls, sheet_name) for sheet_name in xls.sheet_names if sheet_name != 'Contatti'}
    except Exception as e:
        print(f"ERRORE: Impossibile leggere il file Excel. Dettagli: {e}")
        return

    # 3. Verifica se la migrazione è già stata fatta
    if 'PasswordHash' in df_contatti.columns:
        print("ATTENZIONE: La colonna 'PasswordHash' esiste già. La migrazione potrebbe essere già stata eseguita.")
        # Chiedi conferma per procedere comunque
        choice = input("Vuoi sovrascrivere i dati esistenti? (s/n): ").lower()
        if choice != 's':
            print("Migrazione annullata dall'utente.")
            return
    else:
        df_contatti['PasswordHash'] = None # Crea la colonna

    print("Inizio hashing delle password (usando bcrypt direttamente)...")
    # 4. Itera e hasha le password
    passwords_migrated = 0
    for index, row in df_contatti.iterrows():
        password = row.get('Password')
        # Controlla se la password non è vuota o NaN
        if password and pd.notna(password):
            # Codifica la password in byte e genera l'hash
            password_bytes = str(password).encode('utf-8')
            salt = bcrypt.gensalt()
            hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
            # Decodifica l'hash in stringa per salvarlo
            df_contatti.loc[index, 'PasswordHash'] = hashed_password_bytes.decode('utf-8')
            passwords_migrated += 1
            print(f"  - Migrata password per l'utente: {row.get('Nome Cognome')}")

    if passwords_migrated == 0:
        print("Nessuna password da migrare trovata nella colonna 'Password'.")

    print(f"\nMigrazione completata. {passwords_migrated} password sono state crittografate.")

    # 5. Salva il file modificato
    print("Salvataggio del file Excel aggiornato...")
    try:
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df_contatti.to_excel(writer, sheet_name='Contatti', index=False)
            for sheet_name, df in other_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print("--- Salvataggio completato con successo! ---")
    except Exception as e:
        print(f"ERRORE CRITICO DURANTE IL SALVATAGGIO: {e}")
        print("I dati modificati NON sono stati salvati.")

if __name__ == "__main__":
    print("*****************************************************************")
    print("* ATTENZIONE: Questo script modificherà il file delle password. *")
    print("* SI CONSIGLIA VIVAMENTE DI FARE UN BACKUP DEL FILE             *")
    print(f"* '{config.PATH_GESTIONALE}' prima di procedere. *")
    print("*****************************************************************")

    confirm = input("Sei sicuro di voler continuare? (s/n): ").lower()
    if confirm == 's':
        migrate_passwords()
    else:
        print("Migrazione annullata.")
