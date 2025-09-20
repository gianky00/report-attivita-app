import pandas as pd
import config

def verify():
    """Legge il file gestionale e stampa le colonne relative alle password."""
    try:
        df = pd.read_excel(config.PATH_GESTIONALE, sheet_name='Contatti')
        print("Verifica del file gestionale dopo la migrazione:")
        print(df[['Nome Cognome', 'Password', 'PasswordHash']])
    except Exception as e:
        print(f"Errore durante la verifica: {e}")

if __name__ == "__main__":
    verify()
