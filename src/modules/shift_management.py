"""
Interfaccia di gestione della logica dei turni (Facade).
Riesporta le funzioni dai moduli specializzati.
"""

from modules.shifts.logic_bookings import (
    cancella_prenotazione_logic,
    prenota_turno_logic,
)
from modules.shifts.logic_market import (
    prendi_turno_da_bacheca_logic,
    pubblica_turno_in_bacheca_logic,
    richiedi_sostituzione_logic,
    rispondi_sostituzione_logic,
)
from modules.shifts.logic_oncall import (
    manual_override_logic,
    sync_oncall_shifts,
)
from modules.shifts.logic_utils import find_matricola_by_surname, log_shift_change

__all__ = [
    "cancella_prenotazione_logic",
    "find_matricola_by_surname",
    "log_shift_change",
    "manual_override_logic",
    "prendi_turno_da_bacheca_logic",
    "prenota_turno_logic",
    "pubblica_turno_in_bacheca_logic",
    "richiedi_sostituzione_logic",
    "rispondi_sostituzione_logic",
    "sync_oncall_shifts",
]
