import unittest
import datetime
import sqlite3
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

from modules.reports_manager import scrivi_o_aggiorna_risposta

class TestReportsManager(unittest.TestCase):
    def setUp(self):
        self.matricola = "12345"
        self.data_rif = datetime.date(2025, 1, 1)
        self.dati_report = {
            "descrizione": "PdL 123456 - Manutenzione",
            "report": "Tutto ok",
            "stato": "TERMINATA"
        }

    @patch("modules.reports_manager.DatabaseEngine.get_connection")
    @patch("modules.reports_manager.st")
    @patch("modules.reports_manager._send_validation_email")
    @patch("modules.database.db_reports.insert_report", return_value=True)
    def test_scrivi_o_aggiorna_risposta_success(self, mock_insert, mock_send_email, mock_st, mock_get_conn):
        # Mock DB per recupero nome utente
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = ("Mario Rossi",)
        mock_get_conn.return_value = mock_conn

        # Execute
        result = scrivi_o_aggiorna_risposta(self.dati_report, self.matricola, self.data_rif)

        # Verify
        self.assertTrue(result)
        # Verifica che insert_report sia stato chiamato con i dati corretti
        self.assertTrue(mock_insert.called)
        report_data = mock_insert.call_args[0][0]
        self.assertEqual(report_data["pdl"], "123456")
        self.assertEqual(report_data["matricola_tecnico"], self.matricola)

    @patch("modules.reports_manager.DatabaseEngine.get_connection")
    @patch("modules.reports_manager.st")
    def test_scrivi_o_aggiorna_risposta_user_not_found(self, mock_st, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = None
        mock_get_conn.return_value = mock_conn

        result = scrivi_o_aggiorna_risposta(self.dati_report, self.matricola, self.data_rif)
        self.assertFalse(result)
        mock_st.error.assert_called()

    @patch("modules.reports_manager.DatabaseEngine.get_connection")
    @patch("modules.reports_manager.st")
    def test_scrivi_o_aggiorna_risposta_db_error(self, mock_st, mock_get_conn):
        # Usiamo sqlite3.Error invece di Exception generica
        mock_get_conn.side_effect = sqlite3.Error("DB Connection Error")

        result = scrivi_o_aggiorna_risposta(self.dati_report, self.matricola, self.data_rif)
        self.assertFalse(result)
        mock_st.error.assert_called()

if __name__ == "__main__":
    unittest.main()
