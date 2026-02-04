"""
Test avanzati per la gestione atomica dei report tecnici.
"""

import sqlite3
import pytest
from pathlib import Path
from src.core.database import DatabaseEngine
import src.modules.database.db_reports as dbr

@pytest.fixture
def setup_db(mocker, tmp_path):
    """Fixture per impostare un database fisico temporaneo per i test."""
    db_path = tmp_path / "test_reports.db"
    mocker.patch("src.core.database.DB_NAME", str(db_path))
    
    def get_test_conn():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
        
    mocker.patch("src.modules.database.db_reports.get_db_connection", side_effect=get_test_conn)
    mocker.patch("src.core.database.DatabaseEngine.get_connection", side_effect=get_test_conn)
    
    conn = get_test_conn()
    conn.execute("CREATE TABLE report_da_validare (id_report TEXT PRIMARY KEY, val TEXT)")
    conn.execute("CREATE TABLE report_interventi (id_report TEXT PRIMARY KEY, val TEXT, timestamp_validazione TEXT)")
    conn.commit()
    conn.close()
    yield

def test_move_report_atomically_success(setup_db, mocker):
    """Verifica che un report venga spostato correttamente tra tabelle in una transazione."""
    DatabaseEngine.execute("INSERT INTO report_da_validare (id_report, val) VALUES (?, ?)", ("R1", "Data 1"))
    success = dbr.move_report_atomically("R1", "report_da_validare", "report_interventi")
    
    assert success is True
    dest = DatabaseEngine.fetch_one("SELECT * FROM report_interventi WHERE id_report = ?", ("R1",))
    assert dest is not None
    assert dest["val"] == "Data 1"

def test_move_report_atomically_integrity_violation(setup_db):
    """Verifica che la transazione fallisca se c'è un conflitto di chiave primaria in destinazione."""
    DatabaseEngine.execute("INSERT INTO report_da_validare (id_report, val) VALUES (?, ?)", ("R1", "New Data"))
    DatabaseEngine.execute("INSERT INTO report_interventi (id_report, val) VALUES (?, ?)", ("R1", "Old Data"))
    
    success = dbr.move_report_atomically("R1", "report_da_validare", "report_interventi")
    
    assert success is False
    src = DatabaseEngine.fetch_one("SELECT * FROM report_da_validare WHERE id_report = ?", ("R1",))
    assert src is not None
    assert src["val"] == "New Data"