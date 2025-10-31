from fpdf import FPDF
import pandas as pd
from datetime import datetime
import os

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Report Reperibilità Mensile', 0, 1, 'C')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def generate_on_call_pdf(data, month, year):
    if not data:
        return None

    pdf = PDF()
    pdf.add_page()

    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, f'REP.STRUM. ISAB SUD {month.upper()} {year}', 0, 1, 'C')
    pdf.ln(10)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 10, 'Data', 1)
    pdf.cell(80, 10, 'Tecnico', 1)
    pdf.cell(70, 10, 'Ruolo', 1)
    pdf.ln()

    pdf.set_font('Arial', '', 12)

    # Create a DataFrame from the data
    df = pd.DataFrame(data)
    df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%d/%m/%Y')
    df = df.sort_values(by='Data')

    for index, row in df.iterrows():
        pdf.cell(40, 10, str(row['Data']), 1)
        pdf.cell(80, 10, str(row['Nome Cognome']), 1)
        pdf.cell(70, 10, str(row['RuoloOccupato']), 1)
        pdf.ln()

    # Ensure the reports directory exists
    if not os.path.exists('reports'):
        os.makedirs('reports')

    file_path = f"reports/reperibilita_{month.lower()}_{year}.pdf"
    pdf.output(file_path)
    return file_path
