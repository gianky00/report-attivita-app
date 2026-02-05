"""
Test unitari per la gestione dei turni e sottomoduli logici.
"""

import pandas as pd
import datetime
from modules.shifts.logic_utils import find_matricola_by_surname, log_shift_change
from modules.shifts.logic_bookings import prenota_turno_logic


def test_prenota_turno_logic_success(mocker):
    # Patchiamo le dipendenze nel modulo dove risiede la logica
    mocker.patch(
        'modules.shifts.logic_bookings.get_shift_by_id',
        return_value={
            "ID_Turno": "T1", 
            "PostiTecnico": 2, 
            "PostiAiutante": 1,
            "Data": datetime.date.today().isoformat()
        },
    )
    mocker.patch(
        'modules.shifts.logic_bookings.get_bookings_for_shift',
        return_value=pd.DataFrame(columns=["RuoloOccupato"]),
    )
    mocker.patch("modules.shifts.logic_bookings.add_booking", return_value=True)
    mocker.patch("modules.shifts.logic_bookings.log_shift_change")
    mocker.patch("modules.shifts.logic_bookings.st")
    mocker.patch("modules.shifts.logic_bookings.check_user_oncall_conflict", return_value=False)
    
    assert prenota_turno_logic("123", "T1", "Tecnico") is True


def test_log_shift_change_call(mocker):
    # Patchiamo nel sottomodulo logic_utils
    mock_add = mocker.patch(
        'modules.shifts.logic_utils.add_shift_log', return_value=True
    )
    log_shift_change("T1", "Test")
    assert mock_add.called


def test_find_matricola_by_surname_success(mocker):
    mock_df = pd.DataFrame([{"Matricola": "123", "Nome Cognome": "Mario Rossi"}])
    assert find_matricola_by_surname(mock_df, "ROSSI") == "123"