"""
Test per la gestione delle richieste materiali e assenze.
"""

from modules.database.db_requests import add_material_request, salva_storico_materiali

def test_add_material_request(mocker):
    """Verifica l'inserimento di una richiesta materiali."""
    mock_exec = mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    assert add_material_request({"Richiedente": "123", "Dettagli": "Test"}) is True
    assert "INSERT INTO richieste_materiali" in mock_exec.call_args[0][0]

def test_salva_storico_materiali(mocker):
    """Verifica l'archiviazione nello storico."""
    mock_exec = mocker.patch("src.core.database.DatabaseEngine.execute", return_value=True)
    assert salva_storico_materiali({"id": "1", "data": "2025"}) is True
    assert "INSERT INTO storico_richieste_materiali" in mock_exec.call_args[0][0]
