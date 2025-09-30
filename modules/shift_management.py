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

def log_shift_change(gestionale_data, turno_id, azione, matricola_originale=None, matricola_subentrante=None, matricola_eseguito_da=None):
    """
    Registra una modifica a un turno in un file Excel per l'auditing, usando le matricole.
    """
    try:
        if os.path.exists(LOG_FILE_PATH):
            log_df = pd.read_excel(LOG_FILE_PATH)
        else:
            log_df = pd.DataFrame(columns=[
                'ID_Modifica', 'Timestamp', 'ID_Turno', 'Azione',
                'UtenteOriginale', 'UtenteSubentrante', 'EseguitoDa'
            ])

        df_contatti = gestionale_data['contatti']
        def get_name(matricola):
            if matricola is None: return None
            user = df_contatti[df_contatti['Matricola'] == str(matricola)]
            return user.iloc[0]['Nome Cognome'] if not user.empty else str(matricola)

        new_log_entry = {
            'ID_Modifica': f"M_{int(datetime.datetime.now().timestamp())}",
            'Timestamp': datetime.datetime.now(),
            'ID_Turno': turno_id,
            'Azione': azione,
            'UtenteOriginale': get_name(matricola_originale),
            'UtenteSubentrante': get_name(matricola_subentrante),
            'EseguitoDa': get_name(matricola_eseguito_da)
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

def find_matricola_by_surname(df_contatti, surname_to_find):
    """Cerca la matricola di un contatto basandosi sul cognome (case-insensitive)."""
    if df_contatti.empty or not isinstance(surname_to_find, str):
        return None

    surname_upper = surname_to_find.upper()

    # 1. Cerca una corrispondenza esatta del cognome
    for _, row in df_contatti.iterrows():
        full_name = row.get("Nome Cognome")
        if isinstance(full_name, str) and full_name.strip():
            if full_name.strip().upper().split()[-1] == surname_upper:
                return str(row.get("Matricola"))

    # 2. Fallback a 'contains'
    for _, row in df_contatti.iterrows():
        full_name = row.get("Nome Cognome")
        if isinstance(full_name, str) and full_name.strip():
            if surname_upper in full_name.strip().upper():
                return str(row.get("Matricola"))
    return None

def sync_oncall_shifts(gestionale_data, start_date, end_date):
    """
    Sincronizza i turni di reperibilità, creandoli se non esistono e usando le matricole.
    """
    df_turni = gestionale_data['turni']
    df_prenotazioni = gestionale_data['prenotazioni']
    df_contatti = gestionale_data['contatti']

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
            'ID_Turno': shift_id, 'Descrizione': f"Reperibilità {current_date.strftime('%d/%m/%Y')}",
            'Data': pd.to_datetime(current_date), 'OrarioInizio': '00:00', 'OrarioFine': '23:59',
            'PostiTecnico': len(team_surnames), 'PostiAiutante': 0, 'Tipo': 'Reperibilità'
        }
        df_turni = _safe_concat(df_turni, new_shift)
        for surname in team_surnames:
            matricola = find_matricola_by_surname(df_contatti, surname)
            if matricola:
                new_booking = {
                    'ID_Prenotazione': f"P_{shift_id}_{matricola}", 'ID_Turno': shift_id,
                    'Matricola': matricola, 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()
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
def prenota_turno_logic(gestionale_data, matricola_utente, turno_id, ruolo_scelto):
    df_turni, df_prenotazioni = gestionale_data['turni'], gestionale_data['prenotazioni']
    turno_info = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    posti_tecnico, posti_aiutante = int(float(turno_info['PostiTecnico'])), int(float(turno_info['PostiAiutante']))
    prenotazioni_per_turno = df_prenotazioni[df_prenotazioni['ID_Turno'] == turno_id]
    tecnici_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Tecnico'])
    aiutanti_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Aiutante'])

    success = False
    if ruolo_scelto == 'Tecnico' and tecnici_prenotati < posti_tecnico:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Matricola': str(matricola_utente), 'RuoloOccupato': 'Tecnico', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = _safe_concat(df_prenotazioni, nuova_riga)
        st.success("Turno prenotato come Tecnico!"); success = True
    elif ruolo_scelto == 'Aiutante' and aiutanti_prenotati < posti_aiutante:
        nuova_riga = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Matricola': str(matricola_utente), 'RuoloOccupato': 'Aiutante', 'Timestamp': datetime.datetime.now()}
        gestionale_data['prenotazioni'] = _safe_concat(df_prenotazioni, nuova_riga)
        st.success("Turno prenotato come Aiutante!"); success = True
    else:
        st.error("Tutti i posti per il ruolo selezionato sono esauriti!"); return False

    if success:
        log_shift_change(gestionale_data, turno_id, "Prenotazione", matricola_subentrante=matricola_utente, matricola_eseguito_da=matricola_utente)
    return success

def cancella_prenotazione_logic(gestionale_data, matricola_utente, turno_id):
    index_to_drop = gestionale_data['prenotazioni'][(gestionale_data['prenotazioni']['ID_Turno'] == turno_id) & (gestionale_data['prenotazioni']['Matricola'] == str(matricola_utente))].index
    if not index_to_drop.empty:
        gestionale_data['prenotazioni'].drop(index_to_drop, inplace=True)
        log_shift_change(gestionale_data, turno_id, "Cancellazione", matricola_originale=matricola_utente, matricola_eseguito_da=matricola_utente)
        st.success("Prenotazione cancellata."); return True
    st.error("Prenotazione non trovata."); return False

def richiedi_sostituzione_logic(gestionale_data, matricola_richiedente, matricola_ricevente, turno_id):
    nome_richiedente = gestionale_data['contatti'][gestionale_data['contatti']['Matricola'] == str(matricola_richiedente)].iloc[0]['Nome Cognome']

    nuova_richiesta = {'ID_Richiesta': f"S_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Richiedente_Matricola': str(matricola_richiedente), 'Ricevente_Matricola': str(matricola_ricevente), 'Timestamp': datetime.datetime.now()}
    gestionale_data['sostituzioni'] = _safe_concat(gestionale_data['sostituzioni'], nuova_richiesta)

    messaggio = f"Hai una nuova richiesta di sostituzione da {nome_richiedente} per il turno {turno_id}."
    crea_notifica(gestionale_data, matricola_ricevente, messaggio)

    st.success(f"Richiesta di sostituzione inviata.");
    st.toast("Richiesta inviata! Il collega riceverà una notifica.")
    return True

def rispondi_sostituzione_logic(gestionale_data, id_richiesta, matricola_che_risponde, accettata):
    sostituzioni_df = gestionale_data['sostituzioni']
    richiesta_index = sostituzioni_df[sostituzioni_df['ID_Richiesta'] == id_richiesta].index
    if richiesta_index.empty:
        st.error("Richiesta non più valida."); return False

    richiesta = sostituzioni_df.loc[richiesta_index[0]]
    matricola_richiedente = richiesta['Richiedente_Matricola']
    turno_id = richiesta['ID_Turno']
    nome_che_risponde = gestionale_data['contatti'][gestionale_data['contatti']['Matricola'] == str(matricola_che_risponde)].iloc[0]['Nome Cognome']

    messaggio = f"{nome_che_risponde} ha {'ACCETTATO' if accettata else 'RIFIUTATO'} la tua richiesta di cambio per il turno {turno_id}."
    crea_notifica(gestionale_data, matricola_richiedente, messaggio)
    gestionale_data['sostituzioni'].drop(richiesta_index, inplace=True)

    if not accettata:
        st.info("Hai rifiutato la richiesta."); st.toast("Risposta inviata."); return True

    prenotazioni_df = gestionale_data['prenotazioni']
    idx_richiedente = prenotazioni_df[(prenotazioni_df['ID_Turno'] == turno_id) & (prenotazioni_df['Matricola'] == str(matricola_richiedente))].index
    if not idx_richiedente.empty:
        prenotazioni_df.loc[idx_richiedente, 'Matricola'] = str(matricola_che_risponde)
        log_shift_change(gestionale_data, turno_id, "Sostituzione Accettata", matricola_originale=matricola_richiedente, matricola_subentrante=matricola_che_risponde, matricola_eseguito_da=matricola_che_risponde)
        st.success("Sostituzione (subentro) effettuata con successo!"); return True

    st.error("Errore: la prenotazione originale del richiedente non è stata trovata."); return False

def pubblica_turno_in_bacheca_logic(gestionale_data, matricola_richiedente, turno_id):
    df_prenotazioni = gestionale_data['prenotazioni']
    idx_prenotazione = df_prenotazioni[(df_prenotazioni['Matricola'] == str(matricola_richiedente)) & (df_prenotazioni['ID_Turno'] == turno_id)].index
    if idx_prenotazione.empty:
        st.error("Errore: Prenotazione non trovata."); return False

    prenotazione_rimossa = df_prenotazioni.loc[idx_prenotazione].iloc[0]
    ruolo_originale = prenotazione_rimossa['RuoloOccupato']
    gestionale_data['prenotazioni'].drop(idx_prenotazione, inplace=True)

    df_bacheca = gestionale_data.get('bacheca', pd.DataFrame())
    nuovo_id_bacheca = f"B_{int(datetime.datetime.now().timestamp())}"
    nuova_voce_bacheca = {'ID_Bacheca': nuovo_id_bacheca, 'ID_Turno': turno_id, 'Tecnico_Originale_Matricola': str(matricola_richiedente), 'Ruolo_Originale': ruolo_originale, 'Timestamp_Pubblicazione': datetime.datetime.now(), 'Stato': 'Disponibile', 'Tecnico_Subentrante_Matricola': None, 'Timestamp_Assegnazione': None}
    gestionale_data['bacheca'] = _safe_concat(df_bacheca, nuova_voce_bacheca)

    log_shift_change(gestionale_data, turno_id, "Pubblicazione in Bacheca", matricola_originale=matricola_richiedente, matricola_eseguito_da=matricola_richiedente)

    df_turni = gestionale_data['turni']
    turno_info = df_turni[df_turni['ID_Turno'] == turno_id].iloc[0]
    messaggio = f"📢 Turno libero: '{turno_info['Descrizione']}' del {pd.to_datetime(turno_info['Data']).strftime('%d/%m')} ({ruolo_originale})."

    matricole_da_notificare = gestionale_data['contatti']['Matricola'].tolist()
    for matricola in matricole_da_notificare:
        if str(matricola) != str(matricola_richiedente):
            crea_notifica(gestionale_data, matricola, messaggio)

    st.success("Il tuo turno è stato pubblicato in bacheca!"); st.toast("Tutti i colleghi sono stati notificati."); return True

def prendi_turno_da_bacheca_logic(gestionale_data, matricola_subentrante, ruolo_utente, id_bacheca):
    df_bacheca = gestionale_data['bacheca']
    idx_bacheca = df_bacheca[df_bacheca['ID_Bacheca'] == id_bacheca].index
    if idx_bacheca.empty:
        st.error("Questo turno non è più disponibile."); return False

    voce_bacheca = df_bacheca.loc[idx_bacheca.iloc[0]]
    if voce_bacheca['Stato'] != 'Disponibile':
        st.warning("Qualcuno è stato più veloce! Turno già assegnato."); return False

    ruolo_richiesto = voce_bacheca['Ruolo_Originale']
    if ruolo_richiesto == 'Tecnico' and ruolo_utente == 'Aiutante':
        st.error(f"Non sei idoneo. È richiesto il ruolo 'Tecnico'."); return False

    matricola_originale = voce_bacheca['Tecnico_Originale_Matricola']
    turno_id = voce_bacheca['ID_Turno']
    nome_subentrante = gestionale_data['contatti'][gestionale_data['contatti']['Matricola'] == str(matricola_subentrante)].iloc[0]['Nome Cognome']

    df_bacheca.loc[idx_bacheca, 'Stato'] = 'Assegnato'
    df_bacheca.loc[idx_bacheca, 'Tecnico_Subentrante_Matricola'] = str(matricola_subentrante)
    df_bacheca.loc[idx_bacheca, 'Timestamp_Assegnazione'] = datetime.datetime.now()

    nuova_prenotazione = {'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}", 'ID_Turno': turno_id, 'Matricola': str(matricola_subentrante), 'RuoloOccupato': ruolo_richiesto, 'Timestamp': datetime.datetime.now()}
    gestionale_data['prenotazioni'] = _safe_concat(gestionale_data['prenotazioni'], nuova_prenotazione)

    log_shift_change(gestionale_data, turno_id, "Preso da Bacheca", matricola_originale=matricola_originale, matricola_subentrante=matricola_subentrante, matricola_eseguito_da=matricola_subentrante)

    turno_info = gestionale_data['turni'][gestionale_data['turni']['ID_Turno'] == turno_id].iloc[0]
    desc_turno = turno_info['Descrizione']
    data_turno = pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')

    messaggio_subentrante = f"Hai preso il turno '{desc_turno}' del {data_turno}."
    crea_notifica(gestionale_data, matricola_subentrante, messaggio_subentrante)
    messaggio_originale = f"Il tuo turno '{desc_turno}' del {data_turno} è stato preso da {nome_subentrante}."
    crea_notifica(gestionale_data, matricola_originale, messaggio_originale)

    st.success(f"Ti sei prenotato con successo per il turno come {ruolo_richiesto}!"); st.balloons(); return True