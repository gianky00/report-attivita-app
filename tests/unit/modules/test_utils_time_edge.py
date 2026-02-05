"""
Test avanzati per casi limite temporali: DST e mezzanotte.
"""

import pytest
from modules.utils import calculate_shift_duration, merge_time_slots

def test_dst_transition_duration():
    """Verifica il calcolo della durata reale durante il passaggio ora legale."""
    # Data: 30 Marzo 2025 (Passaggio a ora legale in Italia)
    # Alle 02:00 scattano le 03:00.
    # Un turno dalle 01:00 alle 04:00 (orologio) dura effettivamente 2 ore.
    start = "2025-03-30T01:00:00"
    end = "2025-03-30T04:00:00"
    
    duration = calculate_shift_duration(start, end)
    assert duration == 2.0

def test_dst_back_transition_duration():
    """Verifica il calcolo della durata reale durante il passaggio ora solare."""
    # Data: 26 Ottobre 2025 (Passaggio a ora solare in Italia)
    # Alle 03:00 si torna alle 02:00.
    # Un turno dalle 01:00 alle 04:00 (orologio) dura effettivamente 4 ore.
    start = "2025-10-26T01:00:00"
    end = "2025-10-26T04:00:00"
    
    duration = calculate_shift_duration(start, end)
    assert duration == 4.0

def test_midnight_crossing_duration():
    """Verifica il calcolo della durata per turni che scavalcano la mezzanotte."""
    # Turno 22:00 -> 02:00 (giorno dopo)
    start = "2025-01-01T22:00:00"
    end = "2025-01-01T02:00:00" # Ora fine < ora inizio
    
    duration = calculate_shift_duration(start, end)
    assert duration == 4.0
