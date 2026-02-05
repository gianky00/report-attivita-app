"""
Test unitari per la gestione globale delle eccezioni.
"""

import pytest
from core.exceptions import safe_streamlit_run


def test_safe_streamlit_run_success():
    """Verifica che il decoratore non interferisca con le funzioni che hanno successo."""

    @safe_streamlit_run
    def success_func():
        return "ok"

    assert success_func() == "ok"


def test_safe_streamlit_run_exception(mocker):
    """Verifica che il decoratore catturi le eccezioni e mostri la UI di errore."""
    mock_st_error = mocker.patch("streamlit.error")
    mocker.patch("streamlit.stop", side_effect=RuntimeError("Streamlit Stopped"))

    @safe_streamlit_run
    def crash_func():
        raise ValueError("Simulated Crash")

    with pytest.raises(RuntimeError, match="Streamlit Stopped"):
        crash_func()

    mock_st_error.assert_called_once()
    # Verifica che il messaggio contenga l'indicazione del crash
    args, _ = mock_st_error.call_args
    assert "errore imprevisto" in args[0]
