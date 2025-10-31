import datetime

# Data di riferimento (Anchor Date): Venerdì 28 Novembre 2025, inizio del turno della Coppia 1
ANCHOR_DATE = datetime.date(2025, 11, 28)

# Sequenza ciclica di 4 coppie di reperibilità.
# Ogni coppia è una tupla che contiene due tuple: (COGNOME, RUOLO)
ON_CALL_ROTATION = [
    (("RICIPUTO", "Tecnico"), ("GUARINO", "Aiutante")),    # Andrea Riciputo, Riccardo Guarino
    (("SPINALI", "Tecnico"), ("ALLEGRETTI", "Aiutante")),  # Domenico Spinali, Giancarlo Allegretti
    (("MILLO", "Tecnico"), ("GUARINO", "Aiutante")),      # Francesco Millo, Riccardo Guarino
    (("TARASCIO", "Tecnico"), ("PARTESANO", "Aiutante")),  # Benito Tarascio, Vincenzo Partesano
]

def get_on_call_pair(current_date):
    """
    Calcola la coppia di reperibilità per una data specifica basandosi su un ciclo di 4 settimane.

    Args:
        current_date (datetime.date): La data per cui calcolare la reperibilità.

    Returns:
        tuple: Una tupla contenente le due tuple (COGNOME, RUOLO) per la data specificata.
               Restituisce (("N/D", ""), ("N/D", "")) se i dati non sono validi.
    """
    if not isinstance(current_date, datetime.date):
        return (("N/D", ""), ("N/D", ""))

    # Il giorno di cambio è il Venerdì (weekday() == 4)
    # Calcoliamo quanti giorni mancano per arrivare al Venerdì precedente o corrente.
    days_since_friday = (current_date.weekday() - 4 + 7) % 7
    start_of_week = current_date - datetime.timedelta(days=days_since_friday)

    # Calcola la differenza in giorni tra l'inizio della settimana della data corrente
    # e la data di riferimento.
    delta_days = (start_of_week - ANCHOR_DATE).days

    # Calcola il numero di settimane di differenza.
    # Usiamo la divisione intera // per ottenere il numero completo di settimane.
    week_difference = delta_days // 7

    # L'indice nel ciclo di rotazione è calcolato usando il modulo 4.
    # Questo garantisce che l'indice sia sempre tra 0 e 3.
    rotation_index = week_difference % len(ON_CALL_ROTATION)

    return ON_CALL_ROTATION[rotation_index]
