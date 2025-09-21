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