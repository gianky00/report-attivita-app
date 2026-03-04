"""
Costanti globali dell'applicazione.
Centralizza stringhe, configurazioni fisse e mappature per facilitare la manutenzione.
"""

import datetime

# --- DATABASE ---
DB_NAME = "report-attivita.db"

# Tabelle consentite per la gestione dei report
VALID_REPORT_TABLES = {"report_da_validare", "report_interventi"}
VALID_HISTORY_TABLES = {"relazioni", "report_interventi"}

# Colonne valide per la tabella contatti (Security)
VALID_USER_COLUMNS = {
    "Matricola",
    "Nome Cognome",
    "Nome",
    "Cognome",
    "Ruolo",
    "PasswordHash",
    "2FA_Secret",
    "Stato",
    "Email",
    "Telefono",
}

# --- REPERIBILITÀ (ROTAZIONE) ---
# Data di riferimento: Venerdì 28 Novembre 2025
ANCHOR_DATE = datetime.date(2025, 11, 28)

# Sequenza ciclica di 4 coppie di reperibilità
ON_CALL_ROTATION = [
    (
        ("RICIPUTO", "Tecnico"),
        ("GUARINO", "Aiutante"),
    ),
    (
        ("SPINALI", "Tecnico"),
        ("ALLEGRETTI", "Aiutante"),
    ),
    (
        ("MILLO", "Tecnico"),
        ("GUARINO", "Aiutante"),
    ),
    (
        ("TARASCIO", "Tecnico"),
        ("PARTESANO", "Aiutante"),
    ),
]

# --- UI COLORS ---
COLORS = {
    "PRIMARY": "#3366ff",
    "SUCCESS": "#28a745",
    "WARNING": "#ffc107",
    "DANGER": "#dc3545",
    "INFO": "#17a2b8",
    "TEXT": "#333333",
    "MUTED": "#6c757d",
}

# --- UI & LABELS ---
STATI_ATTIVITA = ["TERMINATA", "SOSPESA", "IN CORSO", "NON SVOLTA"]

# Icone Material (Streamlit)
ICONS = {
    "ATTIVITA": ":material/edit_note:",
    "STORICO": ":material/history:",
    "ARCHIVIO": ":material/archive:",
    "TURNI": ":material/calendar_month:",
    "RICHIESTE": ":material/list_alt:",
    "ADMIN": ":material/settings:",
    "GUIDA": ":material/help:",
    "LOGOUT": ":material/logout:",
    "REPORT": ":material/description:",
    "RELATION": ":material/assignment:",
    "MATERIAL": ":material/inventory_2:",
    "LEAVE": ":material/event_busy:",
    "CHECK": ":material/check_circle:",
    "CANCEL": ":material/cancel:",
    "ADD": ":material/add_circle:",
    "EDIT": ":material/edit:",
    "DELETE": ":material/delete:",
    "SAVE": ":material/save:",
    "INFO": ":material/info:",
    "WARNING": ":material/warning:",
    "ERROR": ":material/error:",
    "BULLETIN": ":material/campaign:",
    "SWAP": ":material/swap_calls:",
    "LIGHTBULB": ":material/lightbulb:",
    "NOTIFICATIONS": ":material/notifications:",
    "IA": ":material/psychology:",
    "USERS": ":material/group:",
    "LOGIN": ":material/login:",
    "SECURITY": ":material/security:",
    "PROGRAMMAZIONE": ":material/list_alt:",
}

# --- CONFIGURAZIONE ---
APP_VERSION = "3.1.0"
VERSION_DATE = "Febbraio 2026"
PATH_KNOWLEDGE_CORE = "knowledge_core.json"
REQUIRED_CONFIG_KEYS = [
    "path_storico_db",
    "path_giornaliera_base",
    "path_attivita_programmate",
]
