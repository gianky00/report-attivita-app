import os
import shutil
import pathlib
import stat

# --- Configurazione ---
# PERCORSO DI ORIGINE (cartella di rete da cui leggere)
# Usiamo una stringa raw (r"...") per gestire correttamente i backslash e gli spazi
source_dir = r"\\192.168.11.251\Database_Tecnico_SMI\Contabilita' strumentale\Relazioni di reperibilita'"

# PERCORSO DI DESTINAZIONE (cartella locale dove salvare i file)
dest_dir = r"C:\Users\Coemi\Desktop\SCRIPT\report-attivita-app\knowledge_base_docs"

# Tipi di file da copiare
file_extensions = ('.docx', '.doc')
# --------------------

def sync_files(src_path, dest_path):
    """
    Copia in modo ricorsivo i file da src_path a dest_path,
    aggiornando solo i file nuovi o modificati.
    """
    
    # 1. Converti le stringhe in oggetti Path
    src_path = pathlib.Path(src_path)
    dest_path = pathlib.Path(dest_path)

    # 2. Crea la cartella di destinazione se non esiste
    try:
        dest_path.mkdir(parents=True, exist_ok=True)
        print(f"Cartella di destinazione assicurata: {dest_path}")
    except OSError as e:
        print(f"ERRORE: Impossibile creare la cartella di destinazione {dest_path}. {e}")
        return

    # 3. Verifica se la cartella di origine è accessibile
    if not src_path.exists() or not src_path.is_dir():
        print(f"ERRORE: Il percorso di origine non esiste o non è una cartella: {src_path}")
        return

    print(f"Avvio scansione da: {src_path}")
    print(f"Sincronizzazione in: {dest_path}")
    
    files_copied = 0
    files_skipped = 0

    # 4. Scansiona ricorsivamente la cartella di origine
    #    usando rglob('*') per cercare in tutte le sottocartelle
    for src_file_path in src_path.rglob('*'):
        
        # 5. Controlla se è un file e ha l'estensione corretta
        if src_file_path.is_file() and src_file_path.suffix.lower() in file_extensions:
            
            # 6. Calcola il percorso di destinazione mantenendo la struttura
            #    delle sottocartelle
            relative_path = src_file_path.relative_to(src_path)
            dest_file_path = dest_path / relative_path
            
            # 7. Crea la sottocartella di destinazione se non esiste
            dest_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 8. Logica di aggiornamento (controllo data/ora)
            try:
                # Se il file non esiste a destinazione...
                if not dest_file_path.exists():
                    print(f"COPIO NUOVO: {relative_path}")
                    shutil.copy2(src_file_path, dest_file_path)
                    files_copied += 1
                else:
                    # Se esiste, confronta le date di modifica
                    src_stat = src_file_path.stat()
                    dest_stat = dest_file_path.stat()
                    
                    # Se il file sorgente è più recente (st_mtime >)
                    if src_stat.st_mtime > dest_stat.st_mtime:
                        print(f"AGGIORNO: {relative_path}")
                        shutil.copy2(src_file_path, dest_file_path)
                        files_copied += 1
                    else:
                        # Il file a destinazione è già aggiornato
                        files_skipped += 1
            
            except (IOError, OSError, shutil.Error) as e:
                print(f"ERRORE durante la copia di {src_file_path}: {e}")
            except Exception as e:
                print(f"ERRORE SCONOSCIUTO su file {src_file_path}: {e}")


    print("\n--- Riepilogo Sincronizzazione ---")
    print(f"File copiati/aggiornati: {files_copied}")
    print(f"File saltati (già aggiornati): {files_skipped}")
    print("Operazione completata.")

# Esegui la funzione di sincronizzazione
if __name__ == "__main__":
    sync_files(source_dir, dest_dir)