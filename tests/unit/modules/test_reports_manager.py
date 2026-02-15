"""
Test unitari per la gestione dei report.
Copre src/modules/reports_manager.py.
"""

import unittest
from unittest.mock import patch, MagicMock
import datetime
import sqlite3
import sys
from pathlib import Path

# Aggiungi 'src' al path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

from modules.reports_manager import scrivi_o_aggiorna_risposta

class TestReportsManager(unittest.TestCase):

    def setUp(self):
        self.dati_report = {
            "descrizione": "Lavoro su PdL 123456/C",
            "stato": "Completata",
            "report": "Tutto ok"
        }
        self.matricola = "M123"
        self.data_rif = datetime.date(2025, 1, 1)

    @patch("modules.reports_manager.get_db_connection")
    @patch("modules.reports_manager.st")
    @patch("modules.reports_manager._send_validation_email")
    def test_scrivi_o_aggiorna_risposta_success(self, mock_send_email, mock_st, mock_get_conn):
        # Mock DB
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = ("Mario Rossi",)
        mock_get_conn.return_value = mock_conn

        # Execute
        result = scrivi_o_aggiorna_risposta(self.dati_report, self.matricola, self.data_rif)

        # Verify
        self.assertTrue(result)
        mock_cursor.execute.assert_any_call('SELECT "Nome Cognome" FROM contatti WHERE Matricola = ?', (self.matricola,))
        # Check if INSERT was called
        insert_call = [call for call in mock_cursor.execute.call_args_list if "INSERT INTO report_da_validare" in call[0][0]]
        self.assertEqual(len(insert_call), 1)
        self.assertIn("123456/C", insert_call[0][0][1]) # Check if PDL was extracted      

        mock_send_email.assert_called_once()
        mock_st.cache_data.clear.assert_called_once()

    @patch("modules.reports_manager.get_db_connection")
    @patch("modules.reports_manager.st")
    def test_scrivi_o_aggiorna_risposta_user_not_found(self, mock_st, mock_get_conn):     
        # Mock DB
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = None
        mock_get_conn.return_value = mock_conn

        # Execute
        result = scrivi_o_aggiorna_risposta(self.dati_report, self.matricola, self.data_rif)

        # Verify
        self.assertFalse(result)
        mock_st.error.assert_called_once_with(f"Utente {self.matricola} non trovato.")    

    @patch("modules.reports_manager.get_db_connection")
    @patch("modules.reports_manager.st")
    def test_scrivi_o_aggiorna_risposta_db_error(self, mock_st, mock_get_conn):
        # Mock DB to raise error on cursor.execute (inside scrivi_o_aggiorna_risposta)
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.side_effect = sqlite3.Error("DB Failure")
        mock_get_conn.return_value = mock_conn

        # Execute
        result = scrivi_o_aggiorna_risposta(self.dati_report, self.matricola, self.data_rif)

        # Verify
        self.assertFalse(result)
        mock_st.error.assert_called_once()
        self.assertIn("Errore salvataggio report", mock_st.error.call_args[0][0])

if __name__ == "__main__":
    unittest.main()
