"""
Test unitari per la gestione richieste.
Copre src/pages/richieste.py.
"""

import datetime
import pandas as pd
from pages.richieste import render_richieste_tab

def test_render_richieste_tab_materiali_success(mocker):
    mocker.patch("streamlit.header")
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.tabs", return_value=[mocker.MagicMock()])
    mocker.patch("streamlit.divider")
    
    mock_form = mocker.MagicMock()
    mock_form.__enter__.return_value = mock_form
    mocker.patch("streamlit.form", return_value=mock_form)

    # In richieste.py ci sono più chiamate a st.columns
    mocker.patch("streamlit.columns", return_value=[mocker.MagicMock() for _ in range(4)])

    mocker.patch("streamlit.text_area", return_value="Materiali test")
    mocker.patch("streamlit.form_submit_button", return_value=True)
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.rerun")

    # Patch delle funzioni importate da db_manager
    mocker.patch("pages.richieste.add_material_request", return_value=True)
    mocker.patch("pages.richieste.salva_storico_materiali", return_value=True)
    mocker.patch("pages.richieste.get_material_requests", return_value=pd.DataFrame())
    mocker.patch("pages.richieste.get_all_users", return_value=pd.DataFrame())

    render_richieste_tab("M1", "Tecnico", "User Test")
    assert mock_success.called
