import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import pages.storico as storico

class TestStoricoLogic(unittest.TestCase):

    def setUp(self):
        # Patch Streamlit methods to return specific values needed for unpacking or logic
        self.patcher_st = patch("pages.storico.st")
        self.mock_st = self.patcher_st.start()
        
        # st.tabs(5) -> returns 5 mocks
        self.mock_st.tabs.return_value = [MagicMock() for _ in range(5)]
        # st.columns([1,1,1]) -> returns 3 mocks
        self.mock_st.columns.return_value = [MagicMock() for _ in range(3)]
        # st.text_input -> returns empty string (prevents re.compile error in pandas)
        self.mock_st.text_input.return_value = ""
        # st.date_input -> returns a date object
        import datetime
        self.mock_st.date_input.return_value = datetime.date.today()

    def tearDown(self):
        self.patcher_st.stop()

    @patch("pages.storico.get_validated_intervention_reports")
    @patch("pages.storico.get_pdl_programmazione")
    @patch("pages.storico.get_validated_reports")
    @patch("pages.storico.get_storico_richieste_materiali")
    def test_render_storico_complete(self, mock_mat, mock_rel, mock_pdl, mock_interv):
        # Mocking dataframes
        df_interv = pd.DataFrame([{
            "pdl": "123", 
            "descrizione_attivita": "Test", 
            "nome_tecnico": "T1", 
            "stato_attivita": "OK", 
            "data_compilazione": "2025-01-01", 
            "data_riferimento_attivita": "2025-01-01",
            "testo_report": "Report text",
            "id_report": "R1"
        }])
        mock_interv.return_value = df_interv
        mock_pdl.return_value = pd.DataFrame()
        mock_rel.return_value = pd.DataFrame()
        mock_mat.return_value = pd.DataFrame()
        
        storico.render_storico_tab()
        
        self.assertTrue(mock_interv.called)
        self.assertTrue(mock_pdl.called)
        self.assertTrue(mock_rel.called)

    @patch("pages.storico.get_validated_intervention_reports")
    @patch("pages.storico.get_pdl_programmazione")
    @patch("pages.storico.get_validated_reports")
    @patch("pages.storico.get_storico_richieste_materiali")
    def test_render_storico_empty(self, mock_mat, mock_rel, mock_pdl, mock_interv):
        mock_interv.return_value = pd.DataFrame()
        mock_pdl.return_value = pd.DataFrame()
        mock_rel.return_value = pd.DataFrame()
        mock_mat.return_value = pd.DataFrame()
        
        storico.render_storico_tab()
        
        self.assertTrue(self.mock_st.success.called)

if __name__ == "__main__":
    unittest.main()
