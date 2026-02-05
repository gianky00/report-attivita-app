"""
Logica di business per la bacheca scambi e le richieste di sostituzione diretta.
Gestisce il ciclo di vita degli annunci e le transazioni di subentro nei turni.
"""
import datetime
import sqlite3
from typing import Optional

import pandas as pd
import streamlit as st
from modules.shifts.logic_utils import log_shift_change

from modules.auth import get_user_by_matricola
from modules.db_manager import (
    add_bacheca_item,
    add_booking,
    add_substitution_request,
    delete_substitution_request,
    get_all_users,
    get_bacheca_item_by_id,
    get_booking_by_user_and_shift,
    get_db_connection,
    get_shift_by_id,
    get_substitution_request_by_id,
    update_bacheca_item,
    update_booking_user,
)
from modules.notifications import crea_notifica


def richiedi_sostituzione_logic(matricola_richiedente: str, matricola_ricevente: str, turno_id: str) -> bool:
    """Invia una richiesta di sostituzione diretta a un collega specifico."""
    richiedente_info = get_user_by_matricola(matricola_richiedente)
    if not richiedente_info:
        st.error("Utente richiedente non trovato.")
        return False

    nome_richiedente = richiedente_info["Nome Cognome"]
    new_request_data = {
        "ID_Richiesta": f"S_{int(datetime.datetime.now().timestamp())}",
        "ID_Turno": turno_id,
        "Richiedente_Matricola": str(matricola_richiedente),
        "Ricevente_Matricola": str(matricola_ricevente),
        "Timestamp": datetime.datetime.now().isoformat(),
    }

    if add_substitution_request(new_request_data):
        msg = (
            f"Hai una nuova richiesta di sostituzione da "
            f"{nome_richiedente} per il turno {turno_id}."
        )
        crea_notifica(matricola_ricevente, msg)
        st.success("Richiesta di sostituzione inviata.")
        st.toast("Richiesta inviata! Il collega riceverà una notifica.")
        return True
    
    st.error("Errore durante l'invio della richiesta.")
    return False

def rispondi_sostituzione_logic(id_richiesta: str, matricola_che_risponde: str, accettata: bool) -> bool:
    """Gestisce l'accettazione o il rifiuto di una richiesta di sostituzione ricevuta."""
    richiesta = get_substitution_request_by_id(id_richiesta)
    if not richiesta:
        st.error("Richiesta non più valida.")
        return False

    matricola_richiedente = richiesta["Richiedente_Matricola"]
    turno_id = richiesta["ID_Turno"]

    user_info = get_user_by_matricola(matricola_che_risponde)
    nome_che_risponde = user_info["Nome Cognome"] if user_info else "Sconosciuto"

    delete_substitution_request(id_richiesta)

    esito = "ACCETTATO" if accettata else "RIFIUTATO"
    msg = (
        f"{nome_che_risponde} ha {esito} la tua richiesta di cambio "
        f"per il turno {turno_id}."
    )
    crea_notifica(matricola_richiedente, msg)

    if not accettata:
        st.info("Hai rifiutato la richiesta.")
        st.toast("Risposta inviata.")
        return True

    if update_booking_user(turno_id, matricola_richiedente, matricola_che_risponde):
        log_shift_change(
            turno_id,
            "Sostituzione Accettata",
            matricola_originale=matricola_richiedente,
            matricola_subentrante=matricola_che_risponde,
            matricola_eseguito_da=matricola_che_risponde,
        )
        st.success("Sostituzione (subentro) effettuata con successo!")
        return True
    
    st.error("Errore di aggiornamento.")
    add_substitution_request(richiesta)
    return False

def pubblica_turno_in_bacheca_logic(matricola_richiedente: str, turno_id: str) -> bool:
    """Pubblica un turno prenotato in bacheca per renderlo disponibile a chiunque."""
    booking_to_publish = get_booking_by_user_and_shift(matricola_richiedente, turno_id)
    if not booking_to_publish:
        st.error("Errore: Prenotazione non trovata.")
        return False

    try:
        conn = get_db_connection()
        with conn:
            delete_sql = "DELETE FROM prenotazioni WHERE ID_Prenotazione = ?"
            conn.execute(delete_sql, (booking_to_publish["ID_Prenotazione"],))

            new_bacheca_item = {
                "ID_Bacheca": f"B_{int(datetime.datetime.now().timestamp())}",
                "ID_Turno": turno_id,
                "Tecnico_Originale_Matricola": str(matricola_richiedente),
                "Ruolo_Originale": booking_to_publish["RuoloOccupato"],
                "Timestamp_Pubblicazione": datetime.datetime.now().isoformat(),
                "Stato": "Disponibile",
                "Tecnico_Subentrante_Matricola": None,
                "Timestamp_Assegnazione": None,
            }
            add_bacheca_item(new_bacheca_item)

        log_shift_change(
            turno_id,
            "Pubblicazione in Bacheca",
            matricola_originale=matricola_richiedente,
            matricola_eseguito_da=matricola_richiedente,
        )

        turno_info = get_shift_by_id(turno_id)
        if turno_info:
            data_str = pd.to_datetime(turno_info["Data"]).strftime("%d/%m")
            msg = f"📢 Turno libero: '{turno_info['Descrizione']}' del {data_str} ({booking_to_publish['RuoloOccupato']})."
            all_users = get_all_users()
            for _, user in all_users.iterrows():
                if str(user["Matricola"]) != str(matricola_richiedente):
                    crea_notifica(user["Matricola"], msg)

        st.success("Turno pubblicato in bacheca!")
        return True
    except sqlite3.Error as e:
        st.error(f"Errore: {e}")
        return False

def prendi_turno_da_bacheca_logic(matricola_subentrante: str, ruolo_utente: str, id_bacheca: str) -> bool:
    """Assegna un turno disponibile in bacheca all'utente richiedente."""
    bacheca_item = get_bacheca_item_by_id(id_bacheca)
    if not bacheca_item or bacheca_item["Stato"] != "Disponibile":
        st.error("Turno non disponibile."); return False

    ruolo_richiesto = bacheca_item["Ruolo_Originale"]
    if ruolo_richiesto == "Tecnico" and ruolo_utente == "Aiutante":
        st.error("Richiesto ruolo 'Tecnico'."); return False

    turno_id = bacheca_item["ID_Turno"]
    update_data = {
        "Stato": "Assegnato",
        "Tecnico_Subentrante_Matricola": str(matricola_subentrante),
        "Timestamp_Assegnazione": datetime.datetime.now().isoformat(),
    }
    new_booking = {
        "ID_Prenotazione": f"P_{int(datetime.datetime.now().timestamp())}",
        "ID_Turno": turno_id,
        "Matricola": str(matricola_subentrante),
        "RuoloOccupato": ruolo_richiesto,
        "Timestamp": datetime.datetime.now().isoformat(),
    }

    conn = get_db_connection()
    try:
        with conn:
            update_bacheca_item(id_bacheca, update_data)
            add_booking(new_booking)

        log_shift_change(
            turno_id, "Preso da Bacheca",
            matricola_originale=bacheca_item["Tecnico_Originale_Matricola"],
            matricola_subentrante=matricola_subentrante,
            matricola_eseguito_da=matricola_subentrante,
        )

        st.success(f"Ti sei prenotato come {ruolo_richiesto}!")
        st.balloons()
        return True
    except sqlite3.Error as e:
        st.error(f"Errore: {e}"); return False