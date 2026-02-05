"""
Test per la resilienza IO e integrità dei log.
"""

import datetime
import logging
from core.logging import JsonFormatter
from learning_module import load_report_knowledge_base

def test_json_formatter_serialization():
    """Verifica che il formatter generi un JSON valido per i campi standard."""
    formatter = JsonFormatter()
    
    log_record = logging.makeLogRecord({
        'msg': 'Test Message', 'levelname': 'INFO', 'name': 'test_logger',
        'created': 1738700000, # Timestamp fisso
        'module': 'test_mod', 'funcName': 'test_func', 'lineno': 10
    })
    
    output = formatter.format(log_record)
    assert '"message": "Test Message"' in output
    assert '"level": "INFO"' in output
    assert '"logger": "test_logger"' in output

def test_load_kb_resilience(mocker, tmp_path, monkeypatch):
    """Verifica che il caricamento KB ignori i file illeggibili."""
    monkeypatch.chdir(tmp_path)
    
    # Crea cartella e file finto
    kb_dir = tmp_path / "knowledge_base_docs"
    kb_dir.mkdir()
    (kb_dir / "good.docx").write_text("Data")
    
    def mock_doc(path):
        if "good" in str(path):
            mock_obj = mocker.MagicMock()
            mock_obj.paragraphs = [mocker.MagicMock(text="Testo valido")]
            return mock_obj
        raise Exception("Corrupt")
        
    mocker.patch("src.learning_module.Document", side_effect=mock_doc)
    
    text = load_report_knowledge_base()
    assert "Testo valido" in text
