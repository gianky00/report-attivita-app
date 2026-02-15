
import unittest
import sqlite3
import pandas as pd
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import modules.shifts.logic_market as market

class TestLogicMarketDeepDive(unittest.TestCase):
    
    @patch('streamlit.error')
    @patch('modules.shifts.logic_market.get_user_by_matricola')
    def test_richiedi_sostituzione_user_not_found(self, mock_get, mock_err):
        mock_get.return_value = None
        result = market.richiedi_sostituzione_logic("M1", "M2", "T1")
        self.assertFalse(result)
        mock_err.assert_called_with("Utente richiedente non trovato.")

    @patch('streamlit.success')
    @patch('streamlit.toast')
    @patch('modules.shifts.logic_market.crea_notifica')
    @patch('modules.shifts.logic_market.add_substitution_request')
    @patch('modules.shifts.logic_market.get_user_by_matricola')
    def test_richiedi_sostituzione_success(self, mock_get, mock_add, mock_notif, mock_toast, mock_succ):
        mock_get.return_value = {"Nome Cognome": "Mario"}
        mock_add.return_value = True
        
        result = market.richiedi_sostituzione_logic("M1", "M2", "T1")
        
        self.assertTrue(result)
        mock_notif.assert_called()
        mock_succ.assert_called()

    @patch('streamlit.error')
    @patch('modules.shifts.logic_market.get_substitution_request_by_id')
    def test_rispondi_sostituzione_invalid(self, mock_get, mock_err):
        mock_get.return_value = None
        result = market.rispondi_sostituzione_logic("REQ1", "M2", True)
        self.assertFalse(result)
        mock_err.assert_called_with("Richiesta non più valida.")

    @patch('streamlit.info')
    @patch('modules.shifts.logic_market.delete_substitution_request')
    @patch('modules.shifts.logic_market.crea_notifica')
    @patch('modules.shifts.logic_market.get_substitution_request_by_id')
    def test_rispondi_sostituzione_refused(self, mock_get, mock_notif, mock_del, mock_info):
        mock_get.return_value = {"Richiedente_Matricola": "M1", "ID_Turno": "T1"}
        from unittest.mock import ANY
        result = market.rispondi_sostituzione_logic("REQ1", "M2", False)
        self.assertTrue(result)
        mock_notif.assert_called_with("M1", ANY)
        mock_info.assert_called_with("Hai rifiutato la richiesta.")

    @patch('streamlit.error')
    @patch('modules.shifts.logic_market.add_substitution_request')
    @patch('modules.shifts.logic_market.update_booking_user')
    @patch('modules.shifts.logic_market.get_substitution_request_by_id')
    def test_rispondi_sostituzione_error_update(self, mock_get, mock_upd, mock_add, mock_err):
        req = {"Richiedente_Matricola": "M1", "ID_Turno": "T1"}
        mock_get.return_value = req
        mock_upd.return_value = False # Simulate DB failure
        
        result = market.rispondi_sostituzione_logic("REQ1", "M2", True)
        
        self.assertFalse(result)
        mock_err.assert_called_with("Errore di aggiornamento.")
        mock_add.assert_called_with(req) # Verify retry add

    @patch('streamlit.success')
    @patch('modules.shifts.logic_market.get_all_users')
    @patch('modules.shifts.logic_market.get_shift_by_id')
    @patch('modules.shifts.logic_market.add_bacheca_item')
    @patch('modules.shifts.logic_market.get_db_connection')
    @patch('modules.shifts.logic_market.get_booking_by_user_and_shift')
    def test_pubblica_turno_logic_complex(self, mock_book, mock_conn, mock_add, mock_shift, mock_all, mock_succ):
        mock_book.return_value = {"ID_Prenotazione": "P1", "RuoloOccupato": "Tecnico"}
        mock_shift.return_value = {"Data": "2023-01-01", "Descrizione": "Turno X"}
        mock_all.return_value = pd.DataFrame([{"Matricola": "M2"}, {"Matricola": "M1"}])
        
        result = market.pubblica_turno_in_bacheca_logic("M1", "T1")
        
        self.assertTrue(result)
        mock_succ.assert_called()

    @patch('streamlit.error')
    @patch('modules.shifts.logic_market.get_bacheca_item_by_id')
    def test_prendi_turno_logic_checks(self, mock_get, mock_err):
        # Scenario: Requested role mismatch
        mock_get.return_value = {"Stato": "Disponibile", "Ruolo_Originale": "Tecnico", "ID_Turno": "T1"}
        result = market.prendi_turno_da_bacheca_logic("M2", "Aiutante", "B1")
        self.assertFalse(result)
        mock_err.assert_called_with("Richiesto ruolo 'Tecnico'.")

    @patch('streamlit.balloons')
    @patch('streamlit.success')
    @patch('modules.shifts.logic_market.add_booking')
    @patch('modules.shifts.logic_market.update_bacheca_item')
    @patch('modules.shifts.logic_market.get_db_connection')
    @patch('modules.shifts.logic_market.get_bacheca_item_by_id')
    def test_prendi_turno_success(self, mock_get, mock_conn, mock_upd, mock_add, mock_succ, mock_ball):
        mock_get.return_value = {"Stato": "Disponibile", "Ruolo_Originale": "Aiutante", "ID_Turno": "T1", "Tecnico_Originale_Matricola": "M1"}
        
        result = market.prendi_turno_da_bacheca_logic("M2", "Aiutante", "B1")
        
        self.assertTrue(result)
        mock_upd.assert_called()
        mock_add.assert_called()
        mock_ball.assert_called()

if __name__ == '__main__':
    unittest.main()
