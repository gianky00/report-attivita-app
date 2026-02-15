
import unittest
import sys
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

from tests.unit.modules.st_mock_helper import MockSessionState

class TestAppNavigationMock(unittest.TestCase):
    def setUp(self):
        self.state_dict = {
            "login_state": "logged_in",
            "authenticated_user": "U1",
            "ruolo": "Tecnico",
            "main_tab": "Attività Assegnate",
            "expanded_menu": "Attività",
            "navigated": False,
        }
        self.session_state = MockSessionState(self.state_dict)
        
        # Mocks container
        self.mocks = {}
        
        # --- Patch Streamlit ---
        for m_name in ['set_page_config', 'title', 'markdown', 'write', 'error', 'stop', 
                       'sidebar', 'tabs', 'success', 'info', 'container', 'columns', 
                       'expander', 'rerun']:
            patcher = patch(f'streamlit.{m_name}')
            mock_obj = patcher.start()
            self.mocks[m_name] = mock_obj
            self.addCleanup(patcher.stop)
            
            if m_name == 'stop':
                mock_obj.side_effect = SystemExit

            # Setup context managers
            if m_name in ['sidebar', 'container', 'expander']:
                mock_obj.return_value.__enter__.return_value = MagicMock()
            
            if m_name == 'columns':
                 def side_effect(spec, *args, **kwargs):
                     count = spec if isinstance(spec, int) else len(spec)
                     cols = [MagicMock() for _ in range(count)]
                     for c in cols: c.__enter__.return_value = c
                     return cols
                 mock_obj.side_effect = side_effect

            if m_name == 'tabs':
                mock_list = [MagicMock() for _ in range(5)] # Fixed list is safe for tabs usually
                for m in mock_list:
                    m.__enter__.return_value = m
                mock_obj.return_value = mock_list

        # Patch st.components.v1.html
        html_patcher = patch('streamlit.components.v1.html')
        self.mocks['html'] = html_patcher.start()
        self.addCleanup(html_patcher.stop)

        # --- Patch Session State ---
        st_ss_patcher = patch('streamlit.session_state', self.session_state)
        st_ss_patcher.start()
        self.addCleanup(st_ss_patcher.stop)
        
        # --- Patch App Modules ---
        # We need to patch functions imported in app.py directly where they are used
        
        # Auth & User
        self.patch_app_func('get_user_by_matricola', return_value={"Nome Cognome": "Test User", "Ruolo": "Tecnico"})
        
        # DB & Data
        self.patch_app_func('get_all_users', return_value=[{"Nome Cognome": "Test User", "Matricola": "U1"}])
        self.patch_app_func('trova_attivita', return_value=[])
        self.patch_app_func('recupera_attivita_non_rendicontate', return_value=[])
        self.patch_app_func('get_validated_intervention_reports', return_value=MagicMock(empty=True))
        
        # Logic
        self.patch_app_func('sync_oncall_shifts')
        self.patch_app_func('check_pyarmor_license')
        
        # Sidebar & Components
        self.patch_app_func('render_sidebar')
        self.patch_app_func('disegna_sezione_attivita')
        
        # Pages
        self.patch_app_func('render_gestione_turni_tab')
        self.patch_app_func('render_richieste_tab')
        self.patch_app_func('render_guida_tab')
        self.patch_app_func('render_caposquadra_view')
        self.patch_app_func('render_sistema_view')
        
        # Page redirection targets
        self.patch_app_func('render_edit_shift_form')
        self.patch_app_func('render_debriefing_ui')
        self.patch_app_func('carica_knowledge_core', return_value={})
        
        import app
        self.app = app

    def patch_app_func(self, name, return_value=None):
        patcher = patch(f'app.{name}')
        mock = patcher.start()
        if return_value is not None:
            mock.return_value = return_value
        self.mocks[name] = mock
        self.addCleanup(patcher.stop)

    def test_main_app_initialization(self):
        """Test basic initialization of main_app."""
        self.app.main_app("U1", "Tecnico")
        
        self.mocks['set_page_config'].assert_called_with(
            layout="wide", page_title="Gestionale", initial_sidebar_state="collapsed"
        )
        # check_pyarmor_license is called at module level, not inside main_app
        self.mocks['sync_oncall_shifts'].assert_called()
        self.mocks['render_sidebar'].assert_called_with("U1", "Test User", "Tecnico")

    def test_navigation_attivita_assegnate_tecnico(self):
        """Test 'Attività Assegnate' tab for Tecnico."""
        self.session_state.main_tab = "Attività Assegnate"
        
        self.app.main_app("U1", "Tecnico")
        
        # Should create tabs for activities
        self.mocks['tabs'].assert_called()
        self.mocks['trova_attivita'].assert_called() # Today's tasks
        self.mocks['disegna_sezione_attivita'].assert_called()

    def test_navigation_gestione_turni(self):
        """Test navigation to 'Gestione Turni'."""
        self.session_state.main_tab = "Gestione Turni"
        
        self.app.main_app("U1", "Tecnico")
        
        self.mocks['render_gestione_turni_tab'].assert_called_with("U1", "Tecnico")
        self.mocks['render_sidebar'].assert_called()

    def test_navigation_richieste(self):
        """Test navigation to 'Richieste'."""
        self.session_state.main_tab = "Richieste"
        
        self.app.main_app("U1", "Tecnico")
        
        self.mocks['render_richieste_tab'].assert_called_with("U1", "Tecnico", "Test User")

    def test_navigation_guida(self):
        """Test navigation to 'Guida'."""
        self.session_state.main_tab = "Guida"
        
        self.app.main_app("U1", "Tecnico")
        
        self.mocks['render_guida_tab'].assert_called_with("Tecnico")

    def test_admin_navigation_caposquadra(self):
        """Test Admin navigation to 'Caposquadra'."""
        self.session_state.main_tab = "Caposquadra"
        
        with self.assertRaises(SystemExit): # st.stop() calls sys.exit
             self.app.main_app("ADM1", "Amministratore")
             
        self.mocks['render_caposquadra_view'].assert_called_with("ADM1")

    def test_admin_navigation_sistema(self):
        """Test Admin navigation to 'Sistema'."""
        self.session_state.main_tab = "Sistema"
        
        with self.assertRaises(SystemExit):
             self.app.main_app("ADM1", "Amministratore")
             
        self.mocks['render_sistema_view'].assert_called()

    def test_redirection_edit_shift(self):
        """Test redirection when 'editing_turno_id' is set."""
        self.session_state.editing_turno_id = "S123"
        
        self.app.main_app("U1", "Tecnico")
        
        self.mocks['render_edit_shift_form'].assert_called()
        # Should verify sidebar is NOT rendered or standard tabs skipped
        # In current code, valid check is if render_edit_shift_form is called
        # Note: render_sidebar IS NOT called in this branch
        self.mocks['render_sidebar'].assert_not_called()

    def test_redirection_debriefing(self):
        """Test redirection when 'debriefing_task' is set."""
        self.session_state.debriefing_task = {"id": 1, "data_attivita": datetime.date(2025, 1, 1)}
        
        self.app.main_app("U1", "Tecnico")
        
        self.mocks['carica_knowledge_core'].assert_called()
        self.mocks['render_debriefing_ui'].assert_called()
        self.mocks['render_sidebar'].assert_not_called()

    def test_auto_navigation_script(self):
        """Test injection of navigation script when 'navigated' is True."""
        self.session_state.navigated = True
        
        self.app.main_app("U1", "Tecnico")
        
        self.mocks['html'].assert_called()
        self.assertFalse(self.session_state.navigated)

if __name__ == '__main__':
    unittest.main()
