import streamlit as st
import pandas as pd
import datetime
from modules.notifications import crea_notifica

# --- LOGICA DI BUSINESS PER I TURNI ---
def prenota_turno_logic(gestionale_data, utente, turno_id, ruolo_scelto):
    df_turni, df_prenotazioni = gestionale_data['turni'], gestionale_data['prenotazioni']
    turno_info = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    posti_tecnico, posti_aiutante = int(float(turno_info['PostiTecnico'])), int(float(turno_info['PostiAiutante']))
    prenotazioni_per_turno = df_prenotazioni[df_prenotazioni['ID_Turno'] == turno_id]
    tecnici_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Tecnico'])
    aiutanti_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Aiutante'])
    if ruolo_scelto == 'Tecnico' and tecnici_prenotati < posti_tecnico:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = pd.concat([df_prenotazioni, pd.DataFrame([nuova_riga])], ignore_index=True)
        st.success("Turno prenotato come Tecnico!"); return True
    elif ruolo_scelto == 'Aiutante' and aiutanti_prenotati < posti_aiutante:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Aiutante', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = pd.concat([df_prenotazioni, pd.DataFrame([nuova_riga])], ignore_index=True)
        st.success("Turno prenotato come Aiutante!"); return True
    else:
        st.error("Tutti i posti per il ruolo selezionato sono esauriti!"); return False

def cancella_prenotazione_logic(gestionale_data, utente, turno_id):
    index_to_drop = gestionale_data['prenotazioni'][(gestionale_data['prenotazioni']['ID_Turno'] == turno_id) & (gestionale_data['prenotazioni']['Nome Cognome'] == utente)].index
    if not index_to_drop.empty:
        gestionale_data['prenotazioni'].drop(index_to_drop, inplace=True)
        st.success("Prenotazione cancellata."); return True
    st.error("Prenotazione non trovata."); return False

