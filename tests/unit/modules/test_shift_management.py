"""
Test unitari per la gestione dei turni.
"""

import pandas as pd
from src.modules.shift_management import (
    find_matricola_by_surname,
    log_shift_change,
    prenota_turno_logic,
)


def test_prenota_turno_logic_success(mocker):
    mocker.patch(
        "src.modules.shift_management.get_shift_by_id",
        return_value={"ID_Turno": "T1", "PostiTecnico": 2, "PostiAiutante": 1},
    )
    mocker.patch(
        "src.modules.shift_management.get_bookings_for_shift",
        return_value=pd.DataFrame(columns=["RuoloOccupato"]),
    )
    mocker.patch("src.modules.shift_management.add_booking", return_value=True)
    mocker.patch("src.modules.shift_management.log_shift_change")
    mocker.patch("src.modules.shift_management.st")
    assert prenota_turno_logic("123", "T1", "Tecnico") is True


def test_log_shift_change_call(mocker):
    mock_add = mocker.patch(
        "src.modules.shift_management.add_shift_log", return_value=True
    )
    log_shift_change("T1", "Test")
    assert mock_add.called


def test_find_matricola_by_surname_success(mocker):
    mock_df = pd.DataFrame([{"Matricola": "123", "Nome Cognome": "Mario Rossi"}])
    # Firma corretta: find_matricola_by_surname(df_contatti, surname_to_find)
    assert find_matricola_by_surname(mock_df, "ROSSI") == "123"
