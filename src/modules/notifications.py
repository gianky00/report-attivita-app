"""
Modulo per la gestione delle notifiche utente all'interno dell'applicazione.
Le notifiche vengono salvate nel database e possono essere segnate come lette.
"""

import datetime
import sqlite3
from typing import Any

import pandas as pd
from core.logging import get_logger

from modules.db_manager import (
    add_notification,
    get_db_connection,
    get_notifications_for_user,
)

logger = get_logger(__name__)


def leggi_notifiche(utente: str) -> pd.DataFrame:
    """Legge le notifiche di un utente direttamente dal database."""
    try:
        res = get_notifications_for_user(utente)
        if not res:
            return pd.DataFrame(columns=["ID_Notifica", "Timestamp", "Messaggio", "Stato"])
        
        df = pd.DataFrame(res)
        if "Stato" not in df.columns:
            df["Stato"] = "letta" # Fallback di sicurezza
        return df
    except Exception as e:
        logger.error(f"Errore durante il caricamento notifiche per {utente}: {e}")
        return pd.DataFrame(columns=["ID_Notifica", "Timestamp", "Messaggio", "Stato"])


def crea_notifica(destinatario: str, messaggio: str, link_azione: str = "") -> bool:
    """Crea una nuova notifica persistente per un utente."""
    new_id = f"N_{int(datetime.datetime.now().timestamp())}"
    timestamp = datetime.datetime.now().isoformat()

    nuova_notifica = {
        "ID_Notifica": new_id,
        "Timestamp": timestamp,
        "Destinatario": destinatario,
        "Messaggio": messaggio,
        "Stato": "non letta",
        "Link_Azione": link_azione,
    }

    logger.info(f"Creazione notifica per {destinatario}: {messaggio[:50]}...")
    res = add_notification(nuova_notifica)
    return bool(res)


def segna_notifica_letta(id_notifica: str) -> bool:
    """Segna una notifica specifica come 'letta' nel database."""
    conn = get_db_connection()
    try:
        with conn:
            sql = "UPDATE notifiche SET Stato = 'letta' WHERE ID_Notifica = ?"
            cursor = conn.execute(sql, (id_notifica,))
            success = bool(cursor.rowcount > 0)
            if success:
                logger.debug(f"Notifica {id_notifica} segnata come letta.")
            return success
    except sqlite3.Error as e:
        logger.error(f"Errore aggiornamento notifica {id_notifica}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def segna_tutte_lette(matricola: str) -> bool:
    """Segna tutte le notifiche di un utente come lette."""
    conn = get_db_connection()
    try:
        with conn:
            # Nota: nel database la colonna è Destinatario_Matricola per le notifiche
            # ma add_notification usa 'Destinatario' nel dizionario. 
            # Verifichiamo lo schema nel file crea_database.py se necessario.
            # Dallo schema in crea_database.py: Destinatario_Matricola
            sql = "UPDATE notifiche SET Stato = 'letta' WHERE Destinatario_Matricola = ?"
            conn.execute(sql, (matricola,))
            return True
    except sqlite3.Error as e:
        logger.error(f"Errore aggiornamento notifiche per {matricola}: {e}")
        return False
    finally:
        if conn:
            conn.close()