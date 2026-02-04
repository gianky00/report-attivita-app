"""
Test per il modulo di apprendimento e indicizzazione IA.
"""

from src.learning_module import build_knowledge_base

def test_build_knowledge_base_no_docs(mocker):
    """Verifica il comportamento se non ci sono documenti da indicizzare."""
    mocker.patch("src.learning_module.load_report_knowledge_base", return_value="")
    result = build_knowledge_base()
    assert result["success"] is False
    assert "Nessun documento" in result["message"]

def test_build_knowledge_base_success(mocker, tmp_path, monkeypatch):
    """Verifica la creazione corretta dell'indice tramite dati reali serializzabili."""
    monkeypatch.chdir(tmp_path)
    text = "Il tecnico ha provveduto alla sostituzione della valvola di regolazione."
    mocker.patch("src.learning_module.load_report_knowledge_base", return_value=text)
    
    mocker.patch("nltk.sent_tokenize", return_value=[text])
    mocker.patch("nltk.corpus.stopwords.words", return_value=["di", "la", "il"])
    mocker.patch("nltk.data.find")
    
    # Non patchiamo TfidfVectorizer, lasciamo che sklearn lavori su un testo piccolo
    # È veloce e garantisce che il pickle funzioni su oggetti reali.
    
    result = build_knowledge_base()
    
    assert result["success"] is True
    assert (tmp_path / "knowledge_base_index.pkl").exists()