"""
Test unitari per l'integrità dei dati.
"""

import datetime
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

import modules.reports_manager as reports_manager

class TestDataIntegrity(unittest.TestCase):
    
    @patch("modules.pdf_utils.FPDF")
    def test_generate_on_call_pdf_success(self, mock_fpdf):
        from modules.pdf_utils import generate_on_call_pdf
        mock_inst = mock_fpdf.return_value
        res = generate_on_call_pdf([], "Gennaio", 2025)
        self.assertIsNotNone(res)

    def test_generate_on_call_pdf_invalid_month(self):
        from modules.pdf_utils import generate_on_call_pdf
        res = generate_on_call_pdf([], "MeseInesistente", 2025)
        self.assertIsNone(res)

    @patch("modules.reports_manager.DatabaseEngine.get_connection")
    @patch("modules.reports_manager.datetime")
    @patch("modules.reports_manager._send_validation_email")
    @patch("streamlit.cache_data.clear")
    @patch("modules.database.db_reports.insert_report", return_value=True)
    def test_scrivi_o_aggiorna_risposta_success(
        self, mock_insert, mock_clear, mock_send_email, mock_datetime, mock_get_conn
    ):
        # Mock DB
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = ["Mario Rossi"]
        mock_get_conn.return_value = mock_conn

        # Mock datetime
        mock_now = datetime.datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.datetime.now.return_value = mock_now

        dati = {
            "descrizione": "PdL 123456 - Test Activity",
            "stato": "Completato",
            "report": "Test report content",
        }

        result = reports_manager.scrivi_o_aggiorna_risposta(dati, "U1", datetime.date(2025, 1, 1))

        self.assertTrue(result)
        self.assertTrue(mock_insert.called)
        # Verifica PdL estratto
        self.assertEqual(mock_insert.call_args[0][0]["pdl"], "123456")

    @patch("modules.reports_manager.DatabaseEngine.get_connection")
    @patch("modules.reports_manager.st")
    def test_scrivi_o_aggiorna_risposta_user_not_found(self, mock_st, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = None
        mock_get_conn.return_value = mock_conn

        dati = {"descrizione": "PdL 123456", "stato": "OK", "report": "Test"}
        result = reports_manager.scrivi_o_aggiorna_risposta(dati, "U1", datetime.date(2025, 1, 1))

        self.assertFalse(result)
        mock_st.error.assert_called()

if __name__ == "__main__":
    unittest.main()
