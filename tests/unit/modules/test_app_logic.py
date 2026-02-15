
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

class MockSessionState:
    def __init__(self, data):
        self._data = data
    def __getattr__(self, k):
        if k in self._data: return self._data[k]
        return None
    def __setattr__(self, k, v):
        if k == "_data": self.__dict__['_data'] = v
        else: self._data[k] = v
    def __getitem__(self, k):
        return self._data[k]
    def __setitem__(self, k, v):
        self._data[k] = v
    def __contains__(self, k):
        return k in self._data
    def get(self, k, default=None):
        return self._data.get(k, default)
    def update(self, other):
        self._data.update(other)
    def __delitem__(self, k):
        if k in self._data: del self._data[k]

class TestAppLogic(unittest.TestCase):
    def setUp(self):
        self.state_dict = {"login_state": "password", "authenticated_user": None}
        self.session_state = MockSessionState(self.state_dict)
        self.qp_dict = {}

        # Patching manual map
        self.mocks = {}

        # Streamlit common
        for m_name in ['set_page_config', 'title', 'rerun', 'error', 'success', 'info',
                       'markdown', 'caption', 'image', 'stop', 'expander', 'columns',
                       'tabs', 'sidebar', 'spinner', 'toast', 'divider', 'write',
                       'text_input', 'form', 'form_submit_button']:
            patcher = patch(f'streamlit.{m_name}')
            mock_obj = patcher.start()
            self.mocks[m_name] = mock_obj
            self.addCleanup(patcher.stop)

            if m_name == 'form_submit_button':
                mock_obj.return_value = False
            if m_name in ['expander', 'spinner', 'form', 'sidebar']:
                mock_obj.return_value.__enter__.return_value = MagicMock()
            if m_name in ['tabs', 'columns']:
                mock_obj.return_value = [MagicMock() for _ in range(5)]
                for item in mock_obj.return_value:
                    item.__enter__.return_value = MagicMock()

        # Custom patches
        st_ss_patcher = patch('streamlit.session_state', self.session_state)
        st_ss_patcher.start()
        self.addCleanup(st_ss_patcher.stop)

        st_qp_patcher = patch('streamlit.query_params', self.qp_dict)
        st_qp_patcher.start()
        self.addCleanup(st_qp_patcher.stop)

        # Module patches for app.py (main_app uses these)
        for name in [
            'check_pyarmor_license',
            'sync_oncall_shifts',
            'get_user_by_matricola',
        ]:
            patcher = patch(f'app.{name}')
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)

        # Module patches for login_handler.py (handle_login_and_navigation uses these)
        for name in [
            'authenticate_user',
            'verify_2fa_code',
            'generate_2fa_secret',
            'get_provisioning_uri',
            'update_user',
            'load_session',
            'save_session',
            'log_access_attempt',
            'create_user',
        ]:
            patcher = patch(f'login_handler.{name}')
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)

        # get_user_by_matricola is used in BOTH app.py and login_handler.py
        # We need to patch it in login_handler too
        patcher = patch('login_handler.get_user_by_matricola')
        self.mocks['login_get_user'] = patcher.start()
        self.addCleanup(patcher.stop)

        import app
        self.app = app

    def test_top_level_login_password_fail(self):
        self.mocks['form_submit_button'].return_value = True
        self.mocks['authenticate_user'].return_value = ("FAIL", None)
        self.mocks['text_input'].return_value = "M123" # matricola

        self.app.handle_login_and_navigation()
        self.mocks['error'].assert_called_with("Credenziali non valide.")

    def test_top_level_login_2fa_required(self):
        self.mocks['form_submit_button'].return_value = True
        self.mocks['authenticate_user'].return_value = ("2FA_REQUIRED", None)
        self.mocks['text_input'].return_value = "M123"

        self.app.handle_login_and_navigation()
        self.assertEqual(self.state_dict["login_state"], "verify_2fa")
        self.mocks['rerun'].assert_called()

    def test_session_recovery_from_query_params(self):
        self.qp_dict["session_token"] = "valid-token"
        self.state_dict["authenticated_user"] = None
        self.mocks['load_session'].return_value = True

        self.app.handle_login_and_navigation()
        self.mocks['load_session'].assert_called_with("valid-token")

    def test_verify_2fa_success(self):
        self.state_dict["login_state"] = "verify_2fa"
        self.state_dict["temp_user_for_2fa"] = "M123"
        self.mocks['login_get_user'].return_value = {"Matricola": "M123", "Nome Cognome": "Mario Rossi", "Ruolo": "admin", "2FA_Secret": "SECRET"}
        self.mocks['verify_2fa_code'].return_value = True
        self.mocks['save_session'].return_value = "new-token"
        self.mocks['form_submit_button'].return_value = True

        self.app.handle_login_and_navigation()
        self.assertEqual(self.state_dict["login_state"], "logged_in")

if __name__ == '__main__':
    unittest.main()
