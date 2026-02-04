"""
Test unitari per le utility di manipolazione orari e dati.
"""

from src.modules.utils import merge_time_slots


def test_merge_time_slots_overlapping():
    """Verifica l'unione di slot temporali sovrapposti."""
    slots = ["08:00-10:00", "09:30-11:00"]
    result = merge_time_slots(slots)
    assert result == ["08:00 - 11:00"]


def test_merge_time_slots_contiguous():
    """Verifica l'unione di slot temporali contigui."""
    slots = ["08:00-10:00", "10:00-12:00"]
    result = merge_time_slots(slots)
    assert result == ["08:00 - 12:00"]


def test_merge_time_slots_disjoint():
    """Verifica che slot disgiunti rimangano separati."""
    slots = ["08:00-10:00", "14:00-16:00"]
    result = merge_time_slots(slots)
    assert result == ["08:00 - 10:00", "14:00 - 16:00"]


def test_merge_time_slots_empty():
    """Verifica il comportamento con lista vuota."""
    assert merge_time_slots([]) == []


def test_merge_time_slots_invalid_format():
    """Verifica la resilienza a formati non validi."""
    slots = ["invalid", "08:00-10:00"]
    result = merge_time_slots(slots)
    assert result == ["08:00 - 10:00"]
