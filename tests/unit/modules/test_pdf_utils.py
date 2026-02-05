"""
Test unitari per la generazione di PDF.
"""

from pathlib import Path

from modules.pdf_utils import generate_on_call_pdf


def test_generate_on_call_pdf_success(tmp_path, monkeypatch):
    """Verifica la creazione corretta di un file PDF."""
    # Cambiamo la directory di lavoro o mockiamo Path per salvare nel tmp_path
    monkeypatch.chdir(tmp_path)

    test_data = [
        {
            "Data": "2025-01-01",
            "RuoloOccupato": "Tecnico",
            "Nome Cognome": "Mario Rossi",
        },
        {
            "Data": "2025-01-01",
            "RuoloOccupato": "Aiutante",
            "Nome Cognome": "Luigi Verdi",
        },
    ]

    file_path = generate_on_call_pdf(test_data, "gennaio", 2025)

    assert file_path is not None
    assert Path(file_path).exists()
    assert Path(file_path).suffix == ".pdf"


def test_generate_on_call_pdf_invalid_month():
    """Verifica la gestione di un mese non valido."""
    result = generate_on_call_pdf([], "mesefinto", 2025)
    assert result is None
