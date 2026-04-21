"""
Test unitari per la logica UI dell'applicazione.
"""

from unittest.mock import MagicMock
import pandas as pd
from components.ui.activity_ui import disegna_sezione_attivita, visualizza_storico_organizzato
from tests.unit.modules.st_mock_helper import MockSessionState

def test_disegna_sezione_attivita_empty(mocker):
    """Verifica il comportamento con lista attività vuota."""
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.divider")
    mocker.patch("streamlit.session_state", MockSessionState({}))
    mocker.patch("components.ui.activity_ui.get_unvalidated_reports_by_technician", return_value=pd.DataFrame())
    mock_success = mocker.patch("streamlit.success")
    
    disegna_sezione_attivita([], "empty_sec", "Tecnico")
    assert mock_success.called

def test_visualizza_storico_large_dataset(mocker):
    """Verifica il rendering dello storico con molti elementi."""
    mock_expander = mocker.patch("streamlit.expander")
    mocker.patch("streamlit.toggle", return_value=True)
    mocker.patch("streamlit.markdown")
    mocker.patch("streamlit.info")
    
    storico = [
        {"Data_Riferimento_dt": "2023-01-01", "Tecnico": "T1", "Report": "Ok"},
        {"Data_Riferimento_dt": "2023-01-02", "Tecnico": "T2", "Report": "Ok"}
    ] * 50
    
    visualizza_storico_organizzato(storico, "123456")
    assert mock_expander.called

def test_disegna_sezione_attivita_rendering(mocker):
    """Verifica che la sezione attività renderizzi correttamente gli expander."""
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.divider")
    mocker.patch("streamlit.session_state", MockSessionState({"authenticated_user": "123"}))
    mocker.patch("components.ui.activity_ui.get_unvalidated_reports_by_technician", return_value=pd.DataFrame())
    
    mock_expander = mocker.patch("streamlit.expander")
    mocker.patch("streamlit.button")
    
    # Mock per le colonne di Streamlit
    mock_col1 = MagicMock()
    mock_col2 = MagicMock()
    mocker.patch("streamlit.columns", return_value=[mock_col1, mock_col2])

    attivita = [
        {"pdl": "123", "attivita": "Test", "team": []}
    ]
    
    disegna_sezione_attivita(attivita, "render_sec", "Tecnico")
    assert mock_expander.called
