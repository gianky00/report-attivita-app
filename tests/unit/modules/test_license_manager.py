"""
Test unitari per il License Manager.
"""

from modules.license_manager import check_pyarmor_license


def test_check_pyarmor_license_missing(mocker):
    """Verifica il comportamento se il file licenza manca."""
    mocker.patch("modules.license_manager.Path.exists", return_value=False)
    mock_logger = mocker.patch("modules.license_manager.logging")

    check_pyarmor_license()
    mock_logger.info.assert_called_with(
        "PyArmor license file not found. Skipping license check."
    )


def test_check_pyarmor_license_found(mocker):
    """Verifica la lettura della data di scadenza dal file licenza."""
    mocker.patch("modules.license_manager.Path.exists", return_value=True)
    mocker.patch(
        'modules.license_manager.Path.read_text',
        return_value="Expired Date: 2025-12-31\nOther Data",
    )
    mock_logger = mocker.patch("modules.license_manager.logging")

    check_pyarmor_license()
    # Verifica che venga loggata la data corretta
    args, _ = mock_logger.info.call_args
    assert "2025-12-31" in args[0]
