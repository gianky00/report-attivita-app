import json
import os
from datetime import datetime

UNREVIEWED_KNOWLEDGE_PATH = "unreviewed_knowledge.json"
KNOWLEDGE_CORE_PATH = "knowledge_core.json"

def load_unreviewed_knowledge():
    """
    Carica le conoscenze non revisionate dal file JSON.
    Restituisce una lista di voci o una lista vuota se il file non esiste.
    """
    if not os.path.exists(UNREVIEWED_KNOWLEDGE_PATH):
        return []
    try:
        with open(UNREVIEWED_KNOWLEDGE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_unreviewed_knowledge(data):
    """
    Salva le conoscenze non revisionate nel file JSON.
    """
    with open(UNREVIEWED_KNOWLEDGE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def add_new_entry(pdl, attivita, report_lines, tecnico):
    """
    Aggiunge una nuova voce di conoscenza da revisionare.
    """
    unreviewed = load_unreviewed_knowledge()
    
    new_entry = {
        "id": f"entry_{int(datetime.now().timestamp())}",
        "pdl": pdl,
        "attivita_collegata": attivita,
        "dettagli_report": report_lines,
        "suggerito_da": tecnico,
        "data_suggerimento": datetime.now().isoformat(),
        "stato": "in attesa di revisione"
    }
    
    unreviewed.append(new_entry)
    save_unreviewed_knowledge(unreviewed)
    return new_entry

def integrate_knowledge(entry_id, integration_details):
    """
    Integra una voce revisionata nel knowledge_core.json principale.
    """
    unreviewed = load_unreviewed_knowledge()
    entry_to_integrate = next((entry for entry in unreviewed if entry['id'] == entry_id), None)

    if not entry_to_integrate:
        return {"success": False, "error": "Voce non trovata."}

    try:
        with open(KNOWLEDGE_CORE_PATH, 'r+', encoding='utf-8') as f:
            knowledge_core = json.load(f)

            equipment_key = integration_details.get("equipment_key")
            new_question = integration_details.get("new_question")

            if equipment_key and new_question:
                if equipment_key not in knowledge_core:
                    knowledge_core[equipment_key] = {
                        "display_name": integration_details.get("display_name", equipment_key.capitalize()),
                        "questions": [],
                        "paths": {}
                    }
                
                knowledge_core[equipment_key]['questions'].append(new_question)

            f.seek(0)
            json.dump(knowledge_core, f, indent=4, ensure_ascii=False)
            f.truncate()

        entry_to_integrate['stato'] = 'integrata'
        save_unreviewed_knowledge(unreviewed)
        
        return {"success": True, "message": "Knowledge Core aggiornato con successo."}

    except Exception as e:
        return {"success": False, "error": str(e)}

def load_report_knowledge_base():
    """
    Carica la base di conoscenza leggendo i file .docx e .txt da tutte le sottocartelle
    in 'relazioni_word' e 'relazioni_inviate'.
    """
    import docx

    knowledge_base_text = ""
    base_paths = ["relazioni_word", "relazioni_inviate"]

    for base_path in base_paths:
        if not os.path.exists(base_path) or not os.path.isdir(base_path):
            continue

        for dirpath, _, filenames in os.walk(base_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    if filename.endswith(".docx"):
                        doc = docx.Document(filepath)
                        for para in doc.paragraphs:
                            knowledge_base_text += para.text + "\n"
                    elif filename.endswith(".txt"):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            knowledge_base_text += f.read() + "\n"
                except Exception:
                    # Ignora file corrotti o illeggibili
                    continue

    return knowledge_base_text

def get_report_knowledge_base_count():
    """
    Conta in modo efficiente il numero di file .docx e .txt nella base di conoscenza
    senza caricarli.
    """
    file_count = 0
    base_paths = ["relazioni_word", "relazioni_inviate"]

    for base_path in base_paths:
        if not os.path.exists(base_path) or not os.path.isdir(base_path):
            continue

        for dirpath, _, filenames in os.walk(base_path):
            for filename in filenames:
                if filename.endswith(".docx") or filename.endswith(".txt"):
                    file_count += 1

    return file_count

def build_knowledge_base():
    """
    Crea e salva un indice vettoriale dalla base di conoscenza dei report.
    Questa funzione è pensata per essere eseguita dall'app.
    Restituisce un dizionario con lo stato dell'operazione.
    """
    import pickle
    import nltk
    from sklearn.feature_extraction.text import TfidfVectorizer

    try:
        # 1. Scarica le risorse NLTK necessarie in modo silenzioso
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True)

        # 2. Carica e processa il testo
        full_text = load_report_knowledge_base()
        if not full_text:
            return {"success": False, "message": "Nessun documento trovato. L'indice non è stato creato."}

        # 3. Segmentazione
        sentences = nltk.sent_tokenize(full_text, language='italian')
        sentences = [s for s in sentences if len(s.split()) > 5]
        if not sentences:
            return {"success": False, "message": "Nessun contenuto testuale valido trovato dopo la segmentazione."}

        # 4. Vettorizzazione
        stopwords_italiano = nltk.corpus.stopwords.words('italian')
        vectorizer = TfidfVectorizer(stop_words=stopwords_italiano, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(sentences)

        # 5. Salvataggio dell'indice
        index_data = {
            'vectorizer': vectorizer,
            'matrix': tfidf_matrix,
            'sentences': sentences
        }

        index_filename = "knowledge_base_index.pkl"
        with open(index_filename, 'wb') as f:
            pickle.dump(index_data, f)

        return {"success": True, "message": f"Indice creato con successo con {len(sentences)} voci."}

    except Exception as e:
        return {"success": False, "message": f"Errore durante la creazione dell'indice: {str(e)}"}

if __name__ == '__main__':
    # Questo blocco consente di eseguire lo script dalla riga di comando
    # per generare l'indice.
    result = build_knowledge_base()
    print(result)