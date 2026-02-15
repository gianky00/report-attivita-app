import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import pages.gestione_dati as gd


class TestGestioneDatiLogic(unittest.TestCase):
    @patch("streamlit.data_editor")
    @patch("streamlit.selectbox")
    @patch("streamlit.button")
    @patch("streamlit.success")
    @patch("pages.gestione_dati.get_table_data")
    @patch("pages.gestione_dati.get_table_names")
    @patch("pages.gestione_dati.save_table_data")
    def test_render_gestione_dati_save(
        self, mock_save, mock_names, mock_data, mock_succ, mock_btn, mock_sel, mock_edit
    ):
        mock_names.return_value = ["table1"]
        mock_sel.return_value = "table1"
        mock_data.return_value = pd.DataFrame({"col1": [1]})
        mock_edit.return_value = pd.DataFrame({"col1": [2]})
        mock_btn.return_value = True
        mock_save.return_value = True

        gd.render_gestione_dati_tab()

        mock_save.assert_called()
        mock_succ.assert_called_with("Dati salvati con successo!", icon=unittest.mock.ANY)

    @patch("streamlit.session_state", {"authenticated_user": "ADM01"})
    @patch("streamlit.rerun")
    @patch("streamlit.data_editor")
    @patch("streamlit.selectbox")
    @patch("streamlit.button")
    @patch("pages.gestione_dati.add_assignment_exclusion")
    @patch("pages.gestione_dati.get_all_users")
    @patch("pages.gestione_dati.get_all_assigned_activities")
    @patch("pages.gestione_dati.get_validated_intervention_reports")
    def test_render_esclusioni_flow(
        self,
        mock_val,
        mock_all,
        mock_get_users,
        mock_add,
        mock_btn,
        mock_sel,
        mock_edit,
        mock_rerun,
    ):
        # Setup users
        mock_get_users.return_value = pd.DataFrame(
            [{"Matricola": "T01", "Nome Cognome": "Tecnico Uno", "Ruolo": "Tecnico"}]
        )
        # First call (table selection) returns empty/None, second call (technician) returns "Tecnico Uno"
        mock_sel.side_effect = ["", "Tecnico Uno"]

        # Setup activities and validated reports
        mock_all.return_value = [
            {
                "pdl": "101",
                "attivita": "Test",
                "team": [{"nome": "T1"}],
                "Data Assegnamento": "2023-01-01",
            }
        ]
        mock_val.return_value = pd.DataFrame()  # No validated reports yet

        # Setup data editor for selection
        mock_edit.return_value = pd.DataFrame(
            [{"pdl": "101", "attivita": "Test", "seleziona": True}]
        )

        mock_btn.return_value = True
        mock_add.return_value = True

        gd.render_gestione_dati_tab()

        mock_add.assert_called_with("ADM01", "101-Test")
        mock_rerun.assert_called()


if __name__ == "__main__":
    unittest.main()
