"""
Test per le funzioni di sistema e blacklist assegnamenti.
"""

from modules.database.db_system import add_assignment_exclusion, get_globally_excluded_activities

def test_add_assignment_exclusion(mocker):
    """Verifica l'inserimento di un'esclusione."""
    mock_exec = mocker.patch("core.database.DatabaseEngine.execute", return_value=True)
    assert add_assignment_exclusion("mat1", "pdl1") is True
    assert "INSERT INTO esclusioni_assegnamenti" in mock_exec.call_args[0][0]

def test_get_globally_excluded_activities(mocker):
    """Verifica il recupero della lista esclusioni."""
    mocker.patch("core.database.DatabaseEngine.fetch_all", return_value=[{"id_attivita": "id1"}, {"id_attivita": "id2"}])
    excluded = get_globally_excluded_activities()
    assert len(excluded) == 2
    assert "id1" in excluded
