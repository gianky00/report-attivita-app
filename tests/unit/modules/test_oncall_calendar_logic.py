
import unittest
import datetime
import pandas as pd
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import pages.shifts.oncall_calendar_view as calendar
from tests.unit.modules.st_mock_helper import MockSessionState

class TestOncallCalendarLogic(unittest.TestCase):
    
    @patch('streamlit.subheader')
    @patch('streamlit.tabs')
    @patch('streamlit.divider')
    @patch('pages.shifts.oncall_calendar_view._render_oncall_filters')
    @patch('pages.shifts.oncall_calendar_view._render_oncall_export_section')
    @patch('pages.shifts.oncall_calendar_view._render_oncall_navigation')
    @patch('pages.shifts.oncall_calendar_view._render_oncall_calendar_grid')
    def test_render_reperibilita_tab_base(self, mock_grid, mock_nav, mock_exp, mock_filt, mock_div, mock_tabs, mock_sub):
        # Use MockSessionState
        with patch('streamlit.session_state', MockSessionState()):
            df_p = pd.DataFrame()
            df_c = pd.DataFrame()
            
            calendar.render_reperibilita_tab(df_p, df_c, "M1", "Tecnico")
            
            mock_sub.assert_called_with("Calendario Reperibilità")
            mock_nav.assert_called()
            mock_grid.assert_called()

    @patch('streamlit.selectbox')
    @patch('pages.shifts.oncall_calendar_view.get_shift_by_id')
    @patch('pages.shifts.oncall_calendar_view.get_all_users')
    def test_render_oncall_edit_form_success(self, mock_users, mock_shift, mock_sel):
        state = MockSessionState({"editing_oncall_shift_id": "S1"})
        with patch('streamlit.session_state', state), \
             patch('streamlit.container', return_value=MagicMock()):
            mock_shift.return_value = {"Data": "2023-01-01"}
            mock_users.return_value = pd.DataFrame([
                {"Matricola": "T1", "Nome Cognome": "Tech 1"},
                {"Matricola": "T2", "Nome Cognome": "Tech 2"}
            ])
            
            calendar._render_oncall_edit_form("ADM01")
            
            self.assertEqual(mock_sel.call_count, 2) 
            mock_shift.assert_called_with("S1")

    def test_render_oncall_navigation_next(self):
        state = MockSessionState({"week_start_date": datetime.date(2023, 1, 2)})
        # Create column mocks with button side effects
        c0, c1, c2 = MagicMock(), MagicMock(), MagicMock()
        c0.button.return_value = False
        c2.button.return_value = True
        
        with patch('streamlit.session_state', state), \
             patch('streamlit.columns', return_value=[c0, c1, c2]), \
             patch('streamlit.rerun'):
            
            calendar._render_oncall_navigation()
            self.assertEqual(state.week_start_date, datetime.date(2023, 1, 9))

    def test_render_oncall_navigation_prev(self):
        state = MockSessionState({"week_start_date": datetime.date(2023, 1, 9)})
        c0, c1, c2 = MagicMock(), MagicMock(), MagicMock()
        c0.button.return_value = True
        c2.button.return_value = False
        
        with patch('streamlit.session_state', state), \
             patch('streamlit.columns', return_value=[c0, c1, c2]), \
             patch('streamlit.rerun'):
            
            calendar._render_oncall_navigation()
            self.assertEqual(state.week_start_date, datetime.date(2023, 1, 2))

if __name__ == '__main__':
    unittest.main()
