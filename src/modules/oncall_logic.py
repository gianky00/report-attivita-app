"""
Logica per il calcolo della rotazione della reperibilità settimanale.
Basato su un ciclo di 4 settimane con cambio turno ogni venerdì.
"""

import datetime

# Data di riferimento (Anchor Date): Venerdì 28 Novembre 2025, inizio del turno della Coppia 1
ANCHOR_DATE = datetime.date(2025, 11, 28)

# Sequenza ciclica di 4 coppie di reperibilità.
# Ogni coppia è una tupla che contiene due tuple: (COGNOME, RUOLO)
ON_CALL_ROTATION = [
    (
        ("RICIPUTO", "Tecnico"),
        ("GUARINO", "Aiutante"),
    ),  # Andrea Riciputo, Riccardo Guarino
    (
        ("SPINALI", "Tecnico"),
        ("ALLEGRETTI", "Aiutante"),
    ),  # Domenico Spinali, Giancarlo Allegretti
    (
        ("MILLO", "Tecnico"),
        ("GUARINO", "Aiutante"),
    ),  # Francesco Millo, Riccardo Guarino
    (
        ("TARASCIO", "Tecnico"),
        ("PARTESANO", "Aiutante"),
    ),  # Benito Tarascio, Vincenzo Partesano
]


def get_on_call_pair(current_date: datetime.date) -> tuple:
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


def get_next_on_call_week(
    user_surname: str, start_date: datetime.date | None = None
) -> datetime.date | None:
    """
    Trova la prossima settimana in cui un utente è di reperibilità.

    Args:
        user_surname (str): Il cognome dell'utente da cercare.
        start_date (datetime.date, optional): La data da cui iniziare la ricerca.
                                             Default a oggi.

    Returns:
        datetime.date or None: La data di inizio del blocco di reperibilità (Venerdì),
                               o None se non trovata entro un anno.
    """
    if not user_surname:
        return None

    if start_date is None:
        start_date = datetime.date.today()

    # Cerca per un massimo di 365 giorni per evitare cicli infiniti
    for i in range(365):
        current_date = start_date + datetime.timedelta(days=i)

        # Il cambio turno è di venerdì, quindi la nostra data di inizio del blocco è sempre un venerdì
        if current_date.weekday() != 4:  # 4 = Venerdì
            continue

        pair = get_on_call_pair(current_date)
        surnames_in_pair = [p[0].upper() for p in pair]

        if user_surname.upper() in surnames_in_pair:
            # La data corrente è già il venerdì che stavamo cercando.
            return current_date

    return None
