import datetime
import shutil
from pathlib import Path

# Configurazione percorsi - PERCORSO FORNITO DALL'UTENTE
NETWORK_ROOT = r"\\192.168.11.251\Database_Tecnico_SMI"
LOCAL_SYNC_DIR = Path(__file__).parent.parent / "data_sync"
CURRENT_YEAR = datetime.date.today().year


def sync():
    print("--- ANALISI SINCRONIZZAZIONE ---")
    print(f"Server Rete: {NETWORK_ROOT}")
    print(f"Cartella Locale: {LOCAL_SYNC_DIR}")

    network_path = Path(NETWORK_ROOT)
    if not network_path.exists():
        print(f"CRITICO: Il server di rete {NETWORK_ROOT} non e' raggiungibile da questo PC.")
        return False

    LOCAL_SYNC_DIR.mkdir(parents=True, exist_ok=True)

    # Percorso specifico richiesto dall'utente
    net_giornaliere = network_path / "Giornaliere" / f"Giornaliere {CURRENT_YEAR}"
    loc_giornaliere = LOCAL_SYNC_DIR / "Giornaliere" / f"Giornaliere {CURRENT_YEAR}"

    print(f"Controllo sorgente: {net_giornaliere}")

    if net_giornaliere.exists():
        loc_giornaliere.mkdir(parents=True, exist_ok=True)
        files = list(net_giornaliere.glob("*.xlsm"))
        print(f"Trovati {len(files)} file Excel.")

        for item in files:
            dest = loc_giornaliere / item.name
            try:
                # Copia forzata anche se aperti (usando copy2)
                if not dest.exists() or item.stat().st_mtime > dest.stat().st_mtime:
                    print(f"  > Sincronizzo: {item.name}")
                    shutil.copy2(item, dest)
                else:
                    print(f"  = Gia' aggiornato: {item.name}")
            except Exception as e:
                print(f"  ! Errore copia {item.name}: {e}")
    else:
        print(f"ERRORE: La cartella {net_giornaliere} non esiste sul server.")

    # Altri file critici
    print("Sincronizzazione file radice...")
    for f in ("Database_Report_Attivita.xlsm", "ATTIVITA_PROGRAMMATE.xlsm"):
        # Cerchiamo in piu' posti comuni sul server
        paths = [
            network_path / "cartella strumentale condivisa" / "ALLEGRETTI" / f,
            network_path / f,
        ]
        for p in paths:
            if p.exists():
                print(f"  + Trovato {f} in {p.parent.name}")
                shutil.copy2(p, LOCAL_SYNC_DIR / f)
                break

    print("--- FINE SINCRONIZZAZIONE ---")
    return True


if __name__ == "__main__":
    sync()
