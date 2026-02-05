"""
Test unitari per il modulo di apprendimento IA.
"""

import json

from learning_module import integrate_knowledge


def test_integrate_knowledge_not_found(mocker):
    """Verifica la gestione di una voce non trovata nelle conoscenze non revisionate."""
    mocker.patch("learning_module.load_unreviewed_knowledge", return_value=[])

    result = integrate_knowledge("999", {})
    assert result["success"] is False
    assert "non trovata" in result["error"]


def test_integrate_knowledge_success(mocker, tmp_path):
    """Verifica il flusso completo di integrazione di una nuova voce."""
    # Setup dati finti
    entry_id = "test_id"
    unreviewed = [{"id": entry_id, "stato": "in attesa"}]

    # Mock dei file
    test_core_file = tmp_path / "knowledge_core.json"
    test_core_file.write_text("{}", encoding="utf-8")

    mocker.patch(
        'learning_module.load_unreviewed_knowledge', return_value=unreviewed
    )
    mocker.patch("learning_module.save_unreviewed_knowledge")
    mocker.patch("learning_module.KNOWLEDGE_CORE_PATH", test_core_file)

    details = {
        "equipment_key": "valvola",
        "new_question": {"id": "q1", "text": "Domanda?"},
    }

    result = integrate_knowledge(entry_id, details)

    assert result["success"] is True
    # Verifica che il file core sia stato aggiornato
    core_data = json.loads(test_core_file.read_text(encoding="utf-8"))
    assert "valvola" in core_data
    assert len(core_data["valvola"]["questions"]) == 1
