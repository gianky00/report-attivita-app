
import unittest
import sys
import datetime
import calendar
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# Add src to path
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir / "src"))

from modules import pdf_utils, reports_manager
from components import form_handlers
import pandas as pd

class TestDataIntegrity(unittest.TestCase):
    
    # --- PDF Utils Tests ---
    @patch('modules.pdf_utils.PDF')
    @patch('modules.pdf_utils.Path')
    def test_generate_on_call_pdf_success(self, mock_path, mock_pdf_class):
        # Setup mocks
        mock_pdf_instance = mock_pdf_class.return_value
        mock_pdf_instance.output.return_value = None
        
        # Configure Path mock to return a valid string path
        mock_dir = mock_path.return_value
        mock_file_path = MagicMock()
        mock_file_path.__str__.return_value = "reports/test_report.pdf"
        mock_dir.__truediv__.return_value = mock_file_path
        
        data = [{"Data": "2025-01-01", "RuoloOccupato": "Tecnico", "Nome Cognome": "Mario Rossi"}]
        
        # execution
        result = pdf_utils.generate_on_call_pdf(data, "gennaio", 2025)
        
        # verification
        mock_pdf_class.assert_called()
        mock_pdf_instance.add_page.assert_called()
        mock_pdf_instance.output.assert_called()
        self.assertTrue(result.endswith(".pdf"))

    def test_generate_on_call_pdf_invalid_month(self):
        result = pdf_utils.generate_on_call_pdf([], "invalid_month", 2025)
        self.assertIsNone(result)

    # --- Reports Manager Tests ---
    @patch('modules.reports_manager.get_db_connection')
    @patch('modules.reports_manager.datetime')
    @patch('modules.reports_manager._send_validation_email')
    @patch('streamlit.cache_data.clear')
    def test_scrivi_o_aggiorna_risposta_success(self, mock_clear, mock_send_email, mock_datetime, mock_get_conn):
        # Mock DB
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_get_conn.return_value = mock_conn
        
        # User exists
        mock_cursor.fetchone.return_value = ["Mario Rossi"] 
        
        # Mock datetime
        mock_now = datetime.datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.datetime.now.return_value = mock_now
        
        dati = {
            "descrizione": "PdL 123456 - Test Activity",
            "stato": "Completato",
            "report": "Test report content"
        }
        
        result = reports_manager.scrivi_o_aggiorna_risposta(dati, "U1", datetime.date(2025, 1, 1))
        
        self.assertTrue(result)
        mock_cursor.execute.assert_called()
        # Verify insert into report_da_validare
        insert_call = [args for args in mock_cursor.execute.call_args_list if "INSERT INTO report_da_validare" in args[0][0]]
        self.assertTrue(insert_call)
        
        mock_send_email.assert_called()
        mock_clear.assert_called()
        mock_conn.close.assert_called()

    @patch('modules.reports_manager.get_db_connection')
    def test_scrivi_o_aggiorna_risposta_user_not_found(self, mock_get_conn):
        mock_cursor = mock_get_conn.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = None
        
        with patch('streamlit.error') as mock_error:
            result = reports_manager.scrivi_o_aggiorna_risposta({}, "U1", datetime.date.today())
            self.assertFalse(result)
            mock_error.assert_called_with("Utente U1 non trovato.")

    @patch('modules.email_sender.invia_email_con_outlook_async')
    def test_send_validation_email(self, mock_send):
        reports_manager._send_validation_email(
            "Mario", datetime.date(2025, 1, 1), datetime.datetime.now(), 
            {"descrizione": "Test", "stato": "OK", "report": "Content"}
        )
        mock_send.assert_called()
        args = mock_send.call_args[0]
        self.assertIn("Nuovo Report da Validare", args[0])
        self.assertIn("Content", args[1])

    # --- CSV Export Tests ---
    def test_to_csv(self):
        df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        csv_bytes = form_handlers.to_csv(df)
        self.assertIsInstance(csv_bytes, bytes)
        self.assertIn(b"col1,col2", csv_bytes)
        self.assertIn(b"1,a", csv_bytes)

if __name__ == '__main__':
    import calendar # Import here to ensure it's available for mocking
    unittest.main()
