"""
Logica per l'invio e il salvataggio dei report tecnici.
"""

import datetime
import re
import sqlite3
import uuid

import streamlit as st

from core.database import DatabaseEngine


def scrivi_o_aggiorna_risposta(
    dati_da_scrivere: dict[str, str],
    matricola: str,
    data_riferimento: datetime.date,
    id_report: str | None = None,
) -> bool:
    """Scrive un report nel DB (o lo aggiorna se id_report è fornito) e invia notifica email."""
    timestamp_compilazione = datetime.datetime.now()
    from modules.database.db_reports import insert_report

    conn = None
    try:
        conn = DatabaseEngine.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT "Nome Cognome" FROM contatti WHERE Matricola = ?', (matricola,))
        user_result = cursor.fetchone()
        if not user_result:
            st.error(f"Utente {matricola} non trovato.")
            return False
        nome_completo = user_result[0]

        pdl_match = re.search(r"PdL (\d{6}/[CS]|\d{6})", dati_da_scrivere["descrizione"])
        pdl = pdl_match.group(1) if pdl_match else "N/D"

        report_data = {
            "id_report": id_report if id_report else str(uuid.uuid4()),
            "pdl": pdl,
            "descrizione_attivita": dati_da_scrivere["descrizione"],
            "matricola_tecnico": matricola,
            "nome_tecnico": nome_completo,
            "team": dati_da_scrivere.get("team_completo", ""),
            "stato_attivita": dati_da_scrivere["stato"],
            "testo_report": dati_da_scrivere["report"],
            "data_compilazione": timestamp_compilazione.isoformat(),
            "data_riferimento_attivita": data_riferimento.isoformat(),
        }

        # Utilizziamo la funzione centralizzata in db_reports per l'inserimento/update
        # che gestisce anche l'aggiornamento della tabella di programmazione PDL
        if insert_report(report_data, "report_da_validare"):
            _send_validation_email(
                nome_completo, data_riferimento, timestamp_compilazione, dati_da_scrivere
            )
            st.cache_data.clear()
            return True
        return False
    except (sqlite3.Error, Exception) as e:
        st.error(f"Errore salvataggio report: {e}")
        return False
    finally:
        if "conn" in locals() and conn:
            conn.close()


def _send_validation_email(
    nome: str, data_rif: datetime.date, ts: datetime.datetime, dati: dict[str, str]
) -> None:
    """Sottoprocesso per l'invio dell'email di validazione."""
    from modules.email_sender import invia_email_con_outlook_async

    titolo = f"Nuovo Report da Validare da: {nome}"
    html = f"""
    <html><body style="font-family: Calibri, sans-serif;">
    <h2>Nuovo Report da Validare</h2>
    <table>
        <tr><th>Data Rif.</th><td>{data_rif.strftime("%d/%m/%Y")}</td></tr>
        <tr><th>Tecnico</th><td>{nome}</td></tr>
        <tr><th>Attività</th><td>{dati["descrizione"]}</td></tr>
        <tr><th>Stato</th><td><b>{dati["stato"]}</b></td></tr>
    </table>
    <hr><p>{dati["report"].replace(chr(10), "<br>")}</p>
    </body></html>
    """
    invia_email_con_outlook_async(titolo, html)
