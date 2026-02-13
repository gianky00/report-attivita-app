# 1/2 — Installazione Stack Qualità Codice Python

> **Step 1 di 2** — Installa tutti i tool di code quality.
> Dopo questo prompt, esegui `2_QUALITY_STACK_CONFIG.md` per configurarli.
>
> Prompt universale, replicabile su qualsiasi progetto Python.
> Compatibile con qualsiasi LLM che abbia accesso al filesystem e al terminale.

---

## Prompt

```
Ruolo: Agisci come un Python DevOps Engineer specializzato in Code Quality Tooling.

Contesto: Devo installare da zero l'intero stack di qualità del codice su un progetto Python.
Lo stack è composto da tool con ruoli NON sovrapposti. Ogni tool ha uno scopo unico.

Obiettivo: Installa tutti i tool, verifica che funzionino, e prepara il progetto
per la successiva fase di configurazione.

IMPORTANTE: Questo prompt è GENERICO. Adattati al progetto che trovi.

=============================================================================
MAPPA DEI TOOL — Ruolo unico di ciascuno
=============================================================================

Tool            │ Categoria       │ Ruolo
────────────────┼─────────────────┼───────────────────────────────────────────
ruff            │ Linter+Formatter│ Sostituisce Black, Isort, Flake8, pyupgrade
mypy            │ Type Checker    │ Analisi statica dei tipi (strict mode)
bandit          │ Security        │ Vulnerabilità di sicurezza nel codice
deptry          │ Dependencies    │ Import mancanti, non usati, transitivi
codespell       │ Spelling        │ Typo nel codice e nei commenti
refurb          │ Modernization   │ Suggerisce sintassi Python più moderna
vulture         │ Dead Code       │ Rileva codice morto (funzioni/variabili mai usate)
xenon           │ Complexity      │ Complessità ciclomatica (grading A/B/C/D/F)
interrogate     │ Docstrings      │ Coverage delle docstring
pre-commit      │ Git Hooks       │ Pipeline automatica ad ogni commit
pytest          │ Testing         │ Framework di test
pytest-cov      │ Coverage        │ Report copertura codice

Tool VIETATI (ridondanti — sostituiti da Ruff):
  ✗ black        → ruff format
  ✗ isort        → ruff (regola I)
  ✗ flake8       → ruff (regole E/W/F)
  ✗ pyupgrade    → ruff (regola UP)
  ✗ autopep8     → ruff format

=============================================================================
FASE 0 — ANALISI DEL PROGETTO
=============================================================================

Prima di installare qualsiasi cosa, analizza il progetto:

1. LEGGI pyproject.toml (o setup.py / setup.cfg):
   - Identifica `requires-python` → determina la versione Python target
   - Identifica `dependencies` → lista dipendenze di produzione
   - Identifica `[project.optional-dependencies] dev` → tool già installati
   - Identifica configurazioni tool già presenti ([tool.ruff], [tool.mypy], ecc.)

2. SE NON esiste pyproject.toml:
   - Cerca setup.py, setup.cfg, requirements.txt
   - Se nessuno esiste, CHIEDERE all'utente la versione Python target
   - Creare pyproject.toml minimo con [build-system] e [project]

3. VERIFICA versione Python attiva:
   ```bash
   python --version
   ```
   - Se diversa da `requires-python`, AVVISA l'utente

4. VERIFICA se esiste un virtual environment:
   ```bash
   # Linux/macOS
   which python
   # Windows
   where python
   ```

   SE il progetto NON ha un virtual environment attivo:
   a. Crea il venv nella root del progetto:
      ```bash
      python -m venv .venv
      ```
   b. Attiva il venv:
      ```bash
      # Linux/macOS
      source .venv/bin/activate

      # Windows (cmd)
      .venv\Scripts\activate.bat

      # Windows (PowerShell)
      .venv\Scripts\Activate.ps1
      ```
   c. Verifica che il venv sia attivo:
      ```bash
      # Deve puntare alla directory .venv del progetto
      # Linux/macOS
      which python
      # Windows
      where python
      ```
   d. Aggiorna pip nel venv:
      ```bash
      python -m pip install --upgrade pip
      ```
   e. Se esiste pyproject.toml con dependencies, installa il progetto:
      ```bash
      pip install -e ".[dev]"
      ```
      Questo installa sia le dipendenze di produzione che quelle dev.
      Se la sezione [dev] non esiste ancora, installa solo le dipendenze base:
      ```bash
      pip install -e .
      ```

   SE il progetto HA GIÀ un venv (.venv/ o venv/ presente):
   - Verifica che sia attivo (il path di `python` punta al venv)
   - Se non è attivo, attivalo con i comandi sopra
   - NON creare un nuovo venv

   VERIFICA che .gitignore ignori il venv:
   ```bash
   grep -E "^\.venv/?$|^venv/?$" .gitignore
   ```
   Se mancante, aggiungi `.venv/` a .gitignore.

5. CONTROLLA tool ridondanti già installati:
   ```bash
   pip list 2>/dev/null | grep -iE "^(black|isort|flake8|autopep8|pyupgrade) "
   ```
   - Se presenti: segnala che saranno sostituiti da Ruff

=============================================================================
FASE 1 — INSTALLAZIONE TOOL PRINCIPALI
=============================================================================

Installa TUTTI i tool in un singolo comando pip:

```bash
pip install \
    ruff \
    mypy \
    bandit \
    deptry \
    codespell \
    refurb \
    vulture \
    xenon \
    interrogate \
    pre-commit \
    pytest \
    pytest-cov \
    pytest-mock \
    pyfakefs
