"""
Test unitari per l'interfaccia dello storico.
"""

import pandas as pd
import datetime
from pages.storico import render_storico_tab

def test_render_storico_tab_all_empty(mocker):
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.subheader")
    # Ora ci sono 5 tab
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock() for _ in range(5)])
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.date_input", return_value=datetime.date.today())

    mocker.patch("pages.storico.get_validated_intervention_reports", return_value=pd.DataFrame())
    mocker.patch("pages.storico.get_validated_reports", return_value=pd.DataFrame())
    mocker.patch("pages.storico.get_storico_richieste_materiali", return_value=pd.DataFrame())
    mocker.patch("pages.storico.get_pdl_programmazione", return_value=pd.DataFrame())

    render_storico_tab()
    assert mock_success.called

def test_render_storico_tab_with_data(mocker):
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock() for _ in range(5)])
    mocker.patch("streamlit.text_input", return_value="")
    mocker.patch("streamlit.expander", return_value=mocker.MagicMock())
    mocker.patch("streamlit.text_area")
    mocker.patch("streamlit.date_input", return_value=datetime.date.today())

    df_act = pd.DataFrame(
        [
            {
                "id_report": "R1",
                "pdl": "P1",
                "descrizione_attivita": "D1",
                "nome_tecnico": "T1",
                "stato_attivita": "Fine",
                "data_riferimento_attivita": "2025-01-01",
                "data_compilazione": "2025-01-01",
                "testo_report": "Report test",
            }
        ]
    )

    mocker.patch("pages.storico.get_validated_intervention_reports", return_value=df_act)
    mocker.patch("pages.storico.get_validated_reports", return_value=pd.DataFrame())
    mocker.patch("pages.storico.get_storico_richieste_materiali", return_value=pd.DataFrame())
    mocker.patch("pages.storico.get_pdl_programmazione", return_value=pd.DataFrame())

    render_storico_tab()
    assert True
