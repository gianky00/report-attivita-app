# ♾️ PROJECT PROFILE: GESTIONALE TECNICI (STREAMLIT APP)

## 🚨 PROJECT OVERVIEW
Questa è un'applicazione **Streamlit** avanzata progettata per la gestione operativa di team tecnici. Il sistema orchestra turni di reperibilità, rendicontazione delle attività (report), gestione delle richieste di materiali e assenze, e integra funzionalità di **Intelligenza Artificiale (Google Gemini)** per la revisione tecnica dei testi e l'analisi della strumentazione (standard ISA S5.1).

### 🛠️ CORE TECH STACK
- **Frontend/App Framework:** Streamlit (Python)
- **Database:** SQLite (schedario.db) + Google Sheets (via gspread)
- **AI Integration:** Google Generative AI (Gemini Flash)
- **Auth & Security:** Bcrypt (hashing), PyOTP (2FA), PyArmor (licensing)
- **Infrastructure:** Docker & Docker Compose, Ngrok (tunneling)
- **Utilities:** Pandas, Matplotlib, python-docx, fpdf2, openpyxl

---

## 🏗️ ARCHITECTURE & STRUCTURE
Il progetto segue una struttura modulare per separare la logica UI dalla business logic:

- `src/app.py`: Punto di ingresso principale dell'applicazione Streamlit.
- `src/modules/`: Contiene la logica di business (es. autenticazione, gestione dati).
- `src/pages/`: Contiene i moduli per le diverse pagine dell'applicazione.
- `src/components/`: Componenti UI riutilizzabili e gestori di form.
- `src/styles/`: Fogli di stile CSS.
- `scripts/`: Directory per script di utility, file batch e creazione database.
    - `crea_database.py`: Script per inizializzare il database SQLite.
    - `rebuild_docker.bat`: Script per ricostruire i container Docker.
- `knowledge_base_docs/`: Archivio storico organizzato per anni utilizzato come base di conoscenza.

---

## 🚀 BUILDING AND RUNNING

### Prerequisiti
1. File `.env` con `NGROK_AUTHTOKEN`.
2. File `.streamlit/secrets.toml` popolato (usa `secrets.toml.example` come base).
3. File `credentials.json` per le API di Google.

### Comandi Key
- **Docker (Consigliato):**
  ```bash
  cd report-attivita-app
  .\scripts\rebuild_docker.bat
  ```
- **Sviluppo Locale:**
  ```bash
  pip install -r requirements.txt
  python scripts/crea_database.py  # Inizializza lo schema SQLite
  streamlit run src/app.py
  ```
- **Utility Scripts:** Gli script in `scripts/` possono essere eseguiti direttamente dalla root del progetto (es. `python scripts/add_admin.py`).

---

## 🧠 DEVELOPMENT CONVENTIONS

1.  **Database Access:** Utilizzare sempre le funzioni in `src/modules/db_manager.py` invece di chiamate SQL dirette nei file UI. La connessione usa `sqlite3.Row` per accesso tramite chiavi.
2.  **Configuration:** Mai hardcodare segreti. Usare `st.secrets` (per Streamlit) o `src/config.py` che legge da `.streamlit/secrets.toml`.
3.  **UI Consistency:** Utilizzare i componenti in `src/components/` e gli stili definiti in `src/styles/style.css` per mantenere un'estetica moderna e uniforme.
4.  **Security:** Ogni modifica alla logica di login o 2FA deve essere loggata tramite `log_access_attempt` (situato in `src/modules/auth.py`).
5.  **AI Prompts:** I prompt per Gemini devono essere strutturati come "Persona" (es. "Sei un Direttore Tecnico...") per garantire output professionali.
6.  **Code Quality & Security Suite:**
    -   `ruff` / `black`: Linting e formattazione rapida e deterministica.
    -   `mypy`: Controllo statico dei tipi.
    -   `refurb`: Modernizzazione e idiomaticità del codice.
    -   `bandit`: Analisi statica della sicurezza (vulnerabilità).
    -   `vulture`: Identificazione di dead code (inutilizzato).
    -   `xenon`: Monitoraggio della complessità ciclotomatica.
    -   `deptry`: Audit delle dipendenze.
    -   `codespell`: Correzione ortografica tecnica.
    -   `interrogate`: Verifica copertura docstring.
    -   `pip-audit`: Scansione vulnerabilità nei pacchetti (CVE).

---

## 💾 DATA PERSISTENCE
- **SQLite (`schedario.db`):** Contiene turni, prenotazioni, log di sistema, report da validare e dati utenti. Situato nella root del progetto.
- **Knowledge Core:** `knowledge_core.json` per la memoria locale del sistema. Situato nella root del progetto.
- **Google Sheets:** Utilizzato come backup o per l'export di risposte ai report.