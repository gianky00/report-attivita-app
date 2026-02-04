"""
Test avanzati per il motore di intelligenza artificiale.
Verifica la generazione dei prompt e l'integrazione con la logica strumentale.
"""

import pytest
import src.modules.ai_engine as ai

def test_prompt_selection_logic(mocker):
    """Verifica che venga scelto il prompt tecnico se vengono rilevati tag ISA."""
    mocker.patch("streamlit.secrets", {"GEMINI_API_KEY": "fake_key"})
    mock_genai = mocker.patch("google.generativeai.GenerativeModel")
    mock_model = mock_genai.return_value
    mock_model.generate_content.return_value = mocker.MagicMock(text="Revised Text")
    
    mocker.patch("src.modules.ai_engine.find_and_analyze_tags", return_value=({"101": [{"tag": "FCV101", "description": "Valve"}]}, []))
    mocker.patch("src.modules.ai_engine.analyze_domain_terminology", return_value={})
    
    spy_tech = mocker.spy(ai, "generate_technical_prompt")
    spy_std = mocker.spy(ai, "generate_standard_prompt")
    
    ai.revisiona_con_ia("Il tag FCV101 è rotto")
    
    assert spy_tech.called
    assert not spy_std.called

def test_standard_prompt_fallback(mocker):
    """Verifica che venga usato il prompt standard se non ci sono tag tecnici."""
    mocker.patch("streamlit.secrets", {"GEMINI_API_KEY": "fake_key"})
    mock_genai = mocker.patch("google.generativeai.GenerativeModel")
    mock_model = mock_genai.return_value
    mock_model.generate_content.return_value = mocker.MagicMock(text="Revised Text")
    
    mocker.patch("src.modules.ai_engine.find_and_analyze_tags", return_value=({}, []))
    mocker.patch("src.modules.ai_engine.analyze_domain_terminology", return_value={})
    
    spy_tech = mocker.spy(ai, "generate_technical_prompt")
    spy_std = mocker.spy(ai, "generate_standard_prompt")
    
    ai.revisiona_con_ia("Oggi è una bella giornata")
    
    assert not spy_tech.called
    assert spy_std.called

def test_ai_revision_empty_text(mocker):
    """Verifica la gestione di testo vuoto."""
    mocker.patch("streamlit.secrets", {"GEMINI_API_KEY": "fake_key"})
    res = ai.revisiona_con_ia("   ")
    assert res["success"] is False
    assert "vuoto" in res["info"]
