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
    Carica la base di conoscenza leggendo i file .docx da tutte le sottocartelle
    annuali presenti in 'relazioni_word'.
    """
    import docx

    base_path = "relazioni_word"
    knowledge_base_text = ""

    if not os.path.exists(base_path) or not os.path.isdir(base_path):
        return ""

    # Scansiona tutte le sottocartelle nella cartella di base
    for year_folder in os.listdir(base_path):
        reports_path = os.path.join(base_path, year_folder)
        if os.path.isdir(reports_path):
            for filename in os.listdir(reports_path):
                if filename.endswith(".docx"):
                    try:
                        filepath = os.path.join(reports_path, filename)
                        doc = docx.Document(filepath)
                        for para in doc.paragraphs:
                            knowledge_base_text += para.text + "\n"
                    except Exception:
                        # Ignora file corrotti o illeggibili
                        continue

    return knowledge_base_text

def get_report_knowledge_base_count():
    """
    Conta in modo efficiente il numero di file .docx nella base di conoscenza
    senza caricarli.
    """
    base_path = "relazioni_word"
    file_count = 0

    if not os.path.exists(base_path) or not os.path.isdir(base_path):
        return 0

    for year_folder in os.listdir(base_path):
        reports_path = os.path.join(base_path, year_folder)
        if os.path.isdir(reports_path):
            for filename in os.listdir(reports_path):
                if filename.endswith(".docx"):
                    file_count += 1

    return file_count

def create_knowledge_base_index():
    """
    Crea e salva un indice vettoriale dalla base di conoscenza dei report.
    Questa funzione è pensata per essere eseguita una tantum o periodicamente.
    """
    import pickle
    import nltk
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    print("Avvio della creazione dell'indice della base di conoscenza...")

    # 1. Scarica le risorse NLTK necessarie
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("Download del tokenizer 'punkt' di NLTK...")
        nltk.download('punkt', quiet=True)
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        print("Download delle 'stopwords' di NLTK...")
        nltk.download('stopwords', quiet=True)

    # 2. Carica e processa il testo
    print("Caricamento dei documenti...")
    full_text = load_report_knowledge_base()
    if not full_text:
        print("Nessun documento trovato. Indice non creato.")
        return

    print("Segmentazione del testo...")
    # Suddivide il testo in frasi (o piccoli paragrafi)
    sentences = nltk.sent_tokenize(full_text, language='italian')

    # Rimuovi frasi troppo corte
    sentences = [s for s in sentences if len(s.split()) > 5]

    if not sentences:
        print("Nessun contenuto testuale valido trovato dopo la segmentazione. Indice non creato.")
        return

    # 3. Vettorizzazione
    print("Vettorizzazione del testo con TF-IDF...")
    # Usa le stopwords italiane
    stopwords_italiano = nltk.corpus.stopwords.words('italian')
    vectorizer = TfidfVectorizer(stop_words=stopwords_italiano, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(sentences)

    # 4. Salvataggio dell'indice
    index_data = {
        'vectorizer': vectorizer,
        'matrix': tfidf_matrix,
        'sentences': sentences
    }

    index_filename = "knowledge_base_index.pkl"
    print(f"Salvataggio dell'indice in '{index_filename}'...")
    with open(index_filename, 'wb') as f:
        pickle.dump(index_data, f)

    print("Creazione dell'indice completata con successo!")

if __name__ == '__main__':
    # Questo blocco consente di eseguire lo script dalla riga di comando
    # per generare l'indice.
    create_knowledge_base_index()