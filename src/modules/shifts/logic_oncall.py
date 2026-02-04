"""
Logica di business specifica per la reperibilità.
"""
import datetime
import sqlite3

import pandas as pd
import streamlit as st
from src.modules.shifts.logic_utils import find_matricola_by_surname, log_shift_change

from modules.auth import get_user_by_matricola
from modules.db_manager import (
    add_booking,
    create_shift,
    get_all_users,
    get_db_connection,
    get_shifts_by_type,
)
from modules.oncall_logic import get_on_call_pair


def sync_oncall_shifts(start_date, end_date):
    """Sincronizza i turni di reperibilità in modo transazionale."""
    df_turni = get_shifts_by_type("Reperibilità")
    df_contatti = get_all_users()

    if not df_turni.empty:
        df_turni["date_only"] = pd.to_datetime(
            df_turni["Data"], errors="coerce", format="mixed"
        ).dt.date
    else:
        df_turni["date_only"] = pd.Series(dtype="object")

    changes_made = False
    current_date = start_date
    while current_date <= end_date:
        if current_date in df_turni["date_only"].values:
            current_date += datetime.timedelta(days=1)
            continue

        changes_made = True
        pair = get_on_call_pair(current_date)
        (technician1, tech1_role), (technician2, tech2_role) = pair

        date_str = current_date.strftime("%Y-%m-%d")
        shift_id = f"REP_{date_str}"
        new_shift = {
            "ID_Turno": shift_id,
            "Descrizione": f"Reperibilità {current_date.strftime('%d/%m/%Y')}",
            "Data": current_date.isoformat(),
            "OrarioInizio": "00:00",
            "OrarioFine": "23:59",
            "PostiTecnico": 1,
            "PostiAiutante": 1,
            "Tipo": "Reperibilità",
        }

        if create_shift(new_shift):
            for sname, role in [(technician1, tech1_role), (technician2, tech2_role)]:
                matricola = find_matricola_by_surname(df_contatti, sname)
                if matricola:
                    new_booking = {
                        "ID_Prenotazione": f"P_{shift_id}_{matricola}",
                        "ID_Turno": shift_id,
                        "Matricola": matricola,
                        "RuoloOccupato": role,
                        "Timestamp": datetime.datetime.now().isoformat(),
                    }
                    add_booking(new_booking)
                else:
                    st.warning(
                        f"Attenzione: Cognome '{sname}' non trovato "
                        f"per la data {date_str}."
                    )
        current_date += datetime.timedelta(days=1)
    return changes_made

def manual_override_logic(
    shift_id, new_tech1_matricola, new_tech2_matricola, admin_matricola
):
    """Sovrascrive manualmente le prenotazioni per un turno di reperibilità."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION")
        # In questo contesto DatabaseEngine gestisce già l'esecuzione,
        # ma qui usiamo una transazione manuale su connessione diretta per sicurezza.
        cursor = conn.cursor()
        cursor.execute("DELETE FROM prenotazioni WHERE ID_Turno = ?", (shift_id,))

        for i, t_matricola in enumerate([new_tech1_matricola, new_tech2_matricola]):
            user_info = get_user_by_matricola(t_matricola)
            role = user_info.get("Ruolo", "Tecnico") if user_info else "Tecnico"
            sql_ins = "INSERT INTO prenotazioni (ID_Prenotazione, ID_Turno, Matricola, RuoloOccupato, Timestamp) VALUES (?, ?, ?, ?, ?)"
            cursor.execute(sql_ins, (
                f"P_{shift_id}_{t_matricola}_{i}",
                shift_id,
                t_matricola,
                role,
                datetime.datetime.now().isoformat()
            ))

        conn.commit()
        log_shift_change(
            shift_id, "Sovrascrittura Manuale", matricola_eseguito_da=admin_matricola
        )
        return True
    except sqlite3.Error as e:
        conn.rollback()
        st.error(f"Errore durante la sovrascrittura manuale: {e}")
        return False
    finally:
        if conn:
            conn.close()
