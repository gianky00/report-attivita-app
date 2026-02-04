"""
Test per il motore IA e la generazione dei prompt.
"""

from src.modules.ai_engine import generate_technical_prompt, generate_standard_prompt

def test_generate_technical_prompt_injection():
    """Verifica che le informazioni tecniche siano iniettate nel prompt."""
    summary = "TAG: FCV301 | Tipo: Valvola"
    text = "La valvola non apre."
    prompt = generate_technical_prompt(text, summary)
    
    assert "FCV301" in prompt
    assert "Valvola" in prompt
    assert text in prompt
    assert "Direttore Tecnico" in prompt

def test_generate_standard_prompt():
    """Verifica la struttura del prompt standard."""
    text = "Testo base."
    prompt = generate_standard_prompt(text)
    assert text in prompt
    assert "revisore esperto" in prompt
