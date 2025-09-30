import datetime

# --- CONFIGURAZIONE DELLA ROTAZIONE ---

# La sequenza delle coppie di tecnici in rotazione.
# Ogni elemento è una tupla di due stringhe (cognomi).
ROTATION_PAIRS = [
    ("RICIPUTO", "GUARINO"),
    ("SPINALI", "ALLEGRETTI"),
    ("MILLO", "GUARINO"),
    ("TARASCIO", "PARTESANO"),
]

# Una data di riferimento nota per ancorare il ciclo di rotazione.
# Deve essere un venerdì, giorno di inizio del ciclo settimanale.
# Usiamo il 5 settembre 2025, che corrisponde alla prima coppia della nostra lista.
REFERENCE_DATE = datetime.date(2025, 9, 5)
REFERENCE_PAIR_INDEX = 0 # L'indice della coppia di riferimento nella lista ROTATION_PAIRS

def get_on_call_pair_for_date(target_date: datetime.date) -> tuple[str, str]:
    """
    Calcola la coppia di tecnici di reperibilità per una data specifica
    basandosi su un ciclo di rotazione di 4 settimane.

    Args:
        target_date: La data per cui calcolare la coppia di turno.

    Returns:
        Una tupla contenente i cognomi dei due tecnici di turno.
    """
    # 1. Trova il venerdì della settimana della data target. Il ciclo inizia di venerdì.
    days_since_friday = (target_date.weekday() - 4) % 7
    start_of_week = target_date - datetime.timedelta(days=days_since_friday)

    # 2. Calcola la differenza in giorni dalla data di riferimento.
    days_difference = (start_of_week - REFERENCE_DATE).days

    # 3. Calcola il numero di settimane passate (o future).
    # Usiamo la divisione intera per ottenere il numero completo di settimane.
    weeks_difference = days_difference // 7

    # 4. Calcola l'indice corrente nel ciclo di rotazione.
    # L'operatore modulo (%) assicura che l'indice rimanga all'interno dei limiti della lista.
    current_index = (REFERENCE_PAIR_INDEX + weeks_difference) % len(ROTATION_PAIRS)

    # 5. Restituisce la coppia di tecnici corretta.
    return ROTATION_PAIRS[current_index]

if __name__ == '__main__':
    # Esempio di utilizzo e test per verificare la correttezza della logica
    print("--- Test del Generatore di Turni di Reperibilità ---")

    test_dates = [
        datetime.date(2025, 9, 5),   # Venerdì, inizio ciclo Riciputo
        datetime.date(2025, 9, 8),   # Lunedì, ancora Riciputo
        datetime.date(2025, 9, 12),  # Venerdì, inizio ciclo Spinali
        datetime.date(2025, 9, 19),  # Venerdì, inizio ciclo Millo
        datetime.date(2025, 9, 26),  # Venerdì, inizio ciclo Tarascio
        datetime.date(2025, 10, 3),  # Venerdì, di nuovo Riciputo
        datetime.date(2025, 10, 31), # Venerdì, di nuovo Riciputo
        datetime.date(2026, 1, 2),   # Anno nuovo
    ]

    for date_to_test in test_dates:
        pair = get_on_call_pair_for_date(date_to_test)
        print(f"Data: {date_to_test.strftime('%d/%m/%Y')} -> Turno di: {pair[0]}-{pair[1]}")

import sqlite3
import pandas as pd
import config

def _get_matricola_from_lastname(lastname: str, contacts_df: pd.DataFrame) -> str | None:
    """Finds a matricola from a lastname in the contacts DataFrame."""
    result = contacts_df[contacts_df['Nome Cognome'].str.contains(lastname, case=False, na=False)]
    if not result.empty:
        return result.iloc[0]['Matricola']
    return None

def sync_on_call_shifts_to_db(start_date: datetime.date, end_date: datetime.date):
    """
    Generates and synchronizes on-call shifts for a given period with the database.
    It creates missing shifts and updates auto-generated ones if needed,
    but respects any shifts that have been manually modified by an admin.
    """
    print(f"--- Avvio sincronizzazione turni di reperibilità dal {start_date} al {end_date} ---")
    conn = None
    try:
        with config.EXCEL_LOCK: # Use the global lock for thread safety
            conn = sqlite3.connect(config.DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            contacts_df = pd.read_sql_query("SELECT Matricola, \"Nome Cognome\" FROM contatti", conn)
            contacts_df['Matricola'] = contacts_df['Matricola'].astype(str)

            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                shift_id = f"REP_{current_date.strftime('%Y%m%d')}"

                cursor.execute("SELECT * FROM turni WHERE Data = ? AND Tipo = 'Reperibilità'", (date_str,))
                existing_shift = cursor.fetchone()

                if existing_shift and existing_shift['is_manually_modified'] == 1:
                    print(f"Turno del {date_str} saltato perché modificato manualmente.")
                    current_date += datetime.timedelta(days=1)
                    continue

                tech1_lastname, tech2_lastname = get_on_call_pair_for_date(current_date)

                tech1_matricola = _get_matricola_from_lastname(tech1_lastname, contacts_df)
                tech2_matricola = _get_matricola_from_lastname(tech2_lastname, contacts_df)

                if not tech1_matricola or not tech2_matricola:
                    print(f"ATTENZIONE: Impossibile trovare la matricola per {tech1_lastname} o {tech2_lastname} per il giorno {date_str}. Turno non creato.")
                    current_date += datetime.timedelta(days=1)
                    continue

                with conn:
                    descrizione = f"Reperibilità {current_date.strftime('%d/%m/%Y')}"

                    cursor.execute(
                        """
                        INSERT INTO turni (ID_Turno, Descrizione, Data, OrarioInizio, OrarioFine, PostiTecnico, PostiAiutante, Tipo, is_manually_modified)
                        VALUES (?, ?, ?, '00:00', '23:59', 2, 0, 'Reperibilità', 0)
                        ON CONFLICT(ID_Turno) DO UPDATE SET
                            Descrizione = excluded.Descrizione,
                            Data = excluded.Data,
                            is_manually_modified = 0;
                        """,
                        (shift_id, descrizione, date_str)
                    )

                    cursor.execute("DELETE FROM prenotazioni WHERE ID_Turno = ?", (shift_id,))

                    timestamp_now = datetime.datetime.now().isoformat()
                    prenotazioni = [
                        (f"P_{shift_id}_{tech1_matricola}", shift_id, tech1_matricola, 'Tecnico', timestamp_now),
                        (f"P_{shift_id}_{tech2_matricola}", shift_id, tech2_matricola, 'Tecnico', timestamp_now),
                    ]
                    cursor.executemany(
                        "INSERT INTO prenotazioni (ID_Prenotazione, ID_Turno, Matricola, RuoloOccupato, Timestamp) VALUES (?, ?, ?, ?, ?)",
                        prenotazioni
                    )
                    print(f"Turno del {date_str} creato/aggiornato per {tech1_lastname}-{tech2_lastname}.")

                current_date += datetime.timedelta(days=1)

            print("--- Sincronizzazione turni di reperibilità completata ---")
            return True

    except sqlite3.Error as e:
        print(f"ERRORE CRITICO durante la sincronizzazione dei turni di reperibilità: {e}")
        return False
    finally:
        if conn:
            conn.close()