```

Su Windows (singola riga):
```cmd
pip install ruff mypy bandit deptry codespell refurb vulture xenon interrogate pre-commit pytest pytest-cov pytest-mock pyfakefs
```

REGOLE CRITICHE:
- Usa SEMPRE `pip install` senza versioni fissate → prendi le ultime stabili
- NON installare black, isort, flake8, autopep8, pyupgrade → Ruff li sostituisce
- Se un tool è già installato con versione recente, pip lo salterà automaticamente

=============================================================================
FASE 2 — INSTALLAZIONE TYPE STUBS (per Mypy)
=============================================================================

Mypy necessita di type stubs per le librerie terze. Senza stubs, mypy non può
verificare i tipi delle chiamate a librerie esterne.

PROCEDURA per ogni dipendenza di produzione:

1. Per ogni libreria in `dependencies` di pyproject.toml:

   a. Controlla se ha stubs built-in (py.typed marker):
      ```bash
      python -c "import <modulo>; import pathlib; p=pathlib.Path(<modulo>.__file__).parent; print((p/'py.typed').exists())"
      ```
      Se True → NON serve nulla, ha stubs integrati

   b. Se NON ha py.typed, cerca stubs esterni:
      ```bash
      pip index versions types-<nome>  2>/dev/null  # Pattern: types-X
      pip index versions <nome>-stubs  2>/dev/null  # Pattern: X-stubs
      ```

   c. Se esistono stubs → installali:
      ```bash
      pip install types-<nome>    # Esempio: types-requests
      pip install <nome>-stubs    # Esempio: pandas-stubs
      ```

   d. Se NON esistono stubs → la libreria necessiterà un override mypy
      (configurato nella fase successiva con 2_QUALITY_STACK_CONFIG.md)

2. STUBS COMUNI — Mappa di riferimento rapido:

   Libreria           │ Stub package        │ Note
   ────────────────────┼─────────────────────┼───────────────────
   requests           │ types-requests      │
   pandas             │ pandas-stubs        │
   SQLAlchemy         │ sqlalchemy[mypy]    │ Plugin integrato
   Pillow             │ types-Pillow        │
   beautifulsoup4     │ types-beautifulsoup4│
   PyYAML             │ types-PyYAML        │
   python-dateutil    │ types-python-dateutil│
   ────────────────────┼─────────────────────┼───────────────────
   customtkinter      │ (nessuno)           │ Override mypy
   garminconnect      │ (nessuno)           │ Override mypy
   google-generativeai│ (nessuno)           │ Override mypy
   fpdf2              │ (nessuno)           │ Override mypy
   seaborn            │ (nessuno)           │ Override mypy
   matplotlib         │ (built-in)          │ Ha py.typed
   numpy              │ (built-in)          │ Ha py.typed

   NOTA: Questa tabella è un riferimento. Verifica SEMPRE la disponibilità
   reale degli stubs perché nuovi pacchetti vengono pubblicati continuamente.

=============================================================================
FASE 3 — RIMOZIONE TOOL RIDONDANTI
=============================================================================

Se nella Fase 0 hai trovato tool ridondanti, rimuovili ORA:

```bash
pip uninstall -y black isort flake8 autopep8 pyupgrade 2>/dev/null
```

Rimuovili anche da:
- pyproject.toml → [project.optional-dependencies] dev
- requirements-dev.txt (se esiste)
- .pre-commit-config.yaml → rimuovi hook di black, isort, flake8

=============================================================================
FASE 4 — AGGIORNAMENTO pyproject.toml (dev dependencies)
=============================================================================

Assicurati che [project.optional-dependencies] dev contenga TUTTI i tool.
Se la sezione non esiste, creala.

```toml
[project.optional-dependencies]
dev = [
    # === Linting & Formatting ===
    "ruff",
    # === Type Checking ===
    "mypy",
    # === Type Stubs (aggiungi solo quelli necessari per il progetto) ===
    # "pandas-stubs",
    # "types-requests",
    # === Security ===
    "bandit",
    # === Dependencies ===
    "deptry",
    # === Spelling ===
    "codespell",
    # === Modernization ===
    "refurb",
    # === Dead Code ===
    "vulture",
    # === Complexity ===
    "xenon",
    # === Docstrings ===
    "interrogate",
    # === Git Hooks ===
    "pre-commit",
    # === Testing ===
    "pytest",
    "pytest-cov",
    "pytest-mock",
]
```

REGOLE:
- Mantieni le dipendenze ordinate per categoria
- Ogni stubs package va nella sezione Type Stubs
- NON includere black, isort, flake8 o loro plugin
- Aggiungi commenti per ogni categoria

=============================================================================
FASE 5 — VERIFICA INSTALLAZIONE
=============================================================================

Esegui TUTTI questi comandi e verifica che ogni tool risponda correttamente.
Se un comando fallisce, il tool non è installato — ripeti pip install.

```bash
# 1. Ruff (linter + formatter)
ruff version
# Output atteso: ruff X.Y.Z

