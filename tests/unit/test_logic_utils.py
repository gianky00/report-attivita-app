import datetime
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir / "src"))

from modules import oncall_logic, pdf_utils, utils


class TestLogicUtils(unittest.TestCase):
    # --- On-Call Logic Tests ---
    def test_get_on_call_pair_valid_date(self):
        """Test on-call pair calculation for a known date."""
        date = datetime.date(2023, 1, 1)
        pair = oncall_logic.get_on_call_pair(date)
        self.assertIsInstance(pair, tuple)
        self.assertEqual(len(pair), 2)
        self.assertEqual(len(pair[0]), 2)  # (Name, Role)

    def test_get_on_call_pair_invalid_input(self):
        """Test graceful handling of invalid input."""
        res = oncall_logic.get_on_call_pair("not a date")
        self.assertEqual(res, (("N/D", ""), ("N/D", "")))

    def test_get_next_on_call_week(self):
        """Test finding the next on-call week."""
        start_date = datetime.date.today()
        with patch(
            "modules.oncall_logic.ON_CALL_ROTATION",
            [
                (("ROSSI", "Tecnico"), ("BIANCHI", "Aiutante")),
                (("VERDI", "Tecnico"), ("NERI", "Aiutante")),
            ],
        ):
            # Test finding ROSSI
            next_date = oncall_logic.get_next_on_call_week("ROSSI", start_date)
            if next_date:
                self.assertIsInstance(next_date, datetime.date)
                self.assertEqual(next_date.weekday(), 4)  # Must be Friday

            # Test finding unknown
            self.assertIsNone(oncall_logic.get_next_on_call_week("UNKNOWN", start_date))

    # --- Utils Tests ---
    def test_calculate_shift_duration_standard(self):
        """Test duration calculation within same day."""
        start = "2023-01-01T08:00:00"
        end = "2023-01-01T16:00:00"
        duration = utils.calculate_shift_duration(start, end)
        self.assertEqual(duration, 8.0)

    def test_calculate_shift_duration_overnight(self):
        """Test duration calculation crossing midnight."""
        start = "2023-01-01T22:00:00"
        end = "2023-01-02T06:00:00"
        duration = utils.calculate_shift_duration(start, end)
        self.assertEqual(duration, 8.0)

        start_same = "2023-01-01T22:00:00"
        end_same = "2023-01-01T06:00:00"
        duration_same = utils.calculate_shift_duration(start_same, end_same)
        self.assertEqual(duration_same, 8.0)

    def test_merge_time_slots(self):
        """Test merging overlapping time slots."""
        slots = ["08:00-10:00", "09:00-11:00", "13:00-14:00"]
        merged = utils.merge_time_slots(slots)
        self.assertEqual(merged, ["08:00 - 11:00", "13:00 - 14:00"])

    def test_merge_time_slots_empty(self):
        self.assertEqual(utils.merge_time_slots([]), [])
        self.assertEqual(utils.merge_time_slots(["invalid"]), [])

    # --- PDF Utils Tests ---
    @patch("modules.pdf_utils.PDF")
    @patch("modules.pdf_utils.calendar")
    @patch("pathlib.Path.mkdir")
    def test_generate_on_call_pdf_success(self, mock_mkdir, mock_calendar, mock_pdf_class):
        """Test PDF generation flow."""
        # Setup mock calendar to contain English months regardless of locale
        mock_calendar.month_name = [
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        mock_calendar.monthrange.return_value = (0, 31)

        # Setup mock PDF
        mock_pdf_instance = MagicMock()
        mock_pdf_class.return_value = mock_pdf_instance

        data = [
            {"Data": "2023-01-01", "RuoloOccupato": "Tecnico", "Nome Cognome": "Rossi"},
            {"Data": "2023-01-01", "RuoloOccupato": "Aiutante", "Nome Cognome": "Bianchi"},
        ]

        # Use JANUARY to match the english_month lookup in pdf_utils.py
        result = pdf_utils.generate_on_call_pdf(data, "gennaio", 2023)

        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".pdf"))
        # Verify output was called on the instance
        self.assertTrue(mock_pdf_instance.output.called)

    def test_generate_on_call_pdf_invalid_month(self):
        """Test PDF generation with invalid month."""
        res = pdf_utils.generate_on_call_pdf([], "MeseFinto", 2023)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
