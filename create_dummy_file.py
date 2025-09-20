import pandas as pd
import config

def create_dummy_excel():
    """Crea un file Gestionale_Tecnici.xlsx fittizio per lo sviluppo."""

    # Dati fittizi
    data = {
        'Nome Cognome': ['Mario Rossi', 'Luigi Bianchi', 'Paolo Verdi', 'Gianni Allegretti'],
        'Password': ['pass123', 'qwerty', 'admin', 'password'],
        'Ruolo': ['Tecnico', 'Tecnico', 'Aiutante', 'Amministratore']
    }
    df_contatti = pd.DataFrame(data)

    # Dati vuoti per gli altri fogli per mantenere la struttura
    df_turni = pd.DataFrame(columns=['ID_Turno', 'Descrizione', 'Data', 'OrarioInizio', 'OrarioFine', 'PostiTecnico', 'PostiAiutante', 'Tipo'])
    df_prenotazioni = pd.DataFrame(columns=['ID_Prenotazione', 'ID_Turno', 'Nome Cognome', 'RuoloOccupato', 'Timestamp'])
    df_sostituzioni = pd.DataFrame(columns=['ID_Richiesta', 'ID_Turno', 'Richiedente', 'Ricevente', 'Timestamp'])
    df_notifiche = pd.DataFrame(columns=['ID_Notifica', 'Timestamp', 'Destinatario', 'Messaggio', 'Stato', 'Link_Azione'])
    df_bacheca = pd.DataFrame(columns=['ID_Bacheca', 'ID_Turno', 'Tecnico_Originale', 'Ruolo_Originale', 'Timestamp_Pubblicazione', 'Stato', 'Tecnico_Subentrante', 'Timestamp_Assegnazione'])

    file_path = config.PATH_GESTIONALE

    print(f"Creazione del file fittizio in: '{file_path}'")

    try:
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df_contatti.to_excel(writer, sheet_name='Contatti', index=False)
            df_turni.to_excel(writer, sheet_name='TurniDisponibili', index=False)
            df_prenotazioni.to_excel(writer, sheet_name='Prenotazioni', index=False)
            df_sostituzioni.to_excel(writer, sheet_name='SostituzioniPendenti', index=False)
            df_notifiche.to_excel(writer, sheet_name='Notifiche', index=False)
            df_bacheca.to_excel(writer, sheet_name='TurniInBacheca', index=False)
        print("File fittizio creato con successo.")
    except Exception as e:
        print(f"Errore durante la creazione del file fittizio: {e}")

if __name__ == "__main__":
    create_dummy_excel()
