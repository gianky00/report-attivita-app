
import unittest
import sys
import datetime
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

from tests.unit.modules.st_mock_helper import MockSessionState
from components.ui import activity_ui, notifications_ui

class TestUIComponentsMock(unittest.TestCase):
    def setUp(self):
        self.state_dict = {
            "completed_tasks_today": [],
            "authenticated_user": "U1",
        }
        self.session_state = MockSessionState(self.state_dict)
        
        self.mocks = {}
        
        # Patch Streamlit
        for m_name in ['markdown', 'expander', 'toggle', 'info', 'success', 'divider', 
                       'button', 'popover', 'write', 'caption', 'rerun', 'columns', 'container']:
            patcher = patch(f'streamlit.{m_name}')
            mock_obj = patcher.start()
            self.mocks[m_name] = mock_obj
            self.addCleanup(patcher.stop)
            
            if m_name in ['expander', 'popover', 'container']:
                mock_obj.return_value.__enter__.return_value = MagicMock()
                
            if m_name == 'columns':
                 def side_effect(spec, *args, **kwargs):
                     count = spec if isinstance(spec, int) else len(spec)
                     cols = [MagicMock() for _ in range(count)]
                     for c in cols: c.__enter__.return_value = c
                     return cols
                 mock_obj.side_effect = side_effect

        # Patch Session State
        st_ss_patcher = patch('streamlit.session_state', self.session_state)
        st_ss_patcher.start()
        self.addCleanup(st_ss_patcher.stop)

    def test_visualizza_storico_organizzato(self):
        storico = [
            {"Data_Riferimento_dt": "2025-01-01", "Tecnico": "U1", "Report": "R1"},
            {"Data_Riferimento_dt": "2025-01-02", "Tecnico": "U2", "Report": "R2"}
        ]
        
        self.mocks['toggle'].return_value = True
        
        activity_ui.visualizza_storico_organizzato(storico, "P1")
        
        self.mocks['expander'].assert_called()
        self.mocks['toggle'].assert_called()
        self.mocks['info'].assert_called() # Shows report

    def test_visualizza_storico_empty(self):
        activity_ui.visualizza_storico_organizzato([], "P1")
        self.mocks['markdown'].assert_called_with("*Nessuno storico disponibile per questo PdL.*")

    def test_disegna_sezione_attivita_empty(self):
        activity_ui.disegna_sezione_attivita([], "today", "Tecnico")
        self.mocks['success'].assert_called_with("Tutte le attività per questa sezione sono state compilate.")

    def test_disegna_sezione_attivita_with_tasks(self):
        tasks = [
            {"pdl": "P1", "attivita": "Task 1", "data_attivita": datetime.date.today(), "team": []}
        ]
        
        # Mock _render_unvalidated_section to avoid external dep issues
        with patch('components.ui.activity_ui._render_unvalidated_section'):
            activity_ui.disegna_sezione_attivita(tasks, "today", "Tecnico")
            
            self.mocks['expander'].assert_called() # render_attivita_card calls expander
            self.mocks['button'].assert_called() # Compile button

    def test_notification_center_empty(self):
        notifications_ui.render_notification_center([], "U1")
        
        self.mocks['popover'].assert_called()
        self.mocks['write'].assert_called_with("Nessuna notifica.")

    def test_notification_center_with_data(self):
        notifs = [
            {"ID_Notifica": 1, "Timestamp": "2025-01-01 10:00", "Messaggio": "Msg 1", "Stato": "non letta"}
        ]
        
        with patch('components.ui.notifications_ui.segna_notifica_letta') as mock_mark:
            self.mocks['button'].return_value = True # Click 'letto'
            
            notifications_ui.render_notification_center(notifs, "U1")
            
            self.mocks['popover'].assert_called()
            self.mocks['markdown'].assert_called()
            mock_mark.assert_called_with(1)
            self.mocks['rerun'].assert_called()

if __name__ == '__main__':
    unittest.main()
