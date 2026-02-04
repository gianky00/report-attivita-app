"""
Interfaccia di gestione della logica dei turni (Facade).
Riesporta le funzioni dai moduli specializzati.
"""

from src.modules.shifts.logic_bookings import (
    cancella_prenotazione_logic,
    prenota_turno_logic,
)
from src.modules.shifts.logic_market import (
    prendi_turno_da_bacheca_logic,
    pubblica_turno_in_bacheca_logic,
    richiedi_sostituzione_logic,
    rispondi_sostituzione_logic,
)
from src.modules.shifts.logic_oncall import (
    manual_override_logic,
    sync_oncall_shifts,
)
from src.modules.shifts.logic_utils import find_matricola_by_surname, log_shift_change

__all__ = [
    "log_shift_change",
    "find_matricola_by_surname",
    "prenota_turno_logic",
    "cancella_prenotazione_logic",
    "sync_oncall_shifts",
    "manual_override_logic",
    "richiedi_sostituzione_logic",
    "rispondi_sostituzione_logic",
    "pubblica_turno_in_bacheca_logic",
    "prendi_turno_da_bacheca_logic",
]
