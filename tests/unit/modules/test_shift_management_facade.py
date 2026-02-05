"""
Test per la facciata shift_management.
"""
from modules.shift_management import __all__

def test_shift_management_exports():
    """Verifica che tutte le funzioni attese siano esportate."""
    expected = [
        "log_shift_change", "find_matricola_by_surname", "prenota_turno_logic",
        "cancella_prenotazione_logic", "sync_oncall_shifts", "manual_override_logic",
        "richiedi_sostituzione_logic", "rispondi_sostituzione_logic",
        "pubblica_turno_in_bacheca_logic", "prendi_turno_da_bacheca_logic"
    ]
    for func in expected:
        assert func in __all__
