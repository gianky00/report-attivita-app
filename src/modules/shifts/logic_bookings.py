"""
Logica di business per la prenotazione e cancellazione dei turni standard.
Gestisce i vincoli di disponibilità posti e la registrazione dei cambiamenti.
"""
import datetime
import streamlit as st
from modules.shifts.logic_utils import log_shift_change

from modules.db_manager import (
    add_booking,
    delete_booking,
    get_bookings_for_shift,
    get_shift_by_id,
    check_user_oncall_conflict,
)


def prenota_turno_logic(matricola_utente: str, turno_id: str, ruolo_scelto: str) -> bool:
    """
    Esegue la logica di prenotazione per un turno, verificando la disponibilità residua
    e l'assenza di conflitti con la reperibilità.
    """
    turno_info = get_shift_by_id(turno_id)
    if not turno_info:
        st.error("Turno non trovato.")
        return False

    # 1. Controllo conflitto con Reperibilità
    if check_user_oncall_conflict(matricola_utente, turno_info["Data"]):
        st.error(
            "⚠️ Conflitto rilevato: sei già impegnato in reperibilità per questa data. "
            "Non puoi prenotare turni aggiuntivi."
        )
        return False

    # 2. Controllo disponibilità posti
    prenotazioni_per_turno = get_bookings_for_shift(turno_id)
    tecnici_prenotati = len(
        prenotazioni_per_turno[prenotazioni_per_turno["RuoloOccupato"] == "Tecnico"]
    )
    aiutanti_prenotati = len(
        prenotazioni_per_turno[prenotazioni_per_turno["RuoloOccupato"] == "Aiutante"]
    )

    can_book = False
    if ruolo_scelto == "Tecnico" and tecnici_prenotati < int(turno_info["PostiTecnico"]):
        can_book = True
    elif ruolo_scelto == "Aiutante" and aiutanti_prenotati < int(turno_info["PostiAiutante"]):
        can_book = True

    if not can_book:
        st.error("Tutti i posti per il ruolo selezionato sono esauriti!")
        return False

    new_booking_data = {
        "ID_Prenotazione": f"P_{int(datetime.datetime.now().timestamp())}",
        "ID_Turno": turno_id,
        "Matricola": str(matricola_utente),
        "RuoloOccupato": ruolo_scelto,
        "Timestamp": datetime.datetime.now().isoformat(),
    }

    if add_booking(new_booking_data):
        st.success(f"Turno prenotato come {ruolo_scelto}!")
        log_shift_change(
            turno_id,
            "Prenotazione",
            matricola_subentrante=matricola_utente,
            matricola_eseguito_da=matricola_utente,
        )
        return True
    
    st.error("Errore durante la prenotazione del turno.")
    return False

def cancella_prenotazione_logic(matricola_utente: str, turno_id: str) -> bool:
    """
    Rimuove la prenotazione di un utente per un determinato turno.
    """
    if delete_booking(matricola_utente, turno_id):
        log_shift_change(
            turno_id,
            "Cancellazione",
            matricola_originale=matricola_utente,
            matricola_eseguito_da=matricola_utente,
        )
        st.success("Prenotazione cancellata.")
        return True
    
    st.error("Prenotazione non trovata o errore durante la cancellazione.")
    return False