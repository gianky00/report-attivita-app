"""
Modulo per la gestione dell'apprendimento e della base di conoscenza dell'IA.
Gestisce l'integrazione di nuove conoscenze e la creazione di indici vettoriali (TF-IDF).
"""

import json
import pickle
from contextlib import suppress
from pathlib import Path
from typing import Any

import nltk
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from src.core.logging import get_logger, measure_time

logger = get_logger(__name__)

UNREVIEWED_KNOWLEDGE_PATH = Path("unreviewed_knowledge.json")
KNOWLEDGE_CORE_PATH = Path("knowledge_core.json")


def load_unreviewed_knowledge() -> list[dict[str, Any]]:
    """Carica le conoscenze non revisionate dal file JSON."""
    if not UNREVIEWED_KNOWLEDGE_PATH.exists():
        return []
    with suppress(json.JSONDecodeError, FileNotFoundError):
        return json.loads(UNREVIEWED_KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return []


def save_unreviewed_knowledge(data: list[dict[str, Any]]):
    """Salva le conoscenze non revisionate nel file JSON."""
    UNREVIEWED_KNOWLEDGE_PATH.write_text(
        json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8"
    )


def integrate_knowledge(
    entry_id: str, integration_details: dict[str, Any]
) -> dict[str, Any]:
    """Integra una voce revisionata nel knowledge_core.json principale."""
    unreviewed = load_unreviewed_knowledge()
    entry_to_integrate = next(
        (entry for entry in unreviewed if entry["id"] == entry_id), None
    )

    if not entry_to_integrate:
        return {"success": False, "error": "Voce non trovata."}

    try:
        if not KNOWLEDGE_CORE_PATH.exists():
            KNOWLEDGE_CORE_PATH.write_text("{}", encoding="utf-8")

        knowledge_core = json.loads(KNOWLEDGE_CORE_PATH.read_text(encoding="utf-8"))

        equipment_key = integration_details.get("equipment_key")
        new_question = integration_details.get("new_question")

        if equipment_key and new_question:
            if equipment_key not in knowledge_core:
                knowledge_core[equipment_key] = {
                    "display_name": integration_details.get(
                        "display_name", equipment_key.capitalize()
                    ),
                    "questions": [],
                    "paths": {},
                }
            knowledge_core[equipment_key]["questions"].append(new_question)

        KNOWLEDGE_CORE_PATH.write_text(
            json.dumps(knowledge_core, indent=4, ensure_ascii=False), encoding="utf-8"
        )

        entry_to_integrate["stato"] = "integrata"
        save_unreviewed_knowledge(unreviewed)

        return {"success": True, "message": "Knowledge Core aggiornato con successo."}

    except Exception as e:
        logger.error(
            f"Errore durante l'integrazione della conoscenza: {e}", exc_info=True
        )
        return {"success": False, "error": f"{e}"}


def load_report_knowledge_base() -> str:
    """Carica la base di conoscenza leggendo i file .docx e .txt locali."""
    knowledge_base_text = []

    # Percorso 1: Documenti Storici
    local_base_path = Path("knowledge_base_docs")
    if local_base_path.is_dir():
        for filepath in local_base_path.rglob("*.docx"):
            with suppress(Exception):
                doc = Document(str(filepath))
                for para in doc.paragraphs:
                    if text := para.text.strip():
                        knowledge_base_text.append(text)
    else:
        logger.warning(f"Cartella '{local_base_path}' non trovata.")

    # Percorso 2: Relazioni Inviate
    local_path = Path("relazioni_inviate")
    if local_path.is_dir():
        for filepath in local_path.glob("*.txt"):
            with suppress(Exception):
                knowledge_base_text.append(filepath.read_text(encoding="utf-8"))

    return "\n".join(knowledge_base_text)


def get_report_knowledge_base_count() -> int:
    """Conta il numero di file nella base di conoscenza."""
    count = 0
    kb_path = Path("knowledge_base_docs")
    if kb_path.exists():
        count += sum(1 for _ in kb_path.rglob("*.docx"))
    rel_path = Path("relazioni_inviate")
    if rel_path.exists():
        count += sum(1 for _ in rel_path.glob("*.txt"))
    return count


@measure_time
def build_knowledge_base() -> dict[str, Any]:
    """Crea e salva un indice TF-IDF dalla base di conoscenza."""
    try:
        # 1. Download risorse NLTK
        for res in ["punkt", "stopwords"]:
            with suppress(LookupError):
                nltk.data.find(
                    f"tokenizers/{res}" if res == "punkt" else f"corpora/{res}"
                )
                continue
            nltk.download(res, quiet=True)

        # 2. Caricamento testo
        full_text = load_report_knowledge_base()
        if not full_text:
            return {"success": False, "message": "Nessun documento trovato."}

        # 3. Segmentazione
        sentences = nltk.sent_tokenize(full_text, language="italian")
        sentences = [s for s in sentences if len(s.split()) > 5]
        if not sentences:
            return {"success": False, "message": "Nessun contenuto valido."}

        # 4. Vettorizzazione
        stop_words = []
        try:
            stop_words = nltk.corpus.stopwords.words("italian")
        except Exception:
            logger.warning("Impossibile caricare stop words NLTK, uso lista vuota.")

        vectorizer = TfidfVectorizer(stop_words=stop_words, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(sentences)

        # 5. Salvataggio
        index_data = {
            "vectorizer": vectorizer,
            "matrix": tfidf_matrix,
            "sentences": sentences,
        }
        Path("knowledge_base_index.pkl").write_bytes(pickle.dumps(index_data))

        return {
            "success": True,
            "message": f"Indice creato con successo con {len(sentences)} voci.",
        }

    except Exception as e:
        logger.error(f"Errore creazione indice: {e}", exc_info=True)
        return {"success": False, "message": f"Errore: {e}"}


if __name__ == "__main__":
    result = build_knowledge_base()
    logger.info(f"Build Result: {result}")
