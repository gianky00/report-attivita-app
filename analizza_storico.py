import pandas as pd
import json
import os

# --- CONFIGURAZIONE ---
# Assicurati che questi percorsi siano corretti
PATH_DATABASE_INPUT = r'\\192.168.11.251\Database_Tecnico_SMI\cartella strumentale condivisa\ALLEGRETTI\Database_Report_Attivita.xlsm'
PATH_JSON_OUTPUT = 'analisi_storico.json' # Verrà creato nella stessa cartella dello script

# --- INIZIO SCRIPT DI ANALISI ---
def analizza_database():
    print("Avvio analisi dello storico...")
    try:
        df = pd.read_excel(PATH_DATABASE_INPUT)
        if df.empty:
            print("🟡 Il database è vuoto. Nessuna analisi da eseguire.")
            return
    except FileNotFoundError:
        print(f"❌ File database non trovato: {PATH_DATABASE_INPUT}")
        return
    except Exception as e:
        print(f"❌ Errore durante la lettura del database: {e}")
        return

    # Dizionario che conterrà tutti i risultati della nostra analisi
    risultati_analisi = {}

    # --- 1. Analisi per "Assistente Intelligente" ---
    # Per ogni tipo di attività, trova le 3 soluzioni (report) più comuni
    print("Elaboro suggerimenti per l'Assistente Intelligente...")
    suggerimenti = {}
    # Raggruppa per descrizione attività e calcola i report più frequenti
    descrizioni_gruppi = df.groupby('Descrizione')
    for nome_descrizione, gruppo in descrizioni_gruppi:
        # Pulisci i report vuoti o inutili prima di contare
        report_validi = gruppo['Report'].dropna().str.strip()
        report_validi = report_validi[report_validi != '']
        if not report_validi.empty:
            soluzioni_comuni = report_validi.value_counts().nlargest(3).index.tolist()
            suggerimenti[nome_descrizione] = {'soluzioni_comuni': soluzioni_comuni}
    
    risultati_analisi['assistente_intelligente'] = suggerimenti
    print(f"✅ Trovati suggerimenti per {len(suggerimenti)} tipi di attività.")

    # --- 2. Analisi per "Modulo Predittivo" ---
    # Trova i 5 PdL che finiscono più spesso in stato "Sospesa"
    print("\nElaboro analisi per il modulo predittivo...")
    df_sospesi = df[df['Stato'].str.upper() == 'SOSPESA']
    if not df_sospesi.empty:
        pdl_problematici = df_sospesi['PdL'].value_counts().nlargest(5).reset_index()
        pdl_problematici.columns = ['pdl', 'conteggio_sospesi']
        risultati_analisi['pdl_problematici'] = pdl_problematici.to_dict('records')
        print(f"✅ Identificati {len(pdl_problematici)} PdL con sospensioni frequenti.")
    else:
        print("🟡 Nessuna attività in stato 'Sospesa' trovata.")
        risultati_analisi['pdl_problematici'] = []


    # --- SALVATAGGIO DEI RISULTATI ---
    try:
        with open(PATH_JSON_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(risultati_analisi, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Analisi completata. Risultati salvati in '{PATH_JSON_OUTPUT}'.")
    except Exception as e:
        print(f"❌ Errore durante il salvataggio del file JSON: {e}")

if __name__ == "__main__":
    analizza_database()