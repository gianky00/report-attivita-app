from fpdf import FPDF
import pandas as pd
from datetime import datetime
import os
import calendar

class PDF(FPDF):
    # Rimuoviamo l'header per eliminare il titolo "Report Reperibilità Mensile"
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Pagina 1 di 1', 0, 0, 'R')

def generate_on_call_pdf(data, month_name, year):
    # Mappa i mesi dall'italiano all'inglese per la compatibilità con il modulo calendar
    italian_to_english_month = {
        "gennaio": "January", "febbraio": "February", "marzo": "March",
        "aprile": "April", "maggio": "May", "giugno": "June",
        "luglio": "July", "agosto": "August", "settembre": "September",
        "ottobre": "October", "novembre": "November", "dicembre": "December"
    }

    english_month_name = italian_to_english_month.get(month_name.lower())
    if not english_month_name:
        # Fallback nel caso in cui il nome del mese non sia valido
        return None

    # Ottieni il numero del mese dal nome
    month_number = list(calendar.month_name).index(english_month_name)

    # Crea un range di date per l'intero mese
    num_days = calendar.monthrange(year, month_number)[1]
    full_month_dates = pd.date_range(start=f"{year}-{month_number}-01", periods=num_days)

    # Crea un DataFrame completo per il mese
    df_month = pd.DataFrame(full_month_dates, columns=['Data'])

    # Prepara il DataFrame con i dati di reperibilità
    if data:
        df_data = pd.DataFrame(data)
        df_data['Data'] = pd.to_datetime(df_data['Data'])

        # Pivot dei dati per avere Persona 1 (Tecnico) e Persona 2 (Aiutante) sulla stessa riga
        df_pivot = df_data.pivot_table(index='Data', columns='RuoloOccupato', values='Nome Cognome', aggfunc='first').reset_index()

        # Rinomina le colonne se esistono, altrimenti creale vuote
        df_pivot = df_pivot.rename(columns={'Tecnico': 'Persona 1', 'Aiutante': 'Persona 2'})
        if 'Persona 1' not in df_pivot:
            df_pivot['Persona 1'] = ''
        if 'Persona 2' not in df_pivot:
            df_pivot['Persona 2'] = ''

        # Unisci i dati di reperibilità con il calendario completo del mese
        df_final = pd.merge(df_month, df_pivot, on='Data', how='left').fillna('')
    else:
        # Se non ci sono dati, crea comunque il calendario vuoto
        df_final = df_month
        df_final['Persona 1'] = ''
        df_final['Persona 2'] = ''

    # Inizia la creazione del PDF
    pdf = PDF()
    pdf.add_page()

    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f'REP.STRUM. ISAB SUD {month_name.upper()} {year}', 0, 1, 'C')

    # Definisci l'altezza della cella più piccola per compattare la tabella
    cell_height = 7

    pdf.set_font('Arial', 'B', 10)
    pdf.cell(30, cell_height, 'Data', 1, 0, 'C')
    pdf.cell(80, cell_height, 'Persona 1', 1, 0, 'C')
    pdf.cell(80, cell_height, 'Persona 2', 1, 1, 'C')

    pdf.set_font('Arial', '', 9)

    for _, row in df_final.iterrows():
        pdf.cell(30, cell_height, row['Data'].strftime('%d/%m/%Y'), 1, 0, 'C')
        pdf.cell(80, cell_height, str(row['Persona 1']), 1, 0, 'L')
        pdf.cell(80, cell_height, str(row['Persona 2']), 1, 1, 'L')

    # Assicura che la directory 'reports' esista
    if not os.path.exists('reports'):
        os.makedirs('reports')

    # Aggiorna il formato del nome del file
    file_path = f"reports/reperibilita_strumentale_{month_name.lower()}_{year}_ISAB_SUD.pdf"
    pdf.output(file_path)
    return file_path
