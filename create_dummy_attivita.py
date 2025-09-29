import pandas as pd
import os
import datetime

# --- CONFIGURAZIONE ---
FILE_NAME = "attivita_programmate.xlsm"
SHEETS_TO_CREATE = ['A1', 'A2', 'A3', 'CTE', 'BLENDING']

def create_dummy_attivita_file():
    """
    Crea un file attivita_programmate.xlsm fittizio con la struttura
    e le colonne attese, includendo dati con timestamp per il test.
    """
    if os.path.exists(FILE_NAME):
        print(f"Il file '{FILE_NAME}' esiste già. Nessuna azione eseguita.")
        return

    print(f"Creazione del file fittizio '{FILE_NAME}'...")

    try:
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
            header = [
                "PdL", "IMP.", "DESCRIZIONE\nATTIVITA'", "STATO\nPdL",
                "LUN", "MAR", "MER", "GIO", "VEN", "STATO\nATTIVITA'", "PERSONALE\nIMPIEGATO", "DATA\nCONTROLLO"
            ]

            sample_data = {
                "PdL": ["123456/C"],
                "IMP.": ["Impianto Prova"],
                "DESCRIZIONE\nATTIVITA'": ["Attività di test con data"],
                "STATO\nPdL": ["CHIUSO"],
                "LUN": ["X"],
                "MAR": [""],
                "MER": [""],
                "GIO": [""],
                "VEN": ["X"],
                "STATO\nATTIVITA'": ["Report di test completato."],
                "PERSONALE\nIMPIEGATO": ["ROSSI"],
                # Aggiungiamo una data per popolare lo storico
                "DATA\nCONTROLLO": [datetime.datetime.now()]
            }
            sample_df = pd.DataFrame(sample_data)

            for sheet_name in SHEETS_TO_CREATE:
                empty_header_df = pd.DataFrame([[] for _ in range(2)])
                empty_header_df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

                if sheet_name == 'A1':
                    sample_df.to_excel(writer, sheet_name=sheet_name, startrow=2, index=False)
                else:
                    pd.DataFrame(columns=header).to_excel(writer, sheet_name=sheet_name, startrow=2, index=False)

        print(f"File fittizio '{FILE_NAME}' creato con successo.")

    except Exception as e:
        print(f"Errore durante la creazione del file fittizio: {e}")

if __name__ == "__main__":
    create_dummy_attivita_file()