# 2. Mypy (type checker)
mypy --version
# Output atteso: mypy X.Y.Z (compiled: yes)

# 3. Bandit (security)
bandit --version
# Output atteso: bandit X.Y.Z

# 4. Deptry (dependency hygiene)
python -m deptry --version
# Output atteso: deptry X.Y.Z

# 5. Codespell (spelling)
codespell --version
# Output atteso: X.Y.Z

# 6. Refurb (modernization)
refurb --version
# Output atteso: refurb vX.Y.Z

# 7. Vulture (dead code)
vulture --version
# Output atteso: vulture X.Y.Z

# 8. Xenon (complexity)
xenon --version
# Output atteso: X.Y.Z

# 9. Interrogate (docstrings)
interrogate --version
# Output atteso: interrogate X.Y.Z

# 10. Pre-commit (git hooks)
pre-commit --version
# Output atteso: pre-commit X.Y.Z

# 11. Pytest (testing)
pytest --version
# Output atteso: pytest X.Y.Z
```

RACCOLTA VERSIONI — Esegui questo one-liner per un riepilogo:

Linux/macOS:
```bash
echo "=== Quality Stack Versions ===" && \
ruff version && \
mypy --version && \
bandit --version && \
python -m deptry --version && \
codespell --version && \
refurb --version && \
vulture --version && \
xenon --version && \
interrogate --version && \
pre-commit --version && \
pytest --version
```

Windows (cmd):
```cmd
echo === Quality Stack Versions === & ruff version & mypy --version & bandit --version & python -m deptry --version & codespell --version & refurb --version & vulture --version & xenon --version & interrogate --version & pre-commit --version & pytest --version
```

=============================================================================
FASE 6 — INIZIALIZZAZIONE PRE-COMMIT
=============================================================================

Se il progetto è un repository Git:

```bash
# Installa gli hook nel repository
pre-commit install

