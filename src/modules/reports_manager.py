"""
Logica per l'invio e il salvataggio dei report tecnici.
"""
import datetime
import re
import sqlite3
import uuid

import streamlit as st

from modules.db_manager import get_db_connection


def scrivi_o_aggiorna_risposta(
    dati_da_scrivere: dict, matricola: str, data_riferimento: datetime.date
) -> bool:
    """Scrive un report nel DB e invia notifica email."""
    timestamp_compilazione = datetime.datetime.now()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT "Nome Cognome" FROM contatti WHERE Matricola = ?', (matricola,))
        user_result = cursor.fetchone()
        if not user_result:
            st.error(f"Utente {matricola} non trovato."); return False
        nome_completo = user_result[0]

        pdl_match = re.search(r"PdL (\d{6}/[CS]|\d{6})", str(dati_da_scrivere["descrizione"]))
        pdl = pdl_match.group(1) if pdl_match else "N/D"

        report_data = {
            "id_report": str(uuid.uuid4()),
            "pdl": pdl,
            "descrizione_attivita": dati_da_scrivere["descrizione"],
            "matricola_tecnico": matricola,
            "nome_tecnico": nome_completo,
            "stato_attivita": dati_da_scrivere["stato"],
            "testo_report": dati_da_scrivere["report"],
            "data_compilazione": timestamp_compilazione.isoformat(),
            "data_riferimento_attivita": data_riferimento.isoformat(),
        }

        with conn:
            cols = ", ".join(f'"{k}"' for k in report_data.keys())
            placeholders = ", ".join("?" for _ in report_data)
            cursor.execute(f"INSERT INTO report_da_validare ({cols}) VALUES ({placeholders})", list(report_data.values()))

        _send_validation_email(nome_completo, data_riferimento, timestamp_compilazione, dati_da_scrivere)
        st.cache_data.clear()
        return True
    except (sqlite3.Error, Exception) as e:
        st.error(f"Errore salvataggio report: {e}"); return False
    finally:
        if conn: conn.close()

def _send_validation_email(nome, data_rif, ts, dati):
    """Sottoprocesso per l'invio dell'email di validazione."""
    from modules.email_sender import invia_email_con_outlook_async
    titolo = f"Nuovo Report da Validare da: {nome}"
    html = f"""
    <html><body style="font-family: Calibri, sans-serif;">
    <h2>Nuovo Report da Validare</h2>
    <table>
        <tr><th>Data Rif.</th><td>{data_rif.strftime("%d/%m/%Y")}</td></tr>
        <tr><th>Tecnico</th><td>{nome}</td></tr>
        <tr><th>Attività</th><td>{dati['descrizione']}</td></tr>
        <tr><th>Stato</th><td><b>{dati['stato']}</b></td></tr>
    </table>
    <hr><p>{dati['report'].replace(chr(10), '<br>')}</p>
    </body></html>
    """
    invia_email_con_outlook_async(titolo, html)
