import streamlit as st
import pandas as pd
import datetime
from modules.db_manager import (
    get_shifts_by_type,
    get_all_users,
    create_shift,
    add_booking,
    get_shift_by_id,
    get_bookings_for_shift,
    delete_booking,
    add_substitution_request,
    get_substitution_request_by_id,
    delete_substitution_request,
    update_booking_user,
    get_booking_by_user_and_shift,
    get_bacheca_item_by_id,
    update_bacheca_item,
    get_db_connection,
    add_shift_log,
    delete_bookings_for_shift
)
from modules.auth import get_user_by_matricola
from modules.notifications import crea_notifica
from modules.oncall_logic import get_on_call_pair
import os
import warnings
import sqlite3

# Sopprime il warning specifico di openpyxl relativo alla "Print area"
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl.reader.workbook",
    message="Print area cannot be set to Defined name: .*."
)


def log_shift_change(turno_id, azione, matricola_originale=None, matricola_subentrante=None, matricola_eseguito_da=None):
    """Registra una modifica a un turno nel database."""

    def get_name(matricola):
        if matricola is None: return None
        user = get_user_by_matricola(matricola)
        return user['Nome Cognome'] if user else str(matricola)

    log_data = {
        'ID_Modifica': f"M_{int(datetime.datetime.now().timestamp())}",
        'Timestamp': datetime.datetime.now().isoformat(),
        'ID_Turno': turno_id,
        'Azione': azione,
        'UtenteOriginale': get_name(matricola_originale),
        'UtenteSubentrante': get_name(matricola_subentrante),
        'EseguitoDa': get_name(matricola_eseguito_da)
    }
    add_shift_log(log_data)

# --- LOGICA DI BUSINESS PER LA REPERIBILITÀ ---

def find_matricola_by_surname(df_contatti, surname_to_find):
    """Cerca la matricola di un contatto basandosi sul cognome (case-insensitive)."""
    if df_contatti.empty or not isinstance(surname_to_find, str):
        return None

    surname_upper = surname_to_find.upper()

    # Cerca una corrispondenza esatta del cognome
    for _, row in df_contatti.iterrows():
        full_name = row.get("Nome Cognome")
        if isinstance(full_name, str) and full_name.strip():
            # Assumiamo che il cognome sia l'ultima parola nel nome completo
            if full_name.strip().upper().split()[-1] == surname_upper:
                return str(row.get("Matricola"))
    return None

def sync_oncall_shifts(start_date, end_date):
    """
    Sincronizza i turni di reperibilità in modo transazionale.
    """
    df_turni = get_shifts_by_type('Reperibilità')
    df_contatti = get_all_users()

    # Convert 'Data' column to date objects for comparison
    if not df_turni.empty:
        # Using format='mixed' allows parsing of both ISO YYYY-MM-DD and other formats
        # without raising a warning when dayfirst is not strictly needed.
        df_turni['date_only'] = pd.to_datetime(df_turni['Data'], errors='coerce', format='mixed').dt.date
    else:
        df_turni['date_only'] = pd.Series(dtype='object')

    changes_made = False
    current_date = start_date
    while current_date <= end_date:
        if current_date in df_turni['date_only'].values:
            current_date += datetime.timedelta(days=1)
            continue

        changes_made = True

        # Usa la nuova logica di rotazione per ottenere la coppia di reperibilità
        pair = get_on_call_pair(current_date)
        (technician1, tech1_role), (technician2, tech2_role) = pair

        date_str = current_date.strftime("%Y-%m-%d")
        shift_id = f"REP_{date_str}"
        new_shift = {
            'ID_Turno': shift_id, 'Descrizione': f"Reperibilità {current_date.strftime('%d/%m/%Y')}",
            'Data': current_date.isoformat(), 'OrarioInizio': '00:00', 'OrarioFine': '23:59',
            'PostiTecnico': 1, 'PostiAiutante': 1, 'Tipo': 'Reperibilità'
        }

        if create_shift(new_shift):
            # Aggiunge le prenotazioni per entrambi i membri della coppia
            for surname, role in [(technician1, tech1_role), (technician2, tech2_role)]:
                matricola = find_matricola_by_surname(df_contatti, surname)
                if matricola:
                    new_booking = {
                        'ID_Prenotazione': f"P_{shift_id}_{matricola}", 'ID_Turno': shift_id,
                        'Matricola': matricola, 'RuoloOccupato': role, 'Timestamp': datetime.datetime.now().isoformat()
                    }
                    add_booking(new_booking)
                else:
                    st.warning(f"Attenzione: Cognome '{surname}' non trovato per la data {date_str}.")

        current_date += datetime.timedelta(days=1)

    return changes_made