# Verifica che il file .pre-commit-config.yaml esista
# Se NON esiste, creane uno minimale (la configurazione completa
# viene fatta con 2_QUALITY_STACK_CONFIG.md)
```

Se .pre-commit-config.yaml NON esiste, crea un file base:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

Se .pre-commit-config.yaml ESISTE GIÀ:
- NON sovrascriverlo
- Esegui `pre-commit install` per attivare gli hook
- Esegui `pre-commit autoupdate` per aggiornare i rev

=============================================================================
FASE 7 — SMOKE TEST (Verifica Rapida)
=============================================================================

Esegui ogni tool sulla directory sorgente del progetto per verificare che
non ci siano errori di configurazione o di import. NON correggere nulla,
solo verificare che i tool si avviano senza crash.

Identifica la directory sorgente (tipicamente src/, oppure il nome del package):

```bash
# Ruff: deve avviarsi senza errori interni
ruff check <src_dir>/ --statistics 2>&1 | head -20

# Ruff format: check mode (non modifica nulla)
ruff format --check <src_dir>/ 2>&1 | head -5

# Mypy: deve avviarsi (gli errori di tipo sono ATTESI, non sono un problema)
python -m mypy <src_dir>/ 2>&1 | tail -5

# Bandit: deve avviarsi
bandit -r <src_dir>/ -q 2>&1 | tail -5

# Deptry: deve avviarsi
python -m deptry <src_dir>/ 2>&1 | tail -5

# Vulture: deve avviarsi (i falsi positivi sono normali)
vulture <src_dir>/ 2>&1 | head -10

# Xenon: complessità (A=ottimo, F=critico)
xenon <src_dir>/ -b B -m A -a A 2>&1 | tail -5

# Interrogate: coverage docstring
interrogate <src_dir>/ -v 2>&1 | tail -10

# Codespell: deve avviarsi
codespell <src_dir>/ 2>&1 | head -10

