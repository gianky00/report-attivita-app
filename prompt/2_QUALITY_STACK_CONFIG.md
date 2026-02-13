# 2/2 — Configurazione Stack Qualità Codice Python

> **Step 2 di 2** — Configura pyproject.toml e .pre-commit-config.yaml.
> Prerequisito: aver eseguito `1_QUALITY_STACK_INSTALL.md` prima.
>
> Prompt universale, replicabile su qualsiasi progetto Python.
> Copia e incolla in un LLM con accesso al filesystem del progetto.

---

## Prompt

```
Ruolo: Agisci come un Python DevOps Engineer specializzato in Modern Tooling, Static Analysis e CI/CD pipelines.

Contesto: Devo configurare da zero lo stack completo di qualita del codice per un progetto Python.
Lo stack deve essere minimale, senza strumenti ridondanti, e ogni tool deve avere un ruolo unico.

Obiettivo: Configura pyproject.toml e .pre-commit-config.yaml seguendo ESATTAMENTE le regole sotto.

=============================================================================
FASE 0 — ANALISI DEL PROGETTO (eseguire PRIMA di qualsiasi modifica)
=============================================================================

1. Leggi pyproject.toml (o setup.py/setup.cfg) per capire:
   - Python version target (requires-python)
   - Dipendenze di produzione (dependencies)
   - Dipendenze di sviluppo (optional-dependencies.dev)
   - Configurazioni tool esistenti

2. Scansiona src/ (o la directory sorgente principale) per identificare:
   - TUTTI gli import di librerie terze usati nel codice
   - Quali di queste librerie hanno py.typed (built-in stubs)
   - Quali necessitano stubs esterni (pandas-stubs, types-requests, ecc.)
   - Quali NON hanno stubs disponibili (necessitano ignore_missing_imports)

3. Verifica le versioni elencate di tutti i tool:
   - ruff, mypy, deptry, bandit, codespell, refurb, pre-commit
   - Se Black e installato, va RIMOSSO (sostituito da Ruff)
   - Se isort e installato standalone, va RIMOSSO (sostituito da Ruff)
   - Se flake8 e installato, va RIMOSSO (sostituito da Ruff)

4. Controlla se esiste gia .pre-commit-config.yaml e analizza i hook presenti.

=============================================================================
FASE 1 — RUFF: "The One Tool" (Linter + Formatter)
=============================================================================

Ruff SOSTITUISCE completamente: Black, Isort, Flake8, pyupgrade.
Se uno di questi e presente nelle dipendenze o nel pre-commit, RIMUOVILO.

Configura [tool.ruff] in pyproject.toml:

```toml
[tool.ruff]
line-length = 100
target-version = "py3XX"  # ← ALLINEA con [tool.mypy] python_version

exclude = [
    ".git", ".venv", "venv", "__pycache__",
    "build", "dist", "*.egg-info",
    # Aggiungi directory specifiche del progetto (logs, data, ecc.)
]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort (sostituisce isort standalone)
    "N",    # pep8-naming
    "UP",   # pyupgrade (modernizza sintassi al target-version)
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "RUF",  # regole Ruff-specifiche
    "PERF", # perflint
    "T20",  # flake8-print (cattura print() in produzione)
]

ignore = [
    "E501",    # line too long → gestito dal formatter
    # Aggiungi ignore specifici del progetto se necessario.
    # REGOLA: ogni ignore DEVE avere un commento che spiega il motivo.
]

fixable = ["ALL"]
unfixable = []

