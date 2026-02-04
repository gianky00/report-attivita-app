"""
Modulo per l'interfaccia con l'Intelligenza Artificiale (Google Gemini).
Centralizza la gestione dei prompt e la logica di revisione tecnica.
"""

import google.generativeai as genai
import streamlit as st
from src.core.logging import get_logger

from modules.instrumentation_logic import (
    analyze_domain_terminology,
    find_and_analyze_tags,
)

logger = get_logger(__name__)


def generate_technical_prompt(testo_originale: str, technical_summary: str) -> str:
    """Costruisce il prompt strutturato per la revisione tecnica."""
    return f"""
    Sei un Direttore Tecnico di Manutenzione esperto in strumentazione.
    Il tuo compito è riformulare la seguente relazione tecnica,
    trasformandola in un report professionale e chiaro.
    **INFORMAZIONI TECNICHE DA USARE (Know-How):**
    ---
    {technical_summary}
    ---
    Usa queste informazioni per interpretare correttamente le sigle
    (es. CTG, FCV301) e le relazioni tra i componenti.
    Riformula il testo per riflettere questa comprensione approfondita.
    **RELAZIONE ORIGINALE DA RIFORMULARE:**
    ---
    {testo_originale}
    ---
    **RELAZIONE RIFORMULATA (restituisci solo il testo corretto):**
    """


def generate_standard_prompt(testo_originale: str) -> str:
    """Costruisce il prompt per la revisione linguistica standard."""
    return f"""
    Sei un revisore esperto di relazioni tecniche industriali.
    Il tuo compito è revisionare e migliorare il seguente testo tecnico,
    mantenendo un tono professionale, chiaro e conciso.
    Correggi eventuali errori grammaticali o di battitura.
    **RELAZIONE DA REVISIONARE:**
    ---
    {testo_originale}
    ---
    **RELAZIONE REVISIONATA (restituisci solo il testo corretto):**
    """


def revisiona_con_ia(testo: str) -> dict:
    """
    Esegue la revisione del testo tramite Gemini, applicando analisi semantica ISA.
    """
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("API Key Gemini mancante nei secrets.")
        return {"success": False, "error": "Configurazione IA incompleta."}

    if not testo.strip():
        return {"success": False, "info": "Testo vuoto."}

    try:
        # Analisi del contesto strumentale
        loops, _ = find_and_analyze_tags(testo)
        terms = analyze_domain_terminology(testo)

        technical_summary = ""
        if loops:
            technical_summary += "Analisi Strumentale:\n"
            for loop_id, components in loops.items():
                technical_summary += f"- Loop {loop_id}:\n"
                for c in components:
                    technical_summary += f"  - {c['tag']}: {c['description']}\n"

        if terms:
            technical_summary += "\nTerminologia:\n"
            for t, d in terms.items():
                technical_summary += f"- {t}: {d}\n"

        # Configurazione Modello
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-flash-latest")

        prompt = (
            generate_technical_prompt(testo, technical_summary)
            if technical_summary
            else generate_standard_prompt(testo)
        )

        response = model.generate_content(prompt)
        return {"success": True, "text": response.text}

    except Exception as e:
        logger.error(f"Errore durante la chiamata IA: {e}", exc_info=True)
        return {"success": False, "error": f"L'IA ha riscontrato un problema: {str(e)}"}