# Refurb: deve avviarsi
refurb <src_dir>/ 2>&1 | head -10
```

CRITERI DI SUCCESSO dello smoke test:
- ✅ Ogni tool si avvia senza crash/ImportError/ModuleNotFoundError
- ✅ Ogni tool produce output (errori di lint/tipo sono OK, crash no)
- ❌ Se un tool va in crash → problema di installazione, ripeti pip install
- ❌ Se mypy lamenta missing stubs → tornare alla Fase 2

=============================================================================
FASE 8 — REPORT FINALE
=============================================================================

Al termine, produci un report con questo formato:

```
╔══════════════════════════════════════════════════════════════╗
║              QUALITY STACK — INSTALLATION REPORT            ║
╠══════════════════════════════════════════════════════════════╣
║ Python version:       3.XX.X                                ║
║ Virtual environment:  ✅ / ⚠️ globale                        ║
║ OS:                   Linux / macOS / Windows                ║
╠══════════════════════════════════════════════════════════════╣
║ TOOL              │ VERSIONE    │ STATO    │ NOTE            ║
║ ──────────────────┼─────────────┼──────────┼──────────────── ║
║ ruff              │ X.Y.Z       │ ✅       │                 ║
║ mypy              │ X.Y.Z       │ ✅       │                 ║
║ bandit            │ X.Y.Z       │ ✅       │                 ║
║ deptry            │ X.Y.Z       │ ✅       │                 ║
║ codespell         │ X.Y.Z       │ ✅       │                 ║
║ refurb            │ X.Y.Z       │ ✅       │                 ║
║ vulture           │ X.Y.Z       │ ✅       │                 ║
║ xenon             │ X.Y.Z       │ ✅       │                 ║
║ interrogate       │ X.Y.Z       │ ✅       │                 ║
║ pre-commit        │ X.Y.Z       │ ✅       │                 ║
║ pytest            │ X.Y.Z       │ ✅       │                 ║
║ pytest-cov        │ X.Y.Z       │ ✅       │                 ║
╠══════════════════════════════════════════════════════════════╣
║ TYPE STUBS INSTALLATI:                                      ║
║   - pandas-stubs, types-requests, ...                       ║
║ LIBRERIE SENZA STUBS (necessitano override mypy):           ║
║   - customtkinter, garminconnect, ...                       ║
╠══════════════════════════════════════════════════════════════╣
║ TOOL RIMOSSI (ridondanti):                                  ║
║   - black, isort, ... (oppure "nessuno")                    ║
╠══════════════════════════════════════════════════════════════╣
║ SMOKE TEST:                                                 ║
║   ruff check:     ✅ (N warnings)                            ║
║   ruff format:    ✅ (N file da formattare)                   ║
║   mypy:           ✅ (N errori tipo — attesi)                 ║
║   bandit:         ✅ (N issues)                               ║
║   deptry:         ✅ / ❌                                     ║
║   vulture:        ✅ (N unused code)                          ║
║   xenon:          ✅ (grade: X)                               ║
║   interrogate:    ✅ (N% docstring coverage)                  ║
║   codespell:      ✅ (N typos)                                ║
║   refurb:         ✅ (N suggestions)                          ║
╠══════════════════════════════════════════════════════════════╣
║ PROSSIMO PASSO:                                             ║
║ Usa 2_QUALITY_STACK_CONFIG.md per configurare pyproject.toml  ║
║ e .pre-commit-config.yaml con regole specifiche.            ║
╚══════════════════════════════════════════════════════════════╝
```

=============================================================================
TROUBLESHOOTING
=============================================================================

Problema: `pip install` fallisce per conflitti di versione
→ Soluzione: installa i tool uno alla volta per identificare il conflitto
→ Se il conflitto è con una dipendenza di produzione, usa:
  pip install <tool> --no-deps  (solo come ultima risorsa)

Problema: refurb crash con UnicodeDecodeError (Windows)
→ Soluzione: impostare la variabile d'ambiente:
  set PYTHONUTF8=1  (cmd)
  $env:PYTHONUTF8=1 (PowerShell)
→ Nel pre-commit usare:
  entry: env PYTHONUTF8=1 python -m refurb

Problema: mypy "error: Duplicate module" o "Source file found twice"
→ Soluzione: verificare che `exclude` in [tool.mypy] sia corretto
→ Non avere la stessa directory in più path

Problema: deptry non trova il package sorgente
→ Soluzione: assicurarsi che il package abbia __init__.py
→ Oppure configurare known_first_party in [tool.deptry]

Problema: xenon non si installa (richiede radon)
→ Soluzione: pip install radon xenon

Problema: pre-commit install fallisce "not a git repository"
→ Soluzione: eseguire prima `git init` se il progetto non è un repo git

Problema: vulture troppi falsi positivi
→ Soluzione: creare un whitelist file:
  vulture src/ whitelist.py --min-confidence 80
→ Il file whitelist.py contiene le variabili/funzioni da ignorare

=============================================================================
PRINCIPI GUIDA
=============================================================================

1. UN TOOL PER FUNZIONE: Mai due tool che fanno la stessa cosa.
   Ruff = lint + format. Non aggiungere Black o Isort.

2. INSTALLA PRIMA, CONFIGURA DOPO: Questo prompt installa.
   2_QUALITY_STACK_CONFIG.md configura. Due fasi separate.

3. STUBS ESPLICITI: Mai risolvere missing stubs con
   ignore_missing_imports = true globale. Installa gli stubs
   o usa override per-module.

4. VERIFICA SEMPRE: Ogni tool deve essere verificato con --version
   E con uno smoke test sulla codebase reale.

5. DOCUMENTA: Il report finale serve come riferimento per il team
   e per future reinstallazioni.
```
