import streamlit as st
import pandas as pd
import datetime
from modules.notifications import crea_notifica
import os

# --- LOGICA DI AUDITING ---
LOG_FILE_PATH = 'Storico_Modifiche_Turni.xlsx'

def _safe_concat(df, new_row_dict):
    """Safely concatenates a new row to a DataFrame, handling empty DFs."""
    new_row_df = pd.DataFrame([new_row_dict])
    if df.empty:
        return new_row_df
    return pd.concat([df, new_row_df], ignore_index=True)

def log_shift_change(turno_id, azione, utente_originale=None, utente_subentrante=None, eseguito_da=None):
    """
    Registra una modifica a un turno in un file Excel per l'auditing.
    """
    try:
        if os.path.exists(LOG_FILE_PATH):
            log_df = pd.read_excel(LOG_FILE_PATH)
        else:
            log_df = pd.DataFrame(columns=[
                'ID_Modifica', 'Timestamp', 'ID_Turno', 'Azione',
                'UtenteOriginale', 'UtenteSubentrante', 'EseguitoDa'
            ])
        new_log_entry = {
            'ID_Modifica': f"M_{int(datetime.datetime.now().timestamp())}",
            'Timestamp': datetime.datetime.now(),
            'ID_Turno': turno_id,
            'Azione': azione,
            'UtenteOriginale': utente_originale,
            'UtenteSubentrante': utente_subentrante,
            'EseguitoDa': eseguito_da
        }
        log_df = _safe_concat(log_df, new_log_entry)
        log_df.to_excel(LOG_FILE_PATH, index=False)
        return True
    except Exception as e:
        st.error(f"Errore durante la registrazione della modifica: {e}")
        return False

# --- LOGICA DI BUSINESS PER LA REPERIBILITÀ ---

