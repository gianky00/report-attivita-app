"""
Test unitari per la logica di analisi strumentazione ISA S5.1.
"""

from modules.instrumentation_logic import (
    find_and_analyze_tags,
    parse_instrument_tag,
)


def test_parse_instrument_tag_standard():
    """Verifica il parsing di un tag standard (Prefisso + Loop)."""
    result = parse_instrument_tag("FCV301")
    assert result["tag"] == "FCV301"
    assert result["type"] == "[ATUTTATORE]"
    assert result["variable"] == "Portata"
    assert result["loop"] == "301"


def test_parse_instrument_tag_suffix_style():
    """Verifica il parsing di un tag con suffisso funzionale (Variabile + Loop + Funzione)."""
    result = parse_instrument_tag("F301RC")
    assert result["tag"] == "F301RC"
    assert result["type"] == "[CONTROLLORE]"
    assert result["variable"] == "Portata"


def test_parse_instrument_tag_special_combination():
    """Verifica il riconoscimento di combinazioni ISA speciali (es. PSV)."""
    result = parse_instrument_tag("PSV100A")
    assert result["type"] == "[VALVOLA_SICUREZZA]"
    assert result["variable"] == "Pressione"


def test_find_and_analyze_tags():
    """Verifica l'estrazione di più tag da un testo tecnico."""
    text = "Abbiamo controllato la valvola FCV301 e il trasmettitore PT102."
    loops, analyzed = find_and_analyze_tags(text)

    assert "301" in loops
    assert "102" in loops
    assert len(analyzed) == 2
    assert any(t["tag"] == "FCV301" for t in analyzed)
    assert any(t["tag"] == "PT102" for t in analyzed)


def test_parse_invalid_tag():
    """Verifica che tag non validi restituiscano None."""
    assert parse_instrument_tag("INVALID_TAG") is None
    assert parse_instrument_tag("12345") is None
