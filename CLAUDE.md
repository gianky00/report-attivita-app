# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running and Building

**Docker (recommended for deployment):**
```bash
docker-compose up --build
```
The compose file runs `scripts/crea_database.py` before starting Streamlit, and spins up an Ngrok tunnel service alongside the app. Requires a `.env` file with `NGROK_AUTHTOKEN`.

**Local development:**
```bash
pip install -r requirements.txt
python scripts/crea_database.py        # Creates/updates schedario.db schema
streamlit run src/app.py               # Starts the app on :8501
```

**Utility scripts** (run from project root):
```bash
python scripts/add_admin.py            # Seed an admin user
python scripts/reset_admin_2fa.py      # Reset admin 2FA secret
python scripts/aggiorna_knowledge_base_docs.py  # Rebuild knowledge_core.json from DOCX files
```

## Linting and Formatting

All tools are configured in `pyproject.toml` targeting Python 3.11:
```bash
ruff check src/                        # Lint (E, F, W, I, B, C4, UP; E402 ignored)
ruff format src/                       # Format (equivalent to black)
black src/                             # Formatter
mypy src/                              # Type checking
bandit -r src/                         # Security static analysis (B101 skipped)
interrogate src/                       # Docstring coverage (fail-under=80; scripts/ excluded)
vulture src/                           # Dead code detection
refurb src/                            # Code modernization
xenon --max-a 10 src/                  # Cyclomatic complexity
deptry .                               # Dependency audit
codespell src/                         # Spelling check
pip-audit                              # Package CVE scan
```

## Prerequisites

The app requires files that are **not** in the repo and must be set up manually before first run:
- `.streamlit/secrets.toml` — all runtime paths and secrets (read by `src/config.py` at import time; missing keys cause `sys.exit(1)`). Required keys: `path_storico_db`, `path_gestionale`, `path_giornaliera_base`, `path_attivita_programmate`. Optional keys: `nome_foglio_risposte`, `email_destinatario`, `email_cc`, `GEMINI_API_KEY`.
- `credentials.json` — Google service-account JSON for Sheets/Drive OAuth (used by `autorizza_google()` in `app.py`).
- `.env` — `NGROK_AUTHTOKEN` for the tunnel service.

## Architecture

**Entry point:** `src/app.py` is a single-file Streamlit app. It handles the entire login/2FA flow at module scope (lines 703–882), then calls `main_app()` for the authenticated UI. Navigation is session-state driven (`st.session_state.main_tab`), not multi-page Streamlit routing.

**Layer structure:**
- `src/pages/` — Each file exports a single `render_*` function called by `main_app()`. They are NOT Streamlit multi-page files; they are imported as regular modules.
- `src/components/` — Reusable UI fragments: `render_debriefing_ui` (activity report form with optional AI correction), `render_edit_shift_form`, `render_notification_center`, `disegna_sezione_attivita`.
- `src/modules/` — All business logic and data access. No Streamlit rendering here (with a few `st.error` fallback prints).

**Database access:** All SQLite queries must go through `src/modules/db_manager.py`. It provides `get_db_connection()` (returns `sqlite3.Row`-backed connections) and typed functions per entity. The database file is `schedario.db` in the project root. Schema is defined and created idempotently by `scripts/crea_database.py`. Never open connections to `schedario.db` directly outside `db_manager.py` and `auth.py`.

**Configuration:** `src/config.py` reads `.streamlit/secrets.toml` at import time using the `toml` library and exports path constants and email settings. It also creates two `threading.Lock` objects (`EXCEL_LOCK`, `OUTLOOK_LOCK`) used when accessing shared Windows resources (Excel files, Outlook).

**Session management:** `src/modules/session_manager.py` persists sessions as JSON files in a `sessions/` directory, keyed by a UUID token passed via `?session_token=` query param. Session duration is 1 year.

**Activity data flow:** Daily activities are sourced from Excel `.xlsm` files on disk (path from `secrets.toml`). `data_manager.py:trova_attivita()` parses these using openpyxl (via pandas), matches technician names with fuzzy logic (`_match_partial_name`), and returns structured task dicts. Completed reports are written to the `report_da_validare` SQLite table, then moved to `report_interventi` after admin validation.

**AI integration:** Google Gemini Flash is used in two places: (1) `revisiona_relazione_con_ia()` in `app.py` revises on-call reports using ISA S5.1 instrumentation analysis context built by `modules/instrumentation_logic.py`, and (2) the debriefing flow in `components/form_handlers.py`. Prompts use a "persona" pattern (e.g., "Sei un Direttore Tecnico..."). The API key comes from `st.secrets["GEMINI_API_KEY"]`.

**Shift/on-call system:** `modules/shift_management.py` syncs on-call shifts for a ±180-day window on every authenticated page load. `modules/oncall_logic.py` computes the next on-call week for sidebar display. Shifts live in the `turni` table; bookings in `prenotazioni`; substitution requests in `sostituzioni`.

**Email:** `modules/email_sender.py` sends via Windows Outlook COM (`win32com`) in a background thread, gated by `OUTLOOK_LOCK`. This means email sending only works on a Windows machine with Outlook installed — it will silently no-op on Linux/Docker unless Outlook is available.

**License check:** `modules/license_manager.py:check_pyarmor_license()` runs at the top of `app.py` before anything else. It guards the application with PyArmor.

## Key Conventions

- **All DB access through `db_manager.py`** — do not write raw SQL in page or component files.
- **Auth changes must be logged** — use `auth.py:log_access_attempt()` for any login/2FA/password event.
- **Secrets via `st.secrets`** — never hardcode API keys or paths. Use `config.py` exports for paths, `st.secrets` for runtime credentials.
- **UI consistency** — use components from `src/components/` and styles from `src/styles/style.css`.
- **Windows-only features** — `pywin32` (Excel COM, Outlook) is conditionally imported; code paths using it must guard with `if win32 is not None`.
- **Streamlit caching** — `data_manager._carica_giornaliera_mese` is cached with `@st.cache_data(ttl=3600)`. Call `.clear()` on it after writes that should invalidate the Excel cache. `carica_knowledge_core` is also cached — clear `st.cache_data` after updating `knowledge_core.json`.
