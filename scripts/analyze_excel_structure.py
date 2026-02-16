import pandas as pd
from pathlib import Path

file_path = "Database_Report_Attivita.xlsm"

def analyze_excel(path):
    print(f"--- Analisi File: {path} ---")
    if not Path(path).exists():
        print("File non trovato.")
        return

    try:
        xl = pd.ExcelFile(path)
        print(f"Fogli trovati: {xl.sheet_names[:10]}...")
        
        # Leggiamo il primo foglio disponibile
        df = pd.read_excel(path, sheet_name=0, header=None, nrows=10)
        
        print("\nAnalisi Colonne (Base 0):")
        for i in range(min(12, len(df.columns))):
            # Proviamo a trovare la prima riga non vuota per quella colonna
            sample_val = "Vuoto"
            for r in range(len(df)):
                val = df.iloc[r, i]
                if pd.notna(val) and str(val).strip():
                    sample_val = val
                    break
            print(f"Colonna {i}: Esempio valore trovato -> {sample_val}")
            
    except Exception as e:
        print(f"Errore durante l'analisi: {e}")

if __name__ == "__main__":
    analyze_excel(file_path)
