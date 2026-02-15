import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import modules.shifts.logic_bookings as booking_logic


class TestLogicBookingsDeepDive(unittest.TestCase):
    @patch("modules.shifts.logic_bookings.get_shift_by_id")
    @patch("streamlit.error")
    def test_prenota_turno_shift_not_found(self, mock_error, mock_get_shift):
        mock_get_shift.return_value = None
        result = booking_logic.prenota_turno_logic("M1", "S1", "Tecnico")
        self.assertFalse(result)
        mock_error.assert_called_with("Turno non trovato.")

    @patch("modules.shifts.logic_bookings.get_shift_by_id")
    @patch("modules.shifts.logic_bookings.check_user_oncall_conflict")
    @patch("streamlit.error")
    def test_prenota_turno_oncall_conflict(self, mock_error, mock_conflict, mock_get_shift):
        mock_get_shift.return_value = {"Data": "2023-01-01"}
        mock_conflict.return_value = True

        result = booking_logic.prenota_turno_logic("M1", "S1", "Tecnico")
        self.assertFalse(result)
        # Check that error was called (exact message might vary, so just checking call)
        mock_error.assert_called()
        args, _ = mock_error.call_args
        self.assertIn("Conflitto rilevato", args[0])

    @patch("modules.shifts.logic_bookings.get_shift_by_id")
    @patch("modules.shifts.logic_bookings.check_user_oncall_conflict")
    @patch("modules.shifts.logic_bookings.get_bookings_for_shift")
    @patch("streamlit.error")
    def test_prenota_turno_full_capacity(
        self, mock_error, mock_bookings, mock_conflict, mock_get_shift
    ):
        mock_get_shift.return_value = {"Data": "2023-01-01", "PostiTecnico": 1, "PostiAiutante": 1}
        mock_conflict.return_value = False

        # Simulate full shift
        import pandas as pd

        mock_bookings.return_value = pd.DataFrame(
            [{"RuoloOccupato": "Tecnico"}, {"RuoloOccupato": "Aiutante"}]
        )

        # Try to book as Tecnico
        result = booking_logic.prenota_turno_logic("M1", "S1", "Tecnico")
        self.assertFalse(result)
        mock_error.assert_called_with("Tutti i posti per il ruolo selezionato sono esauriti!")

    @patch("modules.shifts.logic_bookings.get_shift_by_id")
    @patch("modules.shifts.logic_bookings.check_user_oncall_conflict")
    @patch("modules.shifts.logic_bookings.get_bookings_for_shift")
    @patch("modules.shifts.logic_bookings.add_booking")
    @patch("modules.shifts.logic_bookings.log_shift_change")
    @patch("streamlit.success")
    def test_prenota_turno_success(
        self, mock_success, mock_log, mock_add, mock_bookings, mock_conflict, mock_get_shift
    ):
        mock_get_shift.return_value = {"Data": "2023-01-01", "PostiTecnico": 2, "PostiAiutante": 0}
        mock_conflict.return_value = False
        import pandas as pd

        mock_bookings.return_value = pd.DataFrame(
            columns=["RuoloOccupato"]
        )  # Empty bookings with columns

        mock_add.return_value = True

        result = booking_logic.prenota_turno_logic("M1", "S1", "Tecnico")
        self.assertTrue(result)
        mock_add.assert_called()
        mock_log.assert_called()
        mock_success.assert_called()

    @patch("modules.shifts.logic_bookings.get_shift_by_id")
    @patch("modules.shifts.logic_bookings.check_user_oncall_conflict")
    @patch("modules.shifts.logic_bookings.get_bookings_for_shift")
    @patch("modules.shifts.logic_bookings.add_booking")
    @patch("streamlit.error")
    def test_prenota_turno_db_error(
        self, mock_error, mock_add, mock_bookings, mock_conflict, mock_get_shift
    ):
        mock_get_shift.return_value = {"Data": "2023-01-01", "PostiTecnico": 2}
        mock_conflict.return_value = False
        import pandas as pd

        mock_bookings.return_value = pd.DataFrame(columns=["RuoloOccupato"])
        mock_add.return_value = False  # DB failure

        result = booking_logic.prenota_turno_logic("M1", "S1", "Tecnico")
        self.assertFalse(result)
        mock_error.assert_called_with("Errore durante la prenotazione del turno.")

    @patch("modules.shifts.logic_bookings.delete_booking")
    @patch("modules.shifts.logic_bookings.log_shift_change")
    @patch("streamlit.success")
    def test_cancella_prenotazione_success(self, mock_success, mock_log, mock_del):
        mock_del.return_value = True
        result = booking_logic.cancella_prenotazione_logic("M1", "S1")
        self.assertTrue(result)
        mock_del.assert_called_with("M1", "S1")
        mock_log.assert_called()
        mock_success.assert_called()

    @patch("modules.shifts.logic_bookings.delete_booking")
    @patch("streamlit.error")
    def test_cancella_prenotazione_failure(self, mock_error, mock_del):
        mock_del.return_value = False
        result = booking_logic.cancella_prenotazione_logic("M1", "S1")
        self.assertFalse(result)
        mock_error.assert_called_with("Prenotazione non trovata o errore durante la cancellazione.")


if __name__ == "__main__":
    unittest.main()
