"""
Configurazione globale per pytest.
Aggiunge la cartella 'src' al path di sistema per permettere gli import durante i test.
"""

import sys
from pathlib import Path

# Aggiungi la root del progetto al path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / "src"))
