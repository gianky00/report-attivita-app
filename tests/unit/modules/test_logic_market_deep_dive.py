import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import modules.shifts.logic_market as market

class TestLogicMarketDeepDive(unittest.TestCase):

    def setUp(self):
        # Mock globale di crea_notifica e log_shift_change per evitare chiamate DB
        self.patcher_notif = patch("modules.shifts.logic_market.crea_notifica", return_value=True)
        self.patcher_log = patch("modules.shifts.logic_market.log_shift_change", return_value=True)
        self.mock_crea_notif = self.patcher_notif.start()
        self.mock_log = self.patcher_log.start()
        
        # Mock globale di st.error/st.success/st.toast/st.balloons
        self.patcher_st_err = patch("streamlit.error")
        self.patcher_st_succ = patch("streamlit.success")
        self.patcher_st_toast = patch("streamlit.toast")
        self.patcher_st_balloons = patch("streamlit.balloons")
        self.mock_st_err = self.patcher_st_err.start()
        self.mock_st_succ = self.patcher_st_succ.start()
        self.mock_st_toast = self.patcher_st_toast.start()
        self.mock_st_balloons = self.patcher_st_balloons.start()

    def tearDown(self):
        self.patcher_notif.stop()
        self.patcher_log.stop()
        self.patcher_st_err.stop()
        self.patcher_st_succ.stop()
        self.patcher_st_toast.stop()
        self.patcher_st_balloons.stop()

    @patch("modules.shifts.logic_market.get_substitution_request_by_id")
    def test_rispondi_sostituzione_invalid(self, mock_get):
        mock_get.return_value = None
        res = market.rispondi_sostituzione_logic("R1", "M1", True)
        self.assertFalse(res)

    @patch("modules.shifts.logic_market.delete_substitution_request")
    @patch("modules.shifts.logic_market.get_user_by_matricola")
    @patch("modules.shifts.logic_market.get_substitution_request_by_id")
    def test_rispondi_sostituzione_refused(self, mock_get, mock_user, mock_del):
        mock_get.return_value = {"Richiedente_Matricola": "M1", "ID_Turno": "T1"}
        mock_user.return_value = {"Nome Cognome": "User 2"}
        res = market.rispondi_sostituzione_logic("R1", "M2", False)
        self.assertTrue(res)

    @patch("modules.shifts.logic_market.update_booking_user")
    @patch("modules.shifts.logic_market.delete_substitution_request")
    @patch("modules.shifts.logic_market.get_user_by_matricola")
    @patch("modules.shifts.logic_market.get_substitution_request_by_id")
    def test_rispondi_sostituzione_error_update(self, mock_get, mock_user, mock_del, mock_upd):
        mock_get.return_value = {"Richiedente_Matricola": "M1", "ID_Turno": "T1"}
        mock_user.return_value = {"Nome Cognome": "User 2"}
        mock_upd.return_value = False
        res = market.rispondi_sostituzione_logic("R1", "M2", True)
        self.assertFalse(res)

    @patch("modules.shifts.logic_market.get_user_by_matricola")
    def test_richiedi_sostituzione_user_not_found(self, mock_user):
        mock_user.return_value = None
        res = market.richiedi_sostituzione_logic("M1", "M2", "T1")
        self.assertFalse(res)

    @patch("modules.shifts.logic_market.add_substitution_request")
    @patch("modules.shifts.logic_market.get_user_by_matricola")
    def test_richiedi_sostituzione_success(self, mock_user, mock_add):
        mock_user.return_value = {"Matricola": "M1", "Nome Cognome": "User 1"}
        mock_add.return_value = True
        res = market.richiedi_sostituzione_logic("M1", "M2", "T1")
        self.assertTrue(res)

    @patch("modules.shifts.logic_market.get_all_users")
    @patch("modules.shifts.logic_market.get_shift_by_id")
    @patch("modules.shifts.logic_market.add_bacheca_item")
    @patch("modules.shifts.logic_market.DatabaseEngine.get_connection")
    @patch("modules.shifts.logic_market.get_booking_by_user_and_shift")
    def test_pubblica_turno_logic_complex(
        self, mock_book, mock_conn, mock_add, mock_shift, mock_all
    ):
        mock_book.return_value = {"ID_Prenotazione": "P1", "RuoloOccupato": "Tecnico"}
        mock_shift.return_value = {"Data": "2023-01-01", "Descrizione": "Turno X"}
        mock_all.return_value = pd.DataFrame([{"Matricola": "M2"}, {"Matricola": "M1"}])
        
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.execute.return_value = MagicMock() # Non usato grazie al mock di log_shift_change, ma per sicurezza

        result = market.pubblica_turno_in_bacheca_logic("M1", "T1")
        self.assertTrue(result)

    @patch("modules.shifts.logic_market.get_bacheca_item_by_id")
    def test_prendi_turno_logic_checks(self, mock_get):
        mock_get.return_value = {"Stato": "Assegnato"}
        res = market.prendi_turno_da_bacheca_logic("M1", "Tecnico", "B1")
        self.assertFalse(res)

    @patch("modules.shifts.logic_market.add_booking")
    @patch("modules.shifts.logic_market.update_bacheca_item")
    @patch("modules.shifts.logic_market.DatabaseEngine.get_connection")
    @patch("modules.shifts.logic_market.get_bacheca_item_by_id")
    def test_prendi_turno_success(
        self, mock_get, mock_conn, mock_upd, mock_add
    ):
        mock_get.return_value = {
            "Stato": "Disponibile",
            "Ruolo_Originale": "Aiutante",
            "ID_Turno": "T1",
            "Tecnico_Originale_Matricola": "M1",
        }
        
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.__enter__.return_value = mock_c

        result = market.prendi_turno_da_bacheca_logic("M2", "Aiutante", "B1")
        self.assertTrue(result)

if __name__ == "__main__":
    unittest.main()
