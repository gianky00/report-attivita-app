import pandas as pd
import datetime
from modules.db_manager import get_notifications_for_user, add_notification

def leggi_notifiche(utente):
    """Legge le notifiche di un utente direttamente dal database."""
    return get_notifications_for_user(utente)

def crea_notifica(destinatario, messaggio, link_azione=""):
    """Crea una nuova notifica nel database."""
    new_id = f"N_{int(datetime.datetime.now().timestamp())}"
    timestamp = datetime.datetime.now().isoformat()

    nuova_notifica = {
        'ID_Notifica': new_id,
        'Timestamp': timestamp,
        'Destinatario': destinatario,
        'Messaggio': messaggio,
        'Stato': 'non letta',
        'Link_Azione': link_azione
    }

    return add_notification(nuova_notifica)

def segna_notifica_letta(id_notifica):
    """Segna una notifica come letta nel database."""
    conn = get_db_connection()
    try:
        with conn:
            sql = "UPDATE notifiche SET Stato = 'letta' WHERE ID_Notifica = ?"
            cursor = conn.execute(sql, (id_notifica,))
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Errore durante l'aggiornamento della notifica: {e}")
        return False
    finally:
        if conn:
            conn.close()