def richiedi_sostituzione_logic(gestionale_data, richiedente, ricevente, turno_id):
    nuova_richiesta = pd.DataFrame([{'ID_Richiesta': f"S_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Richiedente': richiedente, 'Ricevente': ricevente, 'Timestamp': datetime.datetime.now()}])
    gestionale_data['sostituzioni'] = pd.concat([gestionale_data['sostituzioni'], nuova_richiesta], ignore_index=True)

    messaggio = f"Hai una nuova richiesta di sostituzione da {richiedente} per il turno {turno_id}."
    crea_notifica(gestionale_data, ricevente, messaggio)

    st.success(f"Richiesta di sostituzione inviata a {ricevente}.")
    st.toast("Richiesta inviata! Il collega riceverà una notifica.")
    return True

def rispondi_sostituzione_logic(gestionale_data, id_richiesta, utente_che_risponde, accettata):
    sostituzioni_df = gestionale_data['sostituzioni']
    richiesta_index = sostituzioni_df[sostituzioni_df['ID_Richiesta'] == id_richiesta].index
    if richiesta_index.empty:
        st.error("Richiesta non più valida.")
        return False

    richiesta = sostituzioni_df.loc[richiesta_index[0]]
    richiedente = richiesta['Richiedente']
    turno_id = richiesta['ID_Turno']

    if accettata:
        messaggio = f"{utente_che_risponde} ha ACCETTATO la tua richiesta di cambio per il turno {turno_id}."
    else:
        messaggio = f"{utente_che_risponde} ha RIFIUTATO la tua richiesta di cambio per il turno {turno_id}."
    crea_notifica(gestionale_data, richiedente, messaggio)

    gestionale_data['sostituzioni'].drop(richiesta_index, inplace=True)

    if not accettata:
        st.info("Hai rifiutato la richiesta.")
        st.toast("Risposta inviata. Il richiedente è stato notificato.")
        return True

    # Logic for accepted request
    prenotazioni_df = gestionale_data['prenotazioni']
    idx_richiedente_originale = prenotazioni_df[(prenotazioni_df['ID_Turno'] == turno_id) & (prenotazioni_df['Nome Cognome'] == richiedente)].index

    if not idx_richiedente_originale.empty:
        prenotazioni_df.loc[idx_richiedente_originale, 'Nome Cognome'] = utente_che_risponde
        st.success("Sostituzione (subentro) effettuata con successo!")
        st.toast("Sostituzione effettuata! Il richiedente è stato notificato.")
        return True

    st.error("Errore: la prenotazione originale del richiedente non è stata trovata per lo scambio.")
    return False

def pubblica_turno_in_bacheca_logic(gestionale_data, utente_richiedente, turno_id):
    df_prenotazioni = gestionale_data['prenotazioni']

    # Trova la prenotazione dell'utente per il turno specificato
    idx_prenotazione = df_prenotazioni[(df_prenotazioni['Nome Cognome'] == utente_richiedente) & (df_prenotazioni['ID_Turno'] == turno_id)].index

    if idx_prenotazione.empty:
        st.error("Errore: Prenotazione non trovata per pubblicare in bacheca.")
        return False

    # Ottieni i dettagli della prenotazione prima di rimuoverla
    prenotazione_rimossa = df_prenotazioni.loc[idx_prenotazione].iloc[0]
    ruolo_originale = prenotazione_rimossa['RuoloOccupato']

    # Rimuovi la vecchia prenotazione
    gestionale_data['prenotazioni'].drop(idx_prenotazione, inplace=True)

    # Aggiungi il turno alla bacheca
    df_bacheca = gestionale_data['bacheca']
    nuovo_id_bacheca = f"B_{int(datetime.datetime.now().timestamp())}"
    nuova_voce_bacheca = pd.DataFrame([{
        'ID_Bacheca': nuovo_id_bacheca,
        'ID_Turno': turno_id,
        'Tecnico_Originale': utente_richiedente,
        'Ruolo_Originale': ruolo_originale,
        'Timestamp_Pubblicazione': datetime.datetime.now(),
        'Stato': 'Disponibile',
        'Tecnico_Subentrante': None,
        'Timestamp_Assegnazione': None
    }])
    gestionale_data['bacheca'] = pd.concat([df_bacheca, nuova_voce_bacheca], ignore_index=True)

    # Invia notifica a tutti gli altri utenti
    df_turni = gestionale_data['turni']
    desc_turno = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]['Descrizione']
    data_turno = pd.to_datetime(df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]['Data']).strftime('%d/%m')

    messaggio = f"📢 Turno libero in bacheca: '{desc_turno}' del {data_turno} ({ruolo_originale})."

    utenti_da_notificare = gestionale_data['contatti']['Nome Cognome'].tolist()
    for utente in utenti_da_notificare:
        if utente != utente_richiedente:
            crea_notifica(gestionale_data, utente, messaggio)

    st.success("Il tuo turno è stato pubblicato in bacheca con successo!")
    st.toast("Tutti i colleghi sono stati notificati.")
    return True


def prendi_turno_da_bacheca_logic(gestionale_data, utente_subentrante, ruolo_utente, id_bacheca):
    df_bacheca = gestionale_data['bacheca']

    # Trova la voce in bacheca
    idx_bacheca = df_bacheca[df_bacheca['ID_Bacheca'] == id_bacheca].index
    if idx_bacheca.empty:
        st.error("Questo turno non è più disponibile in bacheca.")
        return False

    voce_bacheca = df_bacheca.loc[idx_bacheca.iloc[0]]

    if voce_bacheca['Stato'] != 'Disponibile':
        st.warning("Qualcuno è stato più veloce! Questo turno è già stato assegnato.")
        return False

    ruolo_richiesto = voce_bacheca['Ruolo_Originale']

    # Controlla l'idoneità del ruolo
    if ruolo_richiesto == 'Tecnico' and ruolo_utente == 'Aiutante':
        st.error(f"Non sei idoneo per questo turno. È richiesto il ruolo 'Tecnico'.")
        return False

    # Assegna il turno
    df_bacheca.loc[idx_bacheca, 'Stato'] = 'Assegnato'
    df_bacheca.loc[idx_bacheca, 'Tecnico_Subentrante'] = utente_subentrante
    df_bacheca.loc[idx_bacheca, 'Timestamp_Assegnazione'] = datetime.datetime.now()

    # Aggiungi la nuova prenotazione
    df_prenotazioni = gestionale_data['prenotazioni']
    nuova_prenotazione = pd.DataFrame([{
        'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}",
        'ID_Turno': voce_bacheca['ID_Turno'],
        'Nome Cognome': utente_subentrante,
        'RuoloOccupato': ruolo_richiesto, # L'utente prende il ruolo che si è liberato
        'Timestamp': datetime.datetime.now()
    }])
    gestionale_data['prenotazioni'] = pd.concat([df_prenotazioni, nuova_prenotazione], ignore_index=True)

    # Invia notifiche di conferma
    tecnico_originale = voce_bacheca['Tecnico_Originale']
    df_turni = gestionale_data['turni']
    turno_info = df_turni[df_turni['ID_Turno'] == voce_bacheca['ID_Turno']].iloc[0]
    desc_turno = turno_info['Descrizione']
    data_turno = pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')

    messaggio_subentrante = f"Hai preso con successo il turno '{desc_turno}' del {data_turno} dalla bacheca."
    crea_notifica(gestionale_data, utente_subentrante, messaggio_subentrante)

    messaggio_originale = f"Il tuo turno '{desc_turno}' del {data_turno} è stato preso da {utente_subentrante}."
    crea_notifica(gestionale_data, tecnico_originale, messaggio_originale)

    st.success(f"Ti sei prenotato con successo per il turno come {ruolo_richiesto}!")
    st.balloons()
    return True
