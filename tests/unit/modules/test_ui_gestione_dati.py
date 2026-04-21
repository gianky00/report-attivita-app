"""
Test unitari per la gestione dati e esclusioni.
Copre src/pages/gestione_dati.py.
"""

import pandas as pd
from pages.gestione_dati import render_gestione_dati_tab
from tests.unit.modules.st_mock_helper import MockSessionState

def test_render_gestione_dati_tab_success(mocker):
    # Patching Streamlit
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mock_success = mocker.patch("streamlit.success")
    mocker.patch("streamlit.error")
    mocker.patch("streamlit.warning")
    mocker.patch("streamlit.write")
    mocker.patch("streamlit.divider")
    
    mocker.patch(
        "streamlit.selectbox",
        side_effect=lambda label, options, **kwargs: options[0] if options else None,
    )
    mocker.patch("streamlit.data_editor", side_effect=lambda df, **kwargs: df)
    
    # Mock selettivo per i bottoni: True solo per il salvataggio per testare un ramo alla volta
    mocker.patch("streamlit.button", side_effect=lambda label, **kwargs: label == "Salva Modifiche")
    mocker.patch("streamlit.rerun")
    mocker.patch("streamlit.session_state", MockSessionState({"authenticated_user": "M1"}))

    # Patching module imports (attento ai percorsi reali di import in gestione_dati.py)
    mocker.patch("pages.gestione_dati.get_table_names", return_value=["table1"])
    mocker.patch("pages.gestione_dati.get_table_data", return_value=pd.DataFrame([{"id": 1}]))
    mocker.patch("pages.gestione_dati.save_table_data", return_value=True)
    
    # Mock utenti con colonne obbligatorie
    df_users = pd.DataFrame([
        {"Matricola": "M1", "Nome Cognome": "Admin Test", "Ruolo": "Amministratore"}
    ])
    mocker.patch("pages.gestione_dati.get_all_users", return_value=df_users)
    
    mocker.patch("pages.gestione_dati.get_all_assigned_activities", return_value=[])
    mocker.patch("pages.gestione_dati.get_validated_intervention_reports", return_value=pd.DataFrame())

    render_gestione_dati_tab()
    assert mock_success.called

def test_render_gestione_dati_tab_no_tables(mocker):
    mocker.patch("streamlit.subheader")
    mocker.patch("streamlit.info")
    mock_warning = mocker.patch("streamlit.warning")
    mocker.patch("streamlit.session_state", MockSessionState({}))

    mocker.patch("pages.gestione_dati.get_table_names", return_value=[])

    render_gestione_dati_tab()
    assert mock_warning.called
