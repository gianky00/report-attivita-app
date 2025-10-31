import datetime
import pandas as pd
from modules.oncall_logic import get_on_call_pair
from modules.shift_management import find_matricola_by_surname
from modules.db_manager import get_all_users

def diagnose_rotation_logic(start_date, end_date):
    """
    Simulates the on-call assignment logic for a specific date range and prints a detailed log.
    """
    print(f"--- Avvio diagnosi per il periodo dal {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')} ---\n")

    # Carica tutti gli utenti dal database una sola volta
    df_contatti = get_all_users()
    if df_contatti.empty:
        print("ERRORE CRITICO: La tabella 'contatti' nel database è vuota o non leggibile.")
        return

    print("--- Utenti trovati nel database ---")
    print(df_contatti[['Matricola', 'Nome Cognome']].to_string())
    print("-" * 35 + "\n")

    current_date = start_date
    delta = datetime.timedelta(days=1)

    while current_date <= end_date:
        print(f"Data: {current_date.strftime('%d/%m/%Y')} ({current_date.strftime('%A')})")

        # 1. Calcola la coppia dall'algoritmo
        pair = get_on_call_pair(current_date)
        (technician1_surname, tech1_role), (technician2_surname, tech2_role) = pair
        print(f"  -> Coppia calcolata: {technician1_surname} ({tech1_role}), {technician2_surname} ({tech2_role})")

        # 2. Verifica la corrispondenza nel database per il primo tecnico
        matricola1 = find_matricola_by_surname(df_contatti, technician1_surname)
        if matricola1:
            print(f"     - OK: Trovato '{technician1_surname}' con matricola '{matricola1}'.")
        else:
            print(f"     - ERRORE: '{technician1_surname}' non trovato nel database.")

        # 3. Verifica la corrispondenza nel database per il secondo tecnico
        matricola2 = find_matricola_by_surname(df_contatti, technician2_surname)
        if matricola2:
            print(f"     - OK: Trovato '{technician2_surname}' con matricola '{matricola2}'.")
        else:
            print(f"     - ERRORE: '{technician2_surname}' non trovato nel database.")

        print("-" * 20)
        current_date += delta

if __name__ == "__main__":
    # Definisci il periodo problematico per l'analisi
    start = datetime.date(2025, 9, 29)
    end = datetime.date(2025, 12, 3)
    diagnose_rotation_logic(start, end)
