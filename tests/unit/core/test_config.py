"""
Test unitari per la configurazione dell'applicazione.
"""

import pytest
from config import validate_config


def test_validate_config_missing_keys(mocker):
    """Verifica che la validazione fallisca se mancano chiavi obbligatorie."""
    mocker.patch("src.config.logger")
    mocker.patch("sys.exit")

    # Forniamo un dizionario con chiavi mancanti.
    # validate_config solleverà KeyError se cerchiamo di accedere a REQUIRED_KEYS mancanti.
    bad_conf = {"path_storico_db": "test"}

    # In config.py la funzione validate_config viene chiamata immediatamente.
    # Testiamo la funzione isolata.
    with pytest.raises(KeyError):
        validate_config(bad_conf)


def test_validate_config_success(mocker):
    """Verifica che la validazione passi con una configurazione completa."""
    mocker.patch("src.config.Path.exists", return_value=True)
    mock_exit = mocker.patch("sys.exit")

    good_conf = {
        "path_storico_db": "p1",
        "path_gestionale": "p2",
        "path_giornaliera_base": "p3",
        "path_attivita_programmate": "p4",
    }

    validate_config(good_conf)
    assert not mock_exit.called