[tool.ruff.lint.isort]
known-first-party = ["NOME_PACKAGE"]  # ← nome del package sorgente
combine-as-imports = true

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["T20", "B011", "PLR2004"]
"scripts/**/*.py" = ["T20"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
docstring-code-format = true
```

REGOLE CRITICHE per Ruff:
- target-version DEVE essere uguale a python_version di Mypy
- E501 DEVE essere in ignore (il formatter gestisce la lunghezza)
- Se T201 (print found) genera troppi falsi positivi, aggiungilo a ignore
  MA segnalalo all'utente come debt tecnico da risolvere
- NON aggiungere regole che non capisci. Ogni regola deve essere giustificata.

=============================================================================
FASE 2 — MYPY: Type Safety Strict
=============================================================================

Configura [tool.mypy] in pyproject.toml:

```toml
[tool.mypy]
python_version = "3.XX"  # ← ALLINEA con ruff target-version

# STRICT CORE
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true

# ANTI-ANY
disallow_any_generics = true
disallow_subclassing_any = true
warn_return_any = true

# NONE SAFETY
no_implicit_optional = true
strict_optional = true

# WARNINGS
warn_unused_configs = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unreachable = true

# OUTPUT
show_error_codes = true
show_error_context = true
pretty = true

# IMPORT: MAI globale, solo per-module
ignore_missing_imports = false

exclude = [
    'venv', '.venv', 'tests',
    # Aggiungi directory non-sorgente del progetto
]
```

REGOLE CRITICHE per Mypy:
- ignore_missing_imports = false SEMPRE a livello globale
- Per ogni libreria terza SENZA stubs, aggiungi un override SPECIFICO:

```toml
[[tool.mypy.overrides]]
module = "nome_libreria.*"
ignore_missing_imports = true
```

- Per determinare quali librerie necessitano override:
  1. Controlla se la libreria ha py.typed: `Path(spec.origin).parent / 'py.typed'`
  2. Se ha py.typed → NON serve override (ha stubs built-in)
  3. Se NON ha py.typed → cerca stubs esterni (types-X, X-stubs)
  4. Se non esistono stubs → aggiungi override ignore_missing_imports
  5. Se esistono stubs → installali e aggiungili a dev dependencies

- Test con regole rilassate:
```toml
[[tool.mypy.overrides]]
module = "tests.*"
ignore_errors = true
```

=============================================================================
FASE 3 — DEPTRY: Dependency Hygiene
=============================================================================

```toml
[tool.deptry]
extend_exclude = ["tests", "scripts"]
known_first_party = ["NOME_PACKAGE"]

[tool.deptry.package_module_name_map]
# Solo per pacchetti il cui nome pip != nome import
# Esempio: python-dotenv = "dotenv"

[tool.deptry.per_rule_ignores]
DEP002 = [
    # CLI tools (mai importati nel codice sorgente)
    # Elenca QUI tutti i tool dev: pytest, ruff, mypy, ecc.
    # Elenca QUI type stubs: pandas-stubs, types-requests, ecc.
    # Elenca QUI librerie runtime/condizionali non importate direttamente
]
DEP003 = [
    # Import transitivi: moduli usati via dipendenza indiretta
    # Elenca SOLO quelli verificati come necessari
]
```

REGOLE CRITICHE per Deptry:
- MAI usare `ignore = ["DEP002", "DEP003"]` globale
- SEMPRE usare per_rule_ignores con lista esplicita di pacchetti
- Ogni pacchetto in per_rule_ignores DEVE avere una ragione chiara
- package_module_name_map serve SOLO quando il nome pip != nome import

=============================================================================
FASE 4 — ALTRI TOOL (Bandit, Codespell, Interrogate)
=============================================================================

Bandit (sicurezza):
```toml
[tool.bandit]
exclude_dirs = ["tests", ".venv", "venv"]
skips = ["B101"]  # assert nei test
```

Codespell (typo):
- Se esiste gia .codespellrc, NON duplicare la config in pyproject.toml
- Se NON esiste, crea .codespellrc con:
  - skip: directory non-sorgente
  - ignore-words-list: termini specifici del dominio (brand, acronimi, lingue)

Interrogate (docstring coverage):
```toml
[tool.interrogate]
ignore-init-method = true
ignore-init-module = true
ignore-magic = true
ignore-semiprivate = true
ignore-private = true
ignore-property-decorators = true
ignore-module = true
ignore-nested-functions = true
fail-under = 0  # ← Parti da 0, alza gradualmente
exclude = ["tests", "venv", ".venv", "build"]
```

=============================================================================
FASE 5 — PRE-COMMIT PIPELINE
=============================================================================

Crea .pre-commit-config.yaml con questa struttura ESATTA.
L'ordine dei hook e IMPORTANTE (dal piu veloce al piu lento):

```yaml
exclude: '<pattern per file da ignorare>'

repos:
  # 1. Hook generici (velocissimi)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: <latest>
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: debug-statements

  # 2. Ruff: Lint + Format (veloce, sostituisce Black+Isort+Flake8)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <allinea con versione installata>
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  # 3. Mypy: Type checking (lento, usa pyproject.toml)
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: <allinea con versione installata>
    hooks:
      - id: mypy
        additional_dependencies:
          # Elenca QUI gli stubs necessari
        # NESSUN args: mypy legge TUTTO da pyproject.toml
        exclude: '^tests/'

  # 4. Deptry
  - repo: https://github.com/fpgmaas/deptry
    rev: <allinea con versione installata>
    hooks:
      - id: deptry
        additional_dependencies: [deptry]

  # 5. Refurb (modernizzazione)
  - repo: https://github.com/dosisod/refurb
    rev: <latest>
    hooks:
      - id: refurb
        exclude: '^tests/'

  # 6. Bandit (sicurezza)
  - repo: https://github.com/PyCQA/bandit
    rev: <latest>
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        additional_dependencies: ["bandit[toml]"]
        files: ^src/  # Solo codice di produzione

  # 7. Codespell (typo)
  - repo: https://github.com/codespell-project/codespell
    rev: <latest>
    hooks:
      - id: codespell
```

REGOLE CRITICHE per pre-commit:
- I rev DEVONO essere allineati con le versioni pip disponibili
- Mypy nel pre-commit NON DEVE avere args che sovrascrivono pyproject.toml
  MAI: args: [--ignore-missing-imports]
  MAI: args: [--disable-error-code=xxx]
- ruff DEVE avere DUE hook: prima `ruff` (lint), poi `ruff-format` (format)
- Black NON DEVE essere presente. Se lo trovi, RIMUOVILO.

=============================================================================
FASE 6 — DEV DEPENDENCIES (pulizia)
=============================================================================

La sezione [project.optional-dependencies] dev DEVE contenere:
- Tool di qualita: ruff, mypy, deptry, bandit, codespell, refurb
- Type stubs: pandas-stubs, types-requests, ecc. (solo quelli necessari)
- Test: pytest, pytest-cov, pytest-mock, ecc.
- Pre-commit: pre-commit

NON DEVE contenere:
- black (sostituito da ruff)
- isort (sostituito da ruff)
- flake8 e plugin flake8-* (sostituiti da ruff)
- pyupgrade (sostituito da ruff UP)
- autopep8 (sostituito da ruff)

=============================================================================
FASE 7 — VALIDAZIONE FINALE
=============================================================================

Dopo aver completato la configurazione, esegui TUTTI questi comandi
e riporta i risultati:

1. ruff check src/ --statistics    → Mostra distribuzione errori lint
2. ruff format --check src/        → Mostra file da riformattare
3. python -m mypy src/             → Mostra errori di tipo (usa pyproject.toml)
4. python -m deptry src/           → DEVE dare "No dependency issues found"
5. Conta errori per categoria e riporta:
   - Quanti sono auto-fixabili (ruff --fix)
   - Quanti richiedono intervento manuale (mypy)

Se deptry NON da "Success", c'e un problema nella configurazione
per_rule_ignores. Correggilo prima di procedere.

=============================================================================
PRINCIPI GUIDA
=============================================================================

1. SINGLE SOURCE OF TRUTH: Ogni tool legge la config da pyproject.toml.
   Il pre-commit NON sovrascrive con args cio che e gia in pyproject.toml.

2. NESSUNA RIDONDANZA: Un solo tool per funzione.
   Formatting = ruff format. Linting = ruff check. Type checking = mypy.

3. EXPLICIT OVER IMPLICIT: Mai ignore_missing_imports globale.
   Mai ignore globale per regole deptry. Sempre per-module/per-rule.

4. ALLINEAMENTO VERSIONI: target-version di ruff = python_version di mypy
   = requires-python del progetto. Se sono diversi, e un bug di config.

5. FAIL FAST: Lo stack pre-commit e ordinato dal piu veloce al piu lento.
   Se trailing-whitespace fallisce, non sprechi tempo su mypy.
```
