"""
Utility e helper per la logica dei turni.
"""
import datetime

from modules.auth import get_user_by_matricola
from modules.db_manager import add_shift_log


def log_shift_change(
    turno_id,
    azione,
    matricola_originale=None,
    matricola_subentrante=None,
    matricola_eseguito_da=None,
):
    """Registra una modifica a un turno nel database."""

    def get_name(matricola):
        if matricola is None:
            return None
        user = get_user_by_matricola(matricola)
        return user["Nome Cognome"] if user else str(matricola)

    log_data = {
        "ID_Modifica": f"M_{int(datetime.datetime.now().timestamp())}",
        "Timestamp": datetime.datetime.now().isoformat(),
        "ID_Turno": turno_id,
        "Azione": azione,
        "UtenteOriginale": get_name(matricola_originale),
        "UtenteSubentrante": get_name(matricola_subentrante),
        "EseguitoDa": get_name(matricola_eseguito_da),
    }
    add_shift_log(log_data)

def find_matricola_by_surname(df_contatti, surname_to_find):
    """Cerca la matricola di un contatto basandosi sul cognome."""
    if df_contatti.empty or not isinstance(surname_to_find, str):
        return None

    surname_upper = surname_to_find.upper()
    for _, row in df_contatti.iterrows():
        full_name = row.get("Nome Cognome")
        if isinstance(full_name, str) and full_name.strip():
            if full_name.strip().upper().split()[-1] == surname_upper:
                return str(row.get("Matricola"))
    return None
