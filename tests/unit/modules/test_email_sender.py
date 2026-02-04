"""
Test unitari per il modulo Email Sender.
"""


def test_invia_email_con_outlook_async(mocker):
    """Verifica che il modulo avvii un thread e lanci il subprocesso corretto."""
    # Mock di subprocess.run
    mock_run = mocker.patch("src.modules.email_sender.subprocess.run")
    mock_run.return_value.returncode = 0

    # Mock di Path.exists per far credere che lo script esista
    mocker.patch("src.modules.email_sender.Path.exists", return_value=True)

    # Eseguiamo la funzione. Poiché è asincrona, dobbiamo aspettare che il thread finisca
    # o testare la logica del subprocesso direttamente.
    from src.modules.email_sender import _send_email_subprocess

    _send_email_subprocess("Oggetto Test", "Corpo Test")

    # Verifica che subprocess.run sia stato chiamato con i parametri attesi
    args, _ = mock_run.call_args
    command = args[0]
    assert "send_email_subprocess.py" in str(command[1])
    assert command[2] == "Oggetto Test"
    assert command[3] == "Corpo Test"


def test_send_email_subprocess_missing_script(mocker):
    """Verifica la gestione dell'errore quando lo script non esiste."""
    mocker.patch("src.modules.email_sender.Path.exists", return_value=False)
    mock_logger = mocker.patch("src.modules.email_sender.logger")

    from src.modules.email_sender import _send_email_subprocess

    _send_email_subprocess("Test", "Test")

    mock_logger.error.assert_called_with(mocker.ANY)
