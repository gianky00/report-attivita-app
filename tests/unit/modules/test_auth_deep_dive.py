import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import modules.auth as auth


class TestAuthDeepDive(unittest.TestCase):
    @patch("modules.auth.get_db_connection")
    def test_get_user_by_matricola_error(self, mock_conn):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.cursor.side_effect = sqlite3.Error("Mock error")
        result = auth.get_user_by_matricola("M123")
        self.assertIsNone(result)

    def test_create_user_empty_data(self):
        result = auth.create_user({"InvalidKey": "Value"})
        self.assertFalse(result)

    @patch("modules.auth.get_db_connection")
    def test_create_user_integrity_error(self, mock_conn):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.__enter__.side_effect = sqlite3.IntegrityError("Duplicate")
        result = auth.create_user({"Matricola": "M123", "Nome Cognome": "Test"})
        self.assertFalse(result)

    @patch("modules.auth.get_db_connection")
    def test_update_user_error(self, mock_conn):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.__enter__.side_effect = sqlite3.Error("DB error")
        result = auth.update_user("M123", {"Ruolo": "Admin"})
        self.assertFalse(result)

    def test_update_user_no_valid_fields(self):
        result = auth.update_user("M123", {"Invalid": "X"})
        self.assertFalse(result)

    @patch("modules.auth.get_db_connection")
    def test_delete_user_error(self, mock_conn):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.__enter__.side_effect = sqlite3.Error("DB error")
        result = auth.delete_user("M123")
        self.assertFalse(result)

    @patch("modules.auth.update_user")
    def test_resets(self, mock_update):
        auth.reset_user_2fa("M123")
        mock_update.assert_called_with("M123", {"2FA_Secret": None})
        auth.reset_user_password("M123")
        mock_update.assert_called_with("M123", {"PasswordHash": None})

    def test_generate_2fa_secret(self):
        secret = auth.generate_2fa_secret()
        self.assertTrue(len(secret) > 0)

    def test_get_provisioning_uri_safe(self):
        uri = auth.get_provisioning_uri("user.name!@#", "JBSWY3DPEHPK3PXP")
        self.assertIn("username", uri)
        self.assertNotIn(".", uri)

    def test_verify_2fa_code_edge(self):
        self.assertFalse(auth.verify_2fa_code("", "123456"))
        self.assertFalse(auth.verify_2fa_code("SECRET", ""))
        with patch("pyotp.totp.TOTP.verify", side_effect=Exception()):
            self.assertFalse(auth.verify_2fa_code("SECRET", "123456"))

    def test_authenticate_user_empty(self):
        status, _data = auth.authenticate_user("", "pass")
        self.assertEqual(status, "FAILED")

    @patch("modules.auth.get_db_connection")
    def test_authenticate_user_first_login_no_users(self, mock_conn):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.cursor.return_value.fetchone.return_value = (0,)
        status, _data = auth.authenticate_user("M123", "pass")
        self.assertEqual(status, "FIRST_LOGIN_SETUP")

    @patch("modules.auth.get_user_by_matricola")
    @patch("modules.auth.get_db_connection")
    def test_authenticate_user_first_login_no_hash(self, mock_conn, mock_get):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.cursor.return_value.fetchone.return_value = (10,)
        mock_get.return_value = {"Nome Cognome": "Mario", "PasswordHash": "  "}
        status, _data = auth.authenticate_user("M123", "pass")
        self.assertEqual(status, "FIRST_LOGIN_SETUP")

    @patch("modules.auth.get_user_by_matricola")
    @patch("modules.auth.get_db_connection")
    def test_authenticate_user_2fa_flags(self, mock_conn, mock_get):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.cursor.return_value.fetchone.return_value = (10,)

        # Scenario: Password match, no 2FA secret
        import bcrypt

        hashed = bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode("utf-8")
        mock_get.return_value = {
            "Nome Cognome": "Mario",
            "PasswordHash": hashed,
            "2FA_Secret": None,
        }
        status, _data = auth.authenticate_user("M123", "pass")
        self.assertEqual(status, "2FA_SETUP_REQUIRED")

        # Scenario: Password match, has 2FA secret
        mock_get.return_value = {
            "Nome Cognome": "Mario",
            "PasswordHash": hashed,
            "2FA_Secret": "SECRET",
        }
        status, _data = auth.authenticate_user("M123", "pass")
        self.assertEqual(status, "2FA_REQUIRED")

    @patch("modules.auth.get_db_connection")
    def test_log_access_attempt_error(self, mock_conn):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.__enter__.side_effect = sqlite3.Error("DB error")
        result = auth.log_access_attempt("admin", "LOGIN")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
