
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

    def test_oncall_admin_buttons(self):
        state = MockSessionState({
            "week_start_date": datetime.date(2023, 1, 2),
            "user": {"Ruolo": "Amministratore", "Matricola": "ADM01"}
        })
        
        # Mocking data to ensure we hit the cell rendering
        with patch('streamlit.session_state', state), \
             patch('streamlit.rerun') as mock_rerun, \
             patch('streamlit.columns') as mock_cols, \
             patch('pages.shifts.oncall_calendar_view.get_on_call_pair') as mock_get_pair, \
             patch('pages.shifts.oncall_calendar_view.get_shift_by_id') as mock_get_shift, \
             patch('pages.shifts.oncall_calendar_view.get_bookings_for_shift') as mock_get_bookings, \
             patch('pages.shifts.oncall_calendar_view.get_all_users') as mock_get_users:

            # Mock data setup
            mock_pair = (
                pd.DataFrame([{"Data": "2023-01-02", "ID_Turno": "S1"}]),
                pd.DataFrame([{"ID_Turno": "S1", "Matricola": "U1", "RuoloOccupato": "Reperibile"}])
            )
            mock_get_pair.side_effect = [mock_pair] # Return for the week
            
            mock_users = pd.DataFrame([
                {"Matricola": "U1", "Nome Cognome": "User One"},
                {"Matricola": "ADM01", "Nome Cognome": "Admin User"}
            ])
            mock_get_users.return_value = mock_users

            # Mock columns and buttons inside the cell loop
            # _render_oncall_cell calls st.columns(2) at the end if conditions met
            # We need to ensure that the button click is simulated.
            
            # Scenario: Admin clicks "pencil" (edit) button
            # The code calls c2.button(..., key=f"e_{day}")
            # We need to mock the button return value to be True for a specific call
            
            # Since _render_oncall_cell is called 7 times (for 7 days), and each time creates cols...
            # This is hard to mock via side_effect efficiently without a complex structure.
            # However, we can use the MockSessionState to verify if state was updated IF we can trigger it.
            
            # Easier approach: Unit test `_render_oncall_cell` directly if possible, but it's nested in main render?
            # No, it's not a standalone function in the previous view, let me check the file content again.
            # Ah, I don't see `_render_oncall_cell` in the previous `view_file` output (lines 270-322). 
            # It seems the code from 270-322 *IS* inside `_render_oncall_rendering_logic` or similar.
            # Actually, looking at lines 205-210, `_render_oncall_navigation` is a function.
            # Lines 270+ seem to be part of the main loop in `render_reperibilita_tab`.
            
            # Let's import the module and check if `_render_oncall_cell` exists or if it's inline.
            # I suspect it's inline or I missed the definition.
            # Let's assume I can call `render_reperibilita_tab` and mock things.
            
            # To simulate a specific button click deep in the loop:
            # We can use a custom side effect for the button mock that checks the 'key' argument.
            
            mock_c1 = MagicMock()
            mock_c2 = MagicMock()
            mock_cols.return_value = [mock_c1, mock_c2]
            
            def button_side_effect(*args, **kwargs):
                key = kwargs.get('key', '')
                # Simulate clicking the edit button for Jan 2nd
                if key == "e_2023-01-02":
                    return True
                return False
            
            mock_c2.button.side_effect = button_side_effect
            
            calendar.render_reperibilita_tab()
            
            # Verification
            self.assertEqual(state.editing_oncall_shift_id, "S1")
            mock_rerun.assert_called()

if __name__ == '__main__':
    unittest.main()
