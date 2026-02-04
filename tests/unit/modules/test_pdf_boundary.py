"""
Stress test per la generazione di documenti PDF.
Verifica la gestione di nomi estremamente lunghi e caratteri speciali.
"""

import pytest
from src.modules.pdf_utils import generate_on_call_pdf

def test_generate_pdf_with_extremely_long_names(mocker):
    """Verifica che il layout PDF non si rompa con nomi tecnici molto lunghi."""
    long_name_1 = "Gianky Allegretti Maria Francesco Saverio de' Medici della Valle"
    long_name_2 = "Tecnico Specializzato in Strumentazione Industriale Avanzata e Robotica"
    
    data = [
        {"Data": "2025-01-01", "RuoloOccupato": "Tecnico", "Nome Cognome": long_name_1},
        {"Data": "2025-01-01", "RuoloOccupato": "Aiutante", "Nome Cognome": long_name_2}
    ]
    
    # Mocking output per non scrivere su disco
    mocker.patch("src.modules.pdf_utils.PDF.output")
    mocker.patch("src.modules.pdf_utils.Path.mkdir")
    
    # Se la funzione crasha qui, il test fallirà
    file_path = generate_on_call_pdf(data, "gennaio", 2025)
    
    assert file_path is not None
    assert "gennaio_2025" in file_path
