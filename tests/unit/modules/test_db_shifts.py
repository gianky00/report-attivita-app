"""
Test di integrità per il database dei turni e bacheca.
"""

import sqlite3
import pytest
from src.core.database import DatabaseEngine
from src.modules.database.db_shifts import create_shift, add_booking, get_bookings_for_shift

@pytest.fixture
def setup_db_cascade(mocker, tmp_path):
    """Fixture per impostare un database con vincoli di integrità attivi."""
    db_path = tmp_path / "test_shifts.db"
    mocker.patch("src.core.database.DB_NAME", str(db_path))
    
    # Sovrascriviamo get_connection per assicurarci che ogni connessione abbia FK ON
    def get_test_conn():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
        
    mocker.patch("src.modules.database.db_shifts.get_db_connection", side_effect=get_test_conn)
    mocker.patch("src.core.database.DatabaseEngine.get_connection", side_effect=get_test_conn)
    
    conn = get_test_conn()
    conn.execute("""
        CREATE TABLE turni (
            ID_Turno TEXT PRIMARY KEY NOT NULL,
            Descrizione TEXT,
            Data TEXT,
            Tipo TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE prenotazioni (
            ID_Prenotazione TEXT PRIMARY KEY NOT NULL,
            ID_Turno TEXT NOT NULL,
            Matricola TEXT NOT NULL,
            FOREIGN KEY (ID_Turno) REFERENCES turni(ID_Turno) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()
    yield

def test_shift_deletion_cascade(setup_db_cascade):
    """Verifica che la cancellazione di un turno elimini le prenotazioni associate."""
    create_shift({"ID_Turno": "T1", "Descrizione": "Turno 1", "Data": "2025-01-01", "Tipo": "A"})
    add_booking({"ID_Prenotazione": "P1", "ID_Turno": "T1", "Matricola": "M1"})
    
    bookings = get_bookings_for_shift("T1")
    assert len(bookings) == 1
    
    # Cancellazione turno
    DatabaseEngine.execute("DELETE FROM turni WHERE ID_Turno = ?", ("T1",))
    
    # Verifica cascade
    bookings_after = get_bookings_for_shift("T1")
    assert len(bookings_after) == 0

def test_booking_integrity_missing_shift(setup_db_cascade):
    """Verifica che non sia possibile creare una prenotazione per un turno inesistente."""
    with pytest.raises(sqlite3.IntegrityError):
        conn = DatabaseEngine.get_connection()
        # Inserimento diretto per catturare l'eccezione FK
        conn.execute("INSERT INTO prenotazioni (ID_Prenotazione, ID_Turno, Matricola) VALUES (?, ?, ?)", 
                     ("P2", "NON_ESISTE", "M1"))
        conn.commit()