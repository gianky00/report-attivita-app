
import unittest
import sys
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

from tests.unit.modules.st_mock_helper import MockSessionState
from components.forms import debriefing_form, relazione_oncall_form, shift_edit_form

class TestUIFormsMock(unittest.TestCase):
    def setUp(self):
        self.state_dict = {
            "debriefing_task": {"pdl": "P1", "attivita": "Test Task", "section_key": "today"},
            "authenticated_user": "U1",
            "relazione_testo": "",
        }
        self.session_state = MockSessionState(self.state_dict)
        
        self.mocks = {}
        
        # Patch Streamlit
        for m_name in ['markdown', 'subheader', 'text_area', 'selectbox', 'columns', 
                       'button', 'warning', 'success', 'error', 'rerun', 'caption', 
                       'form', 'form_submit_button', 'spinner', 'toast', 'info', 'text_input',
                       'date_input', 'time_input', 'multiselect']:
            patcher = patch(f'streamlit.{m_name}')
            mock_obj = patcher.start()
            self.mocks[m_name] = mock_obj
            self.addCleanup(patcher.stop)
            
            if m_name == 'columns':
                 def side_effect(spec, *args, **kwargs):
                     count = spec if isinstance(spec, int) else len(spec)
                     cols = [MagicMock() for _ in range(count)]
                     for c in cols: 
                         c.__enter__.return_value = c
                         # Attach mocked button methods to columns
                         c.button = self.mocks['button']
                         c.form_submit_button = self.mocks['form_submit_button']
                     return cols
                 mock_obj.side_effect = side_effect
                 
            if m_name in ['form', 'spinner']:
                mock_obj.return_value.__enter__.return_value = MagicMock()
        
        # Patch Session State
        st_ss_patcher = patch('streamlit.session_state', self.session_state)
        st_ss_patcher.start()
        self.addCleanup(st_ss_patcher.stop)
        
    def test_debriefing_form_render_and_submit(self):
        # Patch data manager
        with patch('components.forms.debriefing_form.scrivi_o_aggiorna_risposta', return_value=True) as mock_save:
            # First button (Invia) returns True, Second (Annulla) returns False
            self.mocks['button'].side_effect = [True, False] 
            self.mocks['text_area'].return_value = "Report Content"
            self.mocks['selectbox'].return_value = "Completato"
            
            debriefing_form.render_debriefing_ui({}, "U1", datetime.date.today())
            
            mock_save.assert_called()
            self.mocks['success'].assert_called()
            self.mocks['rerun'].assert_called()
            # It should be deleted exactly once
            self.assertNotIn("debriefing_task", self.session_state)

    def test_relazione_oncall_form_render(self):
        with patch('components.forms.relazione_oncall_form.get_all_users', return_value=MagicMock()), \
             patch('components.forms.relazione_oncall_form.get_report_knowledge_base_count', return_value=5):
             
             # Ensure form_submit_buttons return False so handlers aren't triggered
             self.mocks['form_submit_button'].return_value = False
             
             relazione_oncall_form.render_relazione_reperibilita_ui("U1", "User One")
             
             self.mocks['subheader'].assert_any_call("Compila Relazione di Reperibilità")
             self.mocks['caption'].assert_any_call(":material/info: KB IA: 5 relazioni.")

    def test_relazione_oncall_submission(self):
        with patch('components.forms.relazione_oncall_form.salva_relazione', return_value=True) as mock_save, \
             patch('components.forms.relazione_oncall_form._send_relazione_email') as mock_email:
             
             # Call private handler directly to test logic
             relazione_oncall_form._handle_submission(
                 datetime.date.today(), "Testo relazione", "User One", "Nessuno", "08:00", "20:00"
             )
             
             mock_save.assert_called()
             mock_email.assert_called()
             self.mocks['success'].assert_called()
             self.mocks['rerun'].assert_called()

    def test_shift_edit_form_render_missing_id(self):
        self.session_state.editing_turno_id = None
        shift_edit_form.render_edit_shift_form()
        self.mocks['error'].assert_called_with("ID Turno mancante.")

    def test_shift_edit_form_render_success(self):
        self.session_state.editing_turno_id = "S1"
        
        mock_shift = {"Descrizione": "Turno 1", "Data": "2025-01-01", "OraInizio": "09:00", "OraFine": "18:00"}
        mock_bookings = MagicMock()
        mock_bookings.set_index.return_value.__getitem__.return_value.to_dict.return_value = {"U1": "Tecnico"}
        
        with patch('components.forms.shift_edit_form.get_shift_by_id', return_value=mock_shift), \
             patch('components.forms.shift_edit_form.get_bookings_for_shift', return_value=mock_bookings), \
             patch('components.forms.shift_edit_form.get_all_users', return_value=MagicMock()):
             
             shift_edit_form.render_edit_shift_form()
             
             self.mocks['subheader'].assert_called_with("Modifica Turno: Turno 1")
             self.mocks['form'].assert_called()

if __name__ == '__main__':
    unittest.main()
