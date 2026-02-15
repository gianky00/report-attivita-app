"""
Test unitari per la gestione delle notifiche strumentali.
Verifica src/modules/notifications.py e le integrazioni.
"""

import unittest
from unittest.mock import patch
import sqlite3
import sys
from pathlib import Path

# Aggiungi 'src' al path
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir / "src"))

from modules import notifications

class NonClosingConnection:
    def __init__(self, connection):
        self.connection = connection
    def __getattr__(self, name):
        return getattr(self.connection, name)
    def close(self):
        pass
    def execute(self, *args, **kwargs):
        return self.connection.execute(*args, **kwargs)
    def commit(self):
        return self.connection.commit()
    def cursor(self):
        return self.connection.cursor()
    def __enter__(self):
        return self.connection.__enter__()
    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.connection.__exit__(exc_type, exc_val, exc_tb)

class TestInstrumentationNotifications(unittest.TestCase):
    def setUp(self):
        # In-memory DB
        self.real_conn = sqlite3.connect(":memory:")
        self.real_conn.row_factory = sqlite3.Row
        self.cursor = self.real_conn.cursor()

        # Schema per le notifiche (coerente con src/modules/database/db_system.py e crea_database.py)
        # La colonna deve essere 'Destinatario_Matricola'
        self.cursor.execute("""
            CREATE TABLE notifiche (
                ID_Notifica TEXT PRIMARY KEY NOT NULL,
                Timestamp TEXT,
                Destinatario_Matricola TEXT NOT NULL,
                Messaggio TEXT,
                Stato TEXT,
                Link_Azione TEXT
            )
        """)
        # Tabella contatti per FK se necessario o per query di lookup
        self.cursor.execute("""
            CREATE TABLE contatti (
                Matricola TEXT PRIMARY KEY NOT NULL,
                "Nome Cognome" TEXT NOT NULL UNIQUE
            )
        """)
        self.real_conn.commit()

        # Patch DatabaseEngine.get_connection
        self.patcher = patch('core.database.DatabaseEngine.get_connection', side_effect=self._get_mock_connection)
        self.mock_get_connection = self.patcher.start()

    def _get_mock_connection(self):
        return NonClosingConnection(self.real_conn)

    def tearDown(self):
        self.patcher.stop()
        self.real_conn.close()

    def test_crea_notifica(self):
        """Test creazione notifica."""
        res = notifications.crea_notifica("USER123", "Test Message")
        self.assertTrue(res, "crea_notifica deve ritornare True")
        
        row = self.cursor.execute("SELECT * FROM notifiche WHERE Destinatario_Matricola='USER123'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["Messaggio"], "Test Message")

    def test_leggi_notifiche(self):
        """Test lettura notifiche."""
        self.cursor.execute("""
            INSERT INTO notifiche (ID_Notifica, Destinatario_Matricola, Messaggio, Stato)
            VALUES ('N1', 'USER123', 'Hello', 'non letta')
        """)
        self.real_conn.commit()

        df = notifications.leggi_notifiche("USER123")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["ID_Notifica"], "N1")

    def test_segna_notifica_letta(self):
        """Test segna notifica come letta."""
        self.cursor.execute("""
            INSERT INTO notifiche (ID_Notifica, Destinatario_Matricola, Messaggio, Stato)
            VALUES ('N1', 'USER123', 'Hello', 'non letta')
        """)
        self.real_conn.commit()

        res = notifications.segna_notifica_letta("N1")
        self.assertTrue(res)

        row = self.cursor.execute("SELECT Stato FROM notifiche WHERE ID_Notifica='N1'").fetchone()
        self.assertEqual(row["Stato"], "letta")

if __name__ == '__main__':
    unittest.main()
