
import unittest
import sqlite3
import pandas as pd
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent.parent.parent.parent
sys.path.append(str(root_dir / "src"))

import modules.notifications as notifications

class TestNotificationsLogic(unittest.TestCase):
    
    @patch('modules.notifications.add_notification')
    def test_crea_notifica_db_error(self, mock_add):
        mock_add.return_value = False
        result = notifications.crea_notifica("M1", "Msg")
        self.assertFalse(result)

    @patch('modules.notifications.get_notifications_for_user')
    def test_leggi_notifiche_error(self, mock_get):
        mock_get.side_effect = Exception("DB error")
        result = notifications.leggi_notifiche("M1")
        self.assertTrue(result.empty)

    @patch('modules.notifications.get_db_connection')
    def test_segna_notifica_letta_error(self, mock_conn):
        mock_c = MagicMock()
        mock_conn.return_value = mock_c
        mock_c.__enter__.side_effect = sqlite3.Error("DB error")
        result = notifications.segna_notifica_letta("N1")
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