def manual_override_logic(shift_id, new_tech1_matricola, new_tech2_matricola, admin_matricola):
    """
    Sovrascrive manualmente le prenotazioni per un turno di reperibilità in modo transazionale.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN TRANSACTION")

        # 1. Rimuove le prenotazioni esistenti per questo turno
        delete_bookings_for_shift(shift_id, cursor=cursor)

        # 2. Aggiunge le nuove prenotazioni
        for i, tech_matricola in enumerate([new_tech1_matricola, new_tech2_matricola]):
            user_info = get_user_by_matricola(tech_matricola)
            role = user_info.get('Ruolo', 'Tecnico') if user_info else 'Tecnico'

            new_booking = {
                'ID_Prenotazione': f"P_{shift_id}_{tech_matricola}_{i}",
                'ID_Turno': shift_id,
                'Matricola': tech_matricola,
                'RuoloOccupato': role,
                'Timestamp': datetime.datetime.now().isoformat()
            }
            add_booking(new_booking, cursor=cursor)

        conn.commit()
        log_shift_change(shift_id, "Sovrascrittura Manuale", matricola_eseguito_da=admin_matricola)
        return True
    except sqlite3.Error as e:
        conn.rollback()
        st.error(f"Errore durante la sovrascrittura manuale: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- LOGICA DI BUSINESS PER I TURNI STANDARD ---
def prenota_turno_logic(matricola_utente, turno_id, ruolo_scelto):
    turno_info = get_shift_by_id(turno_id)
    if not turno_info:
        st.error("Turno non trovato."); return False

    prenotazioni_per_turno = get_bookings_for_shift(turno_id)
    tecnici_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Tecnico'])
    aiutanti_prenotati = len(prenotazioni_per_turno[prenotazioni_per_turno['RuoloOccupato'] == 'Aiutante'])

    can_book = False
    if ruolo_scelto == 'Tecnico' and tecnici_prenotati < int(turno_info['PostiTecnico']):
        can_book = True
    elif ruolo_scelto == 'Aiutante' and aiutanti_prenotati < int(turno_info['PostiAiutante']):
        can_book = True

    if not can_book:
        st.error("Tutti i posti per il ruolo selezionato sono esauriti!"); return False

    new_booking_data = {
        'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}",
        'ID_Turno': turno_id,
        'Matricola': str(matricola_utente),
        'RuoloOccupato': ruolo_scelto,
        'Timestamp': datetime.datetime.now().isoformat()
    }

    if add_booking(new_booking_data):
        st.success(f"Turno prenotato come {ruolo_scelto}!");
        log_shift_change(turno_id, "Prenotazione", matricola_subentrante=matricola_utente, matricola_eseguito_da=matricola_utente)
        return True
    else:
        st.error("Errore durante la prenotazione del turno.")
        return False

def cancella_prenotazione_logic(matricola_utente, turno_id):
    if delete_booking(matricola_utente, turno_id):
        log_shift_change(turno_id, "Cancellazione", matricola_originale=matricola_utente, matricola_eseguito_da=matricola_utente)
        st.success("Prenotazione cancellata.")
        return True
    else:
        st.error("Prenotazione non trovata o errore durante la cancellazione.")
        return False

def richiedi_sostituzione_logic(matricola_richiedente, matricola_ricevente, turno_id):
    richiedente_info = get_user_by_matricola(matricola_richiedente)
    if not richiedente_info:
        st.error("Utente richiedente non trovato."); return False

    nome_richiedente = richiedente_info['Nome Cognome']

    new_request_data = {
        'ID_Richiesta': f"S_{int(datetime.datetime.now().timestamp())}",
        'ID_Turno': turno_id,
        'Richiedente_Matricola': str(matricola_richiedente),
        'Ricevente_Matricola': str(matricola_ricevente),
        'Timestamp': datetime.datetime.now().isoformat()
    }

    if add_substitution_request(new_request_data):
        messaggio = f"Hai una nuova richiesta di sostituzione da {nome_richiedente} per il turno {turno_id}."
        crea_notifica(matricola_ricevente, messaggio)
        st.success("Richiesta di sostituzione inviata.")
        st.toast("Richiesta inviata! Il collega riceverà una notifica.")
        return True
    else:
        st.error("Errore durante l'invio della richiesta.")
        return False

def rispondi_sostituzione_logic(id_richiesta, matricola_che_risponde, accettata):
    richiesta = get_substitution_request_by_id(id_richiesta)
    if not richiesta:
        st.error("Richiesta non più valida."); return False

    matricola_richiedente = richiesta['Richiedente_Matricola']
    turno_id = richiesta['ID_Turno']

    user_info = get_user_by_matricola(matricola_che_risponde)
    nome_che_risponde = user_info['Nome Cognome'] if user_info else "Sconosciuto"

    # Always delete the request
    delete_substitution_request(id_richiesta)

    messaggio = f"{nome_che_risponde} ha {'ACCETTATO' if accettata else 'RIFIUTATO'} la tua richiesta di cambio per il turno {turno_id}."
    crea_notifica(matricola_richiedente, messaggio)

    if not accettata:
        st.info("Hai rifiutato la richiesta."); st.toast("Risposta inviata."); return True

    if update_booking_user(turno_id, matricola_richiedente, matricola_che_risponde):
        log_shift_change(turno_id, "Sostituzione Accettata", matricola_originale=matricola_richiedente, matricola_subentrante=matricola_che_risponde, matricola_eseguito_da=matricola_che_risponde)
        st.success("Sostituzione (subentro) effettuata con successo!")
        return True
    else:
        st.error("Errore: la prenotazione originale del richiedente non è stata trovata o errore nell'aggiornamento.")
        # Re-create the substitution request if the booking update fails to avoid data loss
        add_substitution_request(richiesta)
        return False

def pubblica_turno_in_bacheca_logic(matricola_richiedente, turno_id):
    booking_to_publish = get_booking_by_user_and_shift(matricola_richiedente, turno_id)
    if not booking_to_publish:
        st.error("Errore: Prenotazione non trovata."); return False

    # Transaction: Delete booking and add to bacheca
    conn = get_db_connection()
    try:
        with conn:
            # 1. Delete the booking
            delete_sql = "DELETE FROM prenotazioni WHERE ID_Prenotazione = ?"
            conn.execute(delete_sql, (booking_to_publish['ID_Prenotazione'],))

            # 2. Add to bacheca
            new_bacheca_item = {
                'ID_Bacheca': f"B_{int(datetime.datetime.now().timestamp())}",
                'ID_Turno': turno_id,
                'Tecnico_Originale_Matricola': str(matricola_richiedente),
                'Ruolo_Originale': booking_to_publish['RuoloOccupato'],
                'Timestamp_Pubblicazione': datetime.datetime.now().isoformat(),
                'Stato': 'Disponibile',
                'Tecnico_Subentrante_Matricola': None,
                'Timestamp_Assegnazione': None
            }
            add_bacheca_item(new_bacheca_item)

        log_shift_change(turno_id, "Pubblicazione in Bacheca", matricola_originale=matricola_richiedente, matricola_eseguito_da=matricola_richiedente)

        turno_info = get_shift_by_id(turno_id)
        if turno_info:
            messaggio = f"📢 Turno libero: '{turno_info['Descrizione']}' del {pd.to_datetime(turno_info['Data']).strftime('%d/%m')} ({booking_to_publish['RuoloOccupato']})."
            all_users = get_all_users()
            if not all_users.empty:
                for _, user in all_users.iterrows():
                    if str(user['Matricola']) != str(matricola_richiedente):
                        crea_notifica(user['Matricola'], messaggio)

        st.success("Il tuo turno è stato pubblicato in bacheca!")
        st.toast("Tutti i colleghi sono stati notificati.")
        return True

    except sqlite3.Error as e:
        st.error(f"Errore durante la pubblicazione in bacheca: {e}")
        return False

def prendi_turno_da_bacheca_logic(matricola_subentrante, ruolo_utente, id_bacheca):
    bacheca_item = get_bacheca_item_by_id(id_bacheca)
    if not bacheca_item:
        st.error("Questo turno non è più disponibile."); return False
    if bacheca_item['Stato'] != 'Disponibile':
        st.warning("Qualcuno è stato più veloce! Turno già assegnato."); return False

    ruolo_richiesto = bacheca_item['Ruolo_Originale']
    if ruolo_richiesto == 'Tecnico' and ruolo_utente == 'Aiutante':
        st.error(f"Non sei idoneo. È richiesto il ruolo 'Tecnico'."); return False

    turno_id = bacheca_item['ID_Turno']

    # Transaction: Update bacheca and add booking
    update_data = {
        'Stato': 'Assegnato',
        'Tecnico_Subentrante_Matricola': str(matricola_subentrante),
        'Timestamp_Assegnazione': datetime.datetime.now().isoformat()
    }
    new_booking_data = {
        'ID_Prenotazione': f"P_{int(datetime.datetime.now().timestamp())}",
        'ID_Turno': turno_id,
        'Matricola': str(matricola_subentrante),
        'RuoloOccupato': ruolo_richiesto,
        'Timestamp': datetime.datetime.now().isoformat()
    }

    conn = get_db_connection()
    try:
        with conn:
            update_bacheca_item(id_bacheca, update_data)
            add_booking(new_booking_data)

        log_shift_change(turno_id, "Preso da Bacheca", matricola_originale=bacheca_item['Tecnico_Originale_Matricola'], matricola_subentrante=matricola_subentrante, matricola_eseguito_da=matricola_subentrante)

        turno_info = get_shift_by_id(turno_id)
        if turno_info:
            desc_turno = turno_info['Descrizione']
            data_turno = pd.to_datetime(turno_info['Data']).strftime('%d/%m/%Y')
            messaggio_subentrante = f"Hai preso il turno '{desc_turno}' del {data_turno}."
            crea_notifica(matricola_subentrante, messaggio_subentrante)

            user_info = get_user_by_matricola(matricola_subentrante)
            nome_subentrante = user_info['Nome Cognome'] if user_info else "un collega"
            messaggio_originale = f"Il tuo turno '{desc_turno}' del {data_turno} è stato preso da {nome_subentrante}."
            crea_notifica(bacheca_item['Tecnico_Originale_Matricola'], messaggio_originale)

        st.success(f"Ti sei prenotato con successo per il turno come {ruolo_richiesto}!")
        st.balloons()
        return True
    except sqlite3.Error as e:
        st.error(f"Errore durante l'assegnazione del turno: {e}")
        return False