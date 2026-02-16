import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from modules.importers.excel_giornaliera import _match_partial_name

def test_matching():
    cases = [
        ("G. Allegretti", "Giancarlo Allegretti", True),
        ("Allegretti G.", "Giancarlo Allegretti", True),
        ("Giancarlo Allegretti", "Giancarlo Allegretti", True),
        ("G.B. Spinali", "Giovanni Battista Spinali", True),
        ("Spinali G.B.", "Giovanni Battista Spinali", True),
        ("Mario Rossi", "Mario Rossi", True),
        ("M. Rossi", "Mario Rossi", True),
        ("Rossi M.", "Mario Rossi", True),
        ("Rossi", "Mario Rossi", True),
        ("Giancarlo", "Giancarlo Allegretti", True),
        ("Allegretti", "Giancarlo Allegretti", True),
        ("D. Spinali", "Domenico Spinali", True),
        ("S. Riciputo", "Sebastiano Riciputo", True),
    ]
    
    for partial, full, expected in cases:
        result = _match_partial_name(partial, full)
        status = "PASS" if result == expected else "FAIL"
        print(f"[{status}] '{partial}' vs '{full}' -> {result} (Expected: {expected})")

if __name__ == "__main__":
    test_matching()
