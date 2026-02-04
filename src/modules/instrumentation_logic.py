"""
Logica di analisi semantica per la strumentazione industriale (ISA S5.1).
Fornisce strumenti per il parsing dei TAG e suggerimenti tecnici basati sul contesto.
"""

import re
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)

# ISA S5.1 Knowledge Base (semplificata e adattata)
ISA_KB = {
    "C": {"name": "Regolatore", "type": "[CONTROLLORE]"},
    "V": {"name": "Valvola", "type": "[ATUTTATORE]"},
    "T": {"name": "Trasmettitore", "type": "[TRASMETTITORE]"},
    "E": {"name": "Elemento primario", "type": "[SENSORE]"},
    "I": {"name": "Indicatore", "type": "[INDICATORE]"},
    "R": {"name": "Registratore", "type": "[REGISTRATORE]"},
    "S": {"name": "Interruttore", "type": "[SWITCH]"},
    "Y": {"name": "Relè/Convertitore", "type": "[LOGICA_AUSILIARIA]"},
    "CV": {"name": "Valvola di Controllo", "type": "[ATUTTATORE]"},
    "RC": {"name": "Controllore e Registratore", "type": "[CONTROLLORE]"},
    "PSV": {"name": "Valvola di Sicurezza Pressione", "type": "[VALVOLA_SICUREZZA]"},
    "TT": {"name": "Trasmettitore di Temperatura", "type": "[TRASMETTITORE]"},
    "PT": {"name": "Trasmettitore di Pressione", "type": "[TRASMETTITORE]"},
    "LT": {"name": "Trasmettitore di Livello", "type": "[TRASMETTITORE]"},
    "FT": {"name": "Trasmettitore di Portata", "type": "[TRASMETTITORE]"},
}

MEASURED_VARIABLE_KB = {
    "F": "Portata",
    "P": "Pressione",
    "T": "Temperatura",
    "L": "Livello",
    "A": "Analisi",
    "S": "Velocità",
    "V": "Vibrazione",
    "W": "Peso",
    "Q": "Quantità",
}


def parse_instrument_tag(tag: str) -> dict[str, Any] | None:
    """
    Analizza un tag di strumentazione per estrarre le sue parti (es. FCV301).
    Ritorna informazioni strutturate o None se non valido.
    """
    tag = tag.strip().upper()

    # Pattern 1: FCV301, TT301, PSV100A
    match1 = re.fullmatch(r"([A-Z]+)(\d+)([A-Z]*)", tag)
    # Pattern 2: F301RC, T301C
    match2 = re.fullmatch(r"([A-Z])(\d+)([A-Z]+)", tag)

    if match2:
        prefix, loop_num, suffix = match2.groups()
        key_letters = suffix
    elif match1:
        prefix, loop_num, suffix = match1.groups()
        key_letters = prefix
    else:
        return None

    instrument_type = "Sconosciuto"
    base_name = "Dispositivo generico"

    # 1. Priorità alle combinazioni speciali
    if key_letters in ISA_KB:
        instrument_type = ISA_KB[key_letters]["type"]
        base_name = ISA_KB[key_letters]["name"]
    # 2. Analisi dell'ultima lettera per la funzione principale
    elif key_letters and key_letters[-1] in ISA_KB:
        last_char = key_letters[-1]
        # Caso speciale Temperatura/Trasmettitore
        if last_char == "T" and len(key_letters) > 1:
            instrument_type = ISA_KB["T"]["type"]
            base_name = ISA_KB["T"]["name"]
        else:
            instrument_type = ISA_KB[last_char]["type"]
            base_name = ISA_KB[last_char]["name"]

    # Composizione descrizione finale
    measured_var = MEASURED_VARIABLE_KB.get(prefix[0], "Sconosciuta")
    description = (
        f"{base_name} di {measured_var.lower()}"
        if prefix[0] in MEASURED_VARIABLE_KB
        else base_name
    )

    return {
        "tag": tag,
        "loop": loop_num,
        "type": instrument_type,
        "description": description,
        "variable": measured_var,
    }


def find_and_analyze_tags(text: str) -> tuple[dict[str, list[dict]], list[dict]]:
    """
    Trova e analizza tutti i TAG ISA nel testo fornito.
    """
    potential_tags = re.findall(r"\b[A-Z]{1,4}\d{2,4}[A-Z]{0,2}\b", text.upper())
    loops: dict[str, list[dict]] = {}
    analyzed_tags: list[dict] = []

    for tag in potential_tags:
        parsed = parse_instrument_tag(tag)
        if parsed and parsed["type"] != "Sconosciuto":
            loop_id = parsed["loop"]
            loops.setdefault(loop_id, []).append(parsed)
            analyzed_tags.append(parsed)
            logger.debug(f"TAG Riconosciuto: {tag} ({parsed['description']})")

    return loops, analyzed_tags


# --- Troubleshooting Knowledge Base ---
TROUBLESHOOTING_KB = {
    "keywords": {
        "termoresistenza": [
            "Suggerimento RTD: Se il segnale è a fondo scala, verificare la "
            "continuità del sensore. Valore infinito indica sensore bruciato.",
            "Suggerimento RTD: Segnale instabile può dipendere da vibrazioni "
            "meccaniche o cattive connessioni nella testa di giunzione.",
        ],
        "termocoppia": [
            "Suggerimento TC: Segnale a fondo scala indica spesso "
            "una TC 'bruciata' o un circuito aperto.",
            "Suggerimento TC: Se il segnale è rumoroso, "
            "controllare la messa a terra della calza.",
        ],
        "pressione differenziale": [
            "Suggerimento DP: Verificare che le prese d'impulso non siano ostruite.",
        ],
    },
    "types": {
        "[ATUTTATORE]": [
            "Suggerimento Attuatore: Verificare la pressione di alimentazione "
            "dell'aria al posizionatore.",
        ],
        "[CONTROLLORE]": [
            "Suggerimento Controllore: Verificare la modalità MAN/AUTO del loop.",
        ],
    },
}


def get_technical_suggestions(text: str) -> list[str]:
    """Restituisce suggerimenti tecnici basati sulle parole chiave e i TAG rilevati."""
    if not text:
        return []

    suggestions = set()
    lower_text = text.lower()

    # 1. Ricerca per parole chiave
    for kw, hints in TROUBLESHOOTING_KB["keywords"].items():
        if kw in lower_text:
            suggestions.update(hints)

    # 2. Ricerca per tipo di strumento (dai TAG)
    _, tags = find_and_analyze_tags(text)
    for tag in tags:
        type_hints = TROUBLESHOOTING_KB["types"].get(tag["type"], [])
        suggestions.update(type_hints)

    return list(suggestions)


DOMAIN_TERMINOLOGY_KB = {
    "CTG": "Capo Turno Generale",
    "CT": "Capo Turno",
    "CR": "Capo Reparto",
    "chiamata": "chiamata di reperibilità",
}


def analyze_domain_terminology(text: str) -> dict[str, str]:
    """Analizza acronimi e terminologia specifica di impianto."""
    found = {}
    for term, definition in DOMAIN_TERMINOLOGY_KB.items():
        # Case-sensitive per acronimi maiuscoli, case-insensitive per il resto
        flags = 0 if term.isupper() else re.IGNORECASE
        if re.search(r"\b" + re.escape(term) + r"\b", text, flags):
            found[term] = definition
    return found