def get_oncall_team_for_date(target_date):
    """
    Calcola il team di reperibilità per una data specifica basandosi su una rotazione di 28 giorni.
    """
    teams = [
        ["RICIPUTO", "GUARINO"],
        ["SPINALI", "ALLEGRETTI"],
        ["MILLO", "GUARINO"],
        ["TARASCIO", "PARTESANO"],
    ]
    reference_date = datetime.date(2025, 10, 3)
    delta_days = (target_date - reference_date).days
    team_index = (delta_days // 7) % 4
    return teams[team_index]

def sync_oncall_shifts(gestionale_data, start_date, end_date):
    """
    Sincronizza i turni di reperibilità, creandoli se non esistono.
    Usa la logica di rotazione dinamica e un matching flessibile dei nomi.
    """
    df_turni = gestionale_data['turni']
    df_prenotazioni = gestionale_data['prenotazioni']
    df_contatti = gestionale_data['contatti']

    def find_contact_by_surname(surname_to_find):
        """Cerca il nome completo di un contatto basandosi sul cognome (case-insensitive)."""
        if df_contatti.empty or not isinstance(surname_to_find, str):
            return None

        surname_upper = surname_to_find.upper()

        # 1. Cerca una corrispondenza esatta del cognome (più affidabile)
        for _, row in df_contatti.iterrows():
            full_name = row.get("Nome Cognome")
            if isinstance(full_name, str) and full_name.strip():
                if full_name.strip().upper().split()[-1] == surname_upper:
                    return full_name.strip()

        # 2. Se non trova, prova con 'contains' come fallback
        for _, row in df_contatti.iterrows():
            full_name = row.get("Nome Cognome")
            if isinstance(full_name, str) and full_name.strip():
                if surname_upper in full_name.strip().upper():
                    return full_name.strip()
        return None

    changes_made = False
    current_date = start_date
    while current_date <= end_date:
        if not df_turni[(df_turni['Tipo'] == 'Reperibilità') & (pd.to_datetime(df_turni['Data']).dt.date == current_date)].empty:
            current_date += datetime.timedelta(days=1)
            continue
        changes_made = True
        team_surnames = get_oncall_team_for_date(current_date)
        date_str = current_date.strftime("%Y-%m-%d")
        shift_id = f"REP_{date_str}"
        new_shift = {
            'ID_Turno': shift_id,
            'Descrizione': f"Reperibilità {current_date.strftime('%d/%m/%Y')}",
            'Data': pd.to_datetime(current_date),
            'OrarioInizio': '00:00',
            'OrarioFine': '23:59',
            'PostiTecnico': len(team_surnames),
            'PostiAiutante': 0,
            'Tipo': 'Reperibilità'
        }
        df_turni = _safe_concat(df_turni, new_shift)
        for surname in team_surnames:
            full_name = find_contact_by_surname(surname)
            if full_name:
                new_booking = {
                    'ID_Prenotazione': f"P_{shift_id}_{full_name.replace(' ', '')}",
                    'ID_Turno': shift_id,
                    'Nome Cognome': full_name,
                    'RuoloOccupato': 'Tecnico',
                    'Timestamp': datetime.datetime.now()
                }
                df_prenotazioni = _safe_concat(df_prenotazioni, new_booking)
            else:
                st.warning(f"Attenzione: Il cognome '{surname}' dal calendario reperibilità non è stato trovato nei contatti.")
        current_date += datetime.timedelta(days=1)
    if changes_made:
        gestionale_data['turni'] = df_turni
        gestionale_data['prenotazioni'] = df_prenotazioni
    return changes_made


# --- LOGICA DI BUSINESS PER I TURNI STANDARD ---
def prenota_turno_logic(gestionale_data, utente, turno_id, ruolo_scelto):
    df_turni, df_prenotazioni = gestionale_data['turni'], gestionale_data['prenotazioni']
    turno_info = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    posti_tecnico, posti_aiutante = int(float(turno_info['PostiTecnico'])), int(float(turno_info['PostiAiutante']))
    prenotazioni_per_turno = df_prenotazioni[df_prenotazioni['ID_Turno'] == turno_id]
    tecnici_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Tecnico'])
    aiutanti_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Aiutante'])

    success = False
    if ruolo_scelto == 'Tecnico' and tecnici_prenotati < posti_tecnico:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = _safe_concat(df_prenotazioni, nuova_riga)
        st.success("Turno prenotato come Tecnico!"); success = True
    elif ruolo_scelto == 'Aiutante' and aiutanti_prenotati < posti_aiutante:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Nome Cognome': utente, 'RuoloOccupato': 'Aiutante', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = _safe_concat(df_prenotazioni, nuova_riga)
        st.success("Turno prenotato come Aiutante!"); success = True
    else:
        st.error("Tutti i posti per il ruolo selezionato sono esauriti!"); return False

    if success:
        log_shift_change(
            turno_id=turno_id,
            azione="Prenotazione",
            utente_subentrante=utente,
            eseguito_da=utente
        )
    return success

def cancella_prenotazione_logic(gestionale_data, utente, turno_id):
    index_to_drop = gestionale_data['prenotazioni'][(gestionale_data['prenotazioni']['ID_Turno'] == turno_id) & (gestionale_data['prenotazioni']['Nome Cognome'] == utente)].index
    if not index_to_drop.empty:
        gestionale_data['prenotazioni'].drop(index_to_drop, inplace=True)
        log_shift_change(
            turno_id=turno_id,
            azione="Cancellazione",
            utente_originale=utente,
            eseguito_da=utente
        )
        st.success("Prenotazione cancellata."); return True
    st.error("Prenotazione non trovata."); return False

def richiedi_sostituzione_logic(gestionale_data, richiedente, ricevente, turno_id):
    nuova_richiesta = {'ID_Richiesta': f"S_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Richiedente': richiedente, 'Ricevente': ricevente, 'Timestamp': datetime.datetime.now()}
    gestionale_data['sostituzioni'] = _safe_concat(gestionale_data['sostituzioni'], nuova_richiesta)

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
        log_shift_change(
            turno_id=turno_id,
            azione="Sostituzione Accettata",
            utente_originale=richiedente,
            utente_subentrante=utente_che_risponde,
            eseguito_da=utente_che_risponde
        )
        st.success("Sostituzione (subentro) effettuata con successo!")
        st.toast("Sostituzione effettuata! Il richiedente è stato notificato.")
        return True

    st.error("Errore: la prenotazione originale del richiedente non è stata trovata per lo scambio.")
    return False

def pubblica_turno_in_bacheca_logic(gestionale_data, utente_richiedente, turno_id):
    df_prenotazioni = gestionale_data['prenotazioni']
    idx_prenotazione = df_prenotazioni[(df_prenotazioni['Nome Cognome'] == utente_richiedente) & (df_prenotazioni['ID_Turno'] == turno_id)].index

    if idx_prenotazione.empty:
        st.error("Errore: Prenotazione non trovata per pubblicare in bacheca.")
        return False

    prenotazione_rimossa = df_prenotazioni.loc[idx_prenotazione].iloc[0]
    ruolo_originale = prenotazione_rimossa['RuoloOccupato']
    gestionale_data['prenotazioni'].drop(idx_prenotazione, inplace=True)

    df_bacheca = gestionale_data.get('bacheca', pd.DataFrame(columns=['ID_Bacheca', 'ID_Turno', 'Tecnico_Originale', 'Ruolo_Originale', 'Timestamp_Pubblicazione', 'Stato', 'Tecnico_Subentrante', 'Timestamp_Assegnazione']))
    nuovo_id_bacheca = f"B_{int(datetime.datetime.now().timestamp())}"
    nuova_voce_bacheca = {'ID_Bacheca': nuovo_id_bacheca, 'ID_Turno': turno_id, 'Tecnico_Originale': utente_richiedente, 'Ruolo_Originale': ruolo_originale, 'Timestamp_Pubblicazione': datetime.datetime.now(), 'Stato': 'Disponibile', 'Tecnico_Subentrante': None, 'Timestamp_Assegnazione': None}
    gestionale_data['bacheca'] = _safe_concat(df_bacheca, nuova_voce_bacheca)

    log_shift_change(
        turno_id=turno_id,
        azione="Pubblicazione in Bacheca",
        utente_originale=utente_richiedente,
        eseguito_da=utente_richiedente
    )

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
    idx_bacheca = df_bacheca[df_bacheca['ID_Bacheca'] == id_bacheca].index
    if idx_bacheca.empty:
        st.error("Questo turno non è più disponibile in bacheca."); return False

    voce_bacheca = df_bacheca.loc[idx_bacheca.iloc[0]]
    if voce_bacheca['Stato'] != 'Disponibile':
        st.warning("Qualcuno è stato più veloce! Questo turno è già stato assegnato."); return False

    ruolo_richiesto = voce_bacheca['Ruolo_Originale']
    if ruolo_richiesto == 'Tecnico' and ruolo_utente == 'Aiutante':
        st.error(f"Non sei idoneo per questo turno. È richiesto il ruolo 'Tecnico'."); return False

    tecnico_originale = voce_bacheca['Tecnico_Originale']
    turno_id = voce_bacheca['ID_Turno']

    df_bacheca.loc[idx_bacheca, 'Stato'] = 'Assegnato'
    df_bacheca.loc[idx_bacheca, 'Tecnico_Subentrante'] = utente_subentrante
    df_bacheca.loc[idx_bacheca, 'Timestamp_Assegnazione'] = datetime.datetime.now()

    df_prenotazioni = gestionale_data['prenotazioni']
    nuova_prenotazione = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Nome Cognome': utente_subentrante, 'RuoloOccupato': ruolo_richiesto, 'Timestamp': datetime.datetime.now()}
    gestionale_data['prenotazioni'] = _safe_concat(df_prenotazioni, nuova_prenotazione)

    log_shift_change(
        turno_id=turno_id,
        azione="Preso da Bacheca",
        utente_originale=tecnico_originale,
        utente_subentrante=utente_subentrante,
        eseguito_da=utente_subentrante
    )

    df_turni = gestionale_data['turni']
    turno_info = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    desc_turno = turno_info['Descrizione']
    data_turno = pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')

    messaggio_subentrante = f"Hai preso con successo il turno '{desc_turno}' del {data_turno} dalla bacheca."
    crea_notifica(gestionale_data, utente_subentrante, messaggio_subentrante)
    messaggio_originale = f"Il tuo turno '{desc_turno}' del {data_turno} è stato preso da {utente_subentrante}."
    crea_notifica(gestionale_data, tecnico_originale, messaggio_originale)

    st.success(f"Ti sei prenotato con successo per il turno come {ruolo_richiesto}!")
    st.balloons()
    return True