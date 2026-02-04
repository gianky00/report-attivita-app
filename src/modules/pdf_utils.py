"""
Utility per la generazione di documenti PDF.
Include la logica per creare il report mensile della reperibilità in formato tabella.
"""

import calendar
from pathlib import Path
from typing import Any

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from src.core.logging import get_logger

logger = get_logger(__name__)


class PDF(FPDF):
    """Classe personalizzata per la generazione di report PDF."""

    def header(self):
        """Metodo per l'intestazione della pagina (attualmente vuota)."""
        pass

    def footer(self):
        """Metodo per il piè di pagina con numerazione."""
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()} di {{nb}}", align="R")


def generate_on_call_pdf(
    data: list[dict[str, Any]], month_name: str, year: int
) -> str | None:
    """
    Genera un file PDF contenente la tabella della reperibilità.
    """
    italian_to_english_month = {
        "gennaio": "January",
        "febbraio": "February",
        "marzo": "March",
        "aprile": "April",
        "maggio": "May",
        "giugno": "June",
        "luglio": "July",
        "agosto": "August",
        "settembre": "September",
        "ottobre": "October",
        "novembre": "November",
        "dicembre": "December",
    }

    english_month = italian_to_english_month.get(month_name.lower())
    if not english_month:
        logger.error(f"Nome mese non valido: {month_name}")
        return None

    try:
        # 1. Preparazione calendario mensile
        month_number = list(calendar.month_name).index(english_month)
        num_days = calendar.monthrange(year, month_number)[1]
        dates = pd.date_range(start=f"{year}-{month_number:02d}-01", periods=num_days)
        df_final = pd.DataFrame(dates, columns=["Data"])

        # 2. Elaborazione dati reperibilità
        if data:
            df_data = pd.DataFrame(data)
            df_data["Data"] = pd.to_datetime(df_data["Data"])
            df_pivot = df_data.pivot_table(
                index="Data",
                columns="RuoloOccupato",
                values="Nome Cognome",
                aggfunc="first",
            ).reset_index()

            df_pivot = df_pivot.rename(
                columns={"Tecnico": "Persona 1", "Aiutante": "Persona 2"}
            )
            for col in ["Persona 1", "Persona 2"]:
                if col not in df_pivot:
                    df_pivot[col] = ""

            df_final = pd.merge(df_final, df_pivot, on="Data", how="left").fillna("")
        else:
            df_final["Persona 1"] = ""
            df_final["Persona 2"] = ""

        # 3. Creazione PDF
        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_font("helvetica", "B", 14)
        title = f"REP.STRUM. ISAB SUD {month_name.upper()} {year}"
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        cell_height = 7
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(30, cell_height, "Data", border=1, align="C")
        pdf.cell(80, cell_height, "Persona 1", border=1, align="C")
        pdf.cell(
            80,
            cell_height,
            "Persona 2",
            border=1,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="C",
        )

        pdf.set_font("helvetica", "", 9)
        for _, row in df_final.iterrows():
            d_str = row["Data"].strftime("%d/%m/%Y")
            pdf.cell(30, cell_height, d_str, border=1, align="C")
            pdf.cell(80, cell_height, str(row["Persona 1"]), border=1, align="L")
            pdf.cell(
                80,
                cell_height,
                str(row["Persona 2"]),
                border=1,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="L",
            )

        # 4. Salvataggio
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        f_name = f"reperibilita_strumentale_{month_name.lower()}_{year}_ISAB_SUD.pdf"
        file_path = report_dir / f_name

        pdf.output(str(file_path))
        logger.info(f"PDF generato con successo: {file_path}")
        return str(file_path)

    except Exception as e:
        logger.error(f"Errore durante la generazione del PDF: {e}", exc_info=True)
        return None
