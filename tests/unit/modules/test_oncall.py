"""
Test unitari per il calcolo della rotazione reperibilità.
"""

import datetime

from modules.oncall_logic import get_next_on_call_week, get_on_call_pair


def test_get_on_call_pair_anchor():
    """Verifica il calcolo sulla data di riferimento (Anchor Date)."""
    # 28 Nov 2025 è un Venerdì (inizio rotazione coppia 0)
    anchor = datetime.date(2025, 11, 28)
    pair = get_on_call_pair(anchor)
    assert pair[0][0] == "RICIPUTO"
    assert pair[1][0] == "GUARINO"


def test_get_on_call_pair_next_week():
    """Verifica il passaggio alla coppia successiva (settimana 2)."""
    next_week = datetime.date(2025, 12, 5)
    pair = get_on_call_pair(next_week)
    assert pair[0][0] == "SPINALI"
    assert pair[1][0] == "ALLEGRETTI"


def test_get_next_on_call_week():
    """Verifica la ricerca della prossima settimana di reperibilità per un utente."""
    # Cerchiamo Spinali partendo dal 28 Nov 2025
    start = datetime.date(2025, 11, 28)
    next_date = get_next_on_call_week("SPINALI", start_date=start)
    # Dovrebbe essere il venerdì successivo
    assert next_date == datetime.date(2025, 12, 5)


def test_get_on_call_pair_invalid_input():
    """Verifica gestione input non validi."""
    assert get_on_call_pair("not-a-date") == (("N/D", ""), ("N/D", ""))
