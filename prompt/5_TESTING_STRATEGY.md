# 5 — Testing Strategy per Progetti Python

> Prompt universale per analizzare la copertura test, identificare gap critici,
> e costruire una strategia di testing completa su qualsiasi progetto Python.
> Compatibile con qualsiasi LLM che abbia accesso al filesystem e al terminale.

---

## Prompt

```
Ruolo: Agisci come un QA Engineer / Test Architect specializzato in Python.

Contesto: Devo analizzare lo stato attuale dei test di un progetto Python,
identificare i gap di copertura più critici, e produrre una strategia
per raggiungere una copertura robusta e mantenibile.

Obiettivo: Analizza test esistenti, misura coverage, identifica moduli
non testati, e produci un piano d'azione con priorità.

IMPORTANTE: Questo prompt è GENERICO. Adattati al progetto che trovi.

=============================================================================
FASE 0 — RICOGNIZIONE TEST ESISTENTI
=============================================================================

1. IDENTIFICA il framework di test:
   ```bash
   # Cerca configurazione pytest
   grep -r "pytest" pyproject.toml setup.cfg tox.ini 2>/dev/null

   # Cerca configurazione unittest
   grep -r "unittest" src/ --include="*.py" -l 2>/dev/null
   ```

2. MAPPA la struttura dei test:
   ```bash
   # Tutti i file di test
   find tests/ -name "test_*.py" -o -name "*_test.py" 2>/dev/null

   # Conta test per file
   grep -c "def test_" tests/**/*.py 2>/dev/null | sort -t: -k2 -rn
   ```

3. IDENTIFICA i file sorgente:
   ```bash
   # Tutti i moduli Python sorgente (esclusi test)
   find src/ -name "*.py" -not -name "test_*" -not -name "__pycache__" 2>/dev/null
   ```

4. CALCOLA il rapporto di copertura strutturale:
   Per ogni file in src/, verifica se esiste un corrispondente test_*.py:

   ```
   src/modulo.py          → tests/test_modulo.py         ✅ coperto
   src/altro.py           → tests/test_altro.py          ❌ MANCANTE
   src/sub/helper.py      → tests/sub/test_helper.py     ❌ MANCANTE
   ```

   File senza test corrispondente → GAP da colmare.

=============================================================================
FASE 1 — COVERAGE QUANTITATIVA
=============================================================================

1. ESEGUI pytest con coverage:
   ```bash
   pytest --cov=src --cov-report=term-missing --cov-report=html -v
   ```

   Se pytest non è configurato:
   ```bash
   pip install pytest pytest-cov
   pytest tests/ --cov=src --cov-report=term-missing -v
   ```

2. ANALIZZA il report coverage:

   Soglie di riferimento:
   - < 30%:  Copertura critica — rischio alto di regressioni
   - 30-50%: Copertura bassa — funzionalità core probabilmente scoperte
   - 50-70%: Copertura accettabile — focus su branch coverage
   - 70-85%: Copertura buona — target per la maggior parte dei progetti
   - > 85%:  Copertura eccellente — mantenere, non inseguire il 100%

3. IDENTIFICA i moduli con coverage più bassa:
   - Elenca i 10 file con coverage peggiore
   - Per ognuno, nota le righe "Missing" dal report
   - Classifica per criticità (vedi Fase 3)

4. ANALIZZA branch coverage (non solo line coverage):
   ```bash
   pytest --cov=src --cov-branch --cov-report=term-missing
   ```
   Branch coverage è più significativa di line coverage perché
   verifica che ogni ramo di ogni if/else sia stato esercitato.

=============================================================================
FASE 2 — ANALISI QUALITATIVA DEI TEST
=============================================================================

Non basta avere tanti test. I test devono essere BUONI.

1. VERIFICA test quality per ogni file di test:

   a. NOMI DESCRITTIVI:
      ```
      ✅ def test_calculate_bmi_returns_correct_value_for_normal_weight():
      ❌ def test_1():
      ❌ def test_calc():
      ```

   b. ARRANGE-ACT-ASSERT (AAA):
      Ogni test dovrebbe avere tre sezioni chiare:
      - Arrange: setup dei dati
      - Act: esecuzione dell'azione
      - Assert: verifica del risultato

      Cerca test senza assert:
      ```bash
      # Test che non hanno assert (possibili test vuoti/incompleti)
      grep -L "assert" tests/**/*.py 2>/dev/null
      ```

   c. UN ASSERT PER TEST (ideale):
      ```bash
      # Test con troppi assert (> 5) — possibili God Tests
      for f in tests/**/*.py; do
        awk '/def test_/{name=$0; count=0} /assert/{count++} /^def |^class /{if(count>5) print name, count}' "$f" 2>/dev/null
      done
      ```

   d. INDIPENDENZA:
      - I test dipendono dall'ordine di esecuzione? → FRAGILE
      - I test condividono stato mutabile? → FRAGILE
      - I test dipendono da risorse esterne (DB, API, file)? → SLOW + FRAGILE

2. CERCA ANTI-PATTERN nei test:

   a. TEST CHE NON TESTANO NULLA:
      ```bash
      # Funzioni test senza corpo
      grep -A2 "def test_" tests/**/*.py 2>/dev/null | grep -B1 "pass$"
      ```

   b. MOCK ECCESSIVO:
      ```bash
      # File con troppi mock (> 10 per file)
      grep -c "mock\|patch\|MagicMock" tests/**/*.py 2>/dev/null | \
        awk -F: '$2 > 10 {print}'
      ```
      Troppi mock → i test non testano il comportamento reale.

   c. TEST FRAGILI (dipendono da valori esatti):
      ```bash
      # Assert su stringhe esatte (fragili se cambiano messaggi)
      grep -rnE 'assert.*==.*["\'].*["\']' tests/ --include="*.py" | head -10
      ```

   d. FIXTURE MANCANTI:
      - Setup ripetuto in ogni test → estrarre in fixture/conftest.py
      ```bash
      grep -c "conftest.py" tests/**/* 2>/dev/null
      # Se 0, probabilmente mancano fixture condivise
      ```

=============================================================================
FASE 3 — PRIORITIZZAZIONE DEI GAP
=============================================================================

Non tutti i gap di coverage hanno la stessa importanza.
Classifica per RISCHIO BUSINESS, non per percentuale.

PRIORITÀ ALTA (testare PRIMA):
- Logica di business core (calcoli, trasformazioni dati)
- Gestione dati utente (salvataggio, caricamento, migrazione)
- Integrazioni esterne (API, database, file I/O)
- Parsing/validazione input
- Gestione errori e edge case
- Flussi che toccano dati finanziari o sensibili

PRIORITÀ MEDIA:
- Utility functions e helper
- Conversioni formato/unità
- Logica di presentazione (formatting)
- Configurazione e setup

PRIORITÀ BASSA:
- Codice GUI puramente visuale (layout, colori, font)
- Boilerplate (__repr__, __str__)
- Codice generato automaticamente
- Script one-off

PER OGNI GAP, documenta:
```
File: src/modulo.py
Coverage attuale: 45%
Righe mancanti: 23-45, 78-92, 110-130
Priorità: ALTA
Motivo: Contiene logica di calcolo core usata ovunque
Test necessari:
  - test caso base con input valido
  - test edge case (input vuoto, None, valori estremi)
  - test errore (input invalido, eccezioni attese)
Effort stimato: 2h
```

=============================================================================
FASE 4 — STRATEGIA DI FIXTURE E CONFTEST
=============================================================================

Un buon sistema di fixture riduce la duplicazione nei test e li rende
più leggibili e mantenibili.

1. ANALIZZA conftest.py esistente (se esiste):
   ```bash
   find tests/ -name "conftest.py" 2>/dev/null
   ```
   - Quante fixture sono definite?
   - Sono usate effettivamente nei test?
   - Coprono i casi d'uso principali (DB, mock API, dati di test)?

2. FIXTURE RACCOMANDATE per tipo di progetto:

   Database (SQLAlchemy/Django ORM):
   ```python
   @pytest.fixture
   def db_session():
       """Database session con rollback automatico."""
       # Setup: crea sessione in-memory o transaction
       # Yield: passa la sessione al test
       # Teardown: rollback automatico

   @pytest.fixture
   def sample_data(db_session):
       """Dati di esempio pre-popolati."""
       # Inserisci record di test
   ```

   API esterne:
   ```python
   @pytest.fixture
   def mock_api(requests_mock):  # o responses
       """Mock delle API esterne."""
       # Registra risposte mock per ogni endpoint usato

   @pytest.fixture
   def api_response_success():
       """Payload di risposta API di successo."""
       return {"status": "ok", "data": [...]}
   ```

   File system:
   ```python
   @pytest.fixture
   def tmp_config(tmp_path):
       """File di configurazione temporaneo."""
       config = tmp_path / "config.json"
       config.write_text('{"key": "value"}')
       return config
   ```

3. ORGANIZZAZIONE conftest.py:
   ```
   tests/
   ├── conftest.py           # Fixture globali (db, mock generici)
   ├── data/
   │   └── conftest.py       # Fixture per test data layer
   ├── logic/
   │   └── conftest.py       # Fixture per test logica
   └── integration/
       └── conftest.py       # Fixture per test integrazione
   ```

=============================================================================
FASE 5 — PATTERN DI TEST RACCOMANDATI
=============================================================================

Per ogni tipo di codice, suggerisci il pattern di test appropriato:

1. FUNZIONI PURE (input → output, no side effect):
   ```python
   @pytest.mark.parametrize("input_val, expected", [
       (caso_base, risultato_atteso),
       (edge_case_1, risultato_edge_1),
       (edge_case_2, risultato_edge_2),
   ])
   def test_funzione(input_val, expected):
       assert funzione(input_val) == expected
   ```
   Usa @parametrize per coprire più casi senza duplicare codice.

2. CLASSI CON STATO:
   ```python
   class TestMiaClasse:
       def test_stato_iniziale(self):
           obj = MiaClasse()
           assert obj.valore == default

       def test_modifica_stato(self):
           obj = MiaClasse()
           obj.aggiorna(nuovo_valore)
           assert obj.valore == nuovo_valore

       def test_invariante_mantenuto(self):
           obj = MiaClasse()
           obj.operazione_complessa()
           assert obj.invariante_valido()
   ```

3. CODICE CON SIDE EFFECT (DB, file, API):
   ```python
   def test_salva_record(db_session):
       # Arrange
       record = Record(nome="test")

       # Act
       salva(db_session, record)

       # Assert
       risultato = db_session.query(Record).first()
       assert risultato.nome == "test"
   ```

4. ECCEZIONI:
   ```python
   def test_errore_input_invalido():
       with pytest.raises(ValueError, match="deve essere positivo"):
           funzione(valore_negativo=-5)
   ```

5. INTEGRAZIONE API ESTERNE:
   ```python
   def test_fetch_dati(mock_api):
       mock_api.get("https://api.example.com/data", json={"ok": True})
       risultato = client.fetch_dati()
       assert risultato["ok"] is True
   ```

=============================================================================
FASE 6 — PIANO DI TESTING
=============================================================================

Produci un piano ordinato per priorità. Formato:

```
╔══════════════════════════════════════════════════════════════╗
║               TESTING STRATEGY REPORT                       ║
╠══════════════════════════════════════════════════════════════╣
║ Progetto:             <nome>                                ║
║ Data:                 <data>                                ║
║ Coverage attuale:     N%  (line) / N% (branch)              ║
║ Test totali:          N                                     ║
║ File testati:         N / M  (N%)                           ║
║ Tempo esecuzione:     Ns                                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ COVERAGE PER MODULO:                                        ║
║  src/core.py           95%  ████████████████████░  ✅        ║
║  src/logic.py          72%  ███████████████░░░░░░  ⚠️        ║
║  src/database.py       45%  █████████░░░░░░░░░░░  ❌        ║
║  src/api.py            12%  ██░░░░░░░░░░░░░░░░░░  🔴        ║
║  src/gui.py             0%  ░░░░░░░░░░░░░░░░░░░░  ⬛        ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ GAP CRITICI (Priorità ALTA):                                ║
║                                                              ║
║  1. src/database.py (45% → target 80%)                      ║
║     Mancano: test upsert, test migration, test rollback     ║
║     Test da scrivere: ~12                                    ║
║     Fixture necessarie: db_session, sample_records           ║
║                                                              ║
║  2. src/api.py (12% → target 70%)                           ║
║     Mancano: test error handling, test timeout, test retry   ║
║     Test da scrivere: ~8                                     ║
║     Fixture necessarie: mock_api, api_responses              ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ QUALITÀ TEST ESISTENTI:                                     ║
║  Naming:              ✅ / ⚠️ / ❌                           ║
║  AAA pattern:         ✅ / ⚠️ / ❌                           ║
║  Indipendenza:        ✅ / ⚠️ / ❌                           ║
║  Fixture usage:       ✅ / ⚠️ / ❌                           ║
║  Parametrize usage:   ✅ / ⚠️ / ❌                           ║
║  Anti-pattern trovati: N                                    ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ PIANO DI AZIONE:                                             ║
║                                                              ║
║  Sprint 1 — Foundation (setup + quick wins):                ║
║   □ Creare/aggiornare conftest.py con fixture base          ║
║   □ Fix test fragili/broken esistenti                       ║
║   □ Aggiungere test per funzioni pure (più facili)          ║
║   Target: +N% coverage                                      ║
║                                                              ║
║  Sprint 2 — Core business logic:                             ║
║   □ Test modulo X (logica core)                             ║
║   □ Test modulo Y (calcoli/trasformazioni)                  ║
║   □ Edge case e error handling                              ║
║   Target: +N% coverage                                      ║
║                                                              ║
║  Sprint 3 — Integration:                                     ║
║   □ Test database operations (con mock/in-memory)           ║
║   □ Test API esterne (con mock)                             ║
║   □ Test file I/O                                           ║
║   Target: +N% coverage                                      ║
║                                                              ║
║  Coverage target finale: N%                                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

=============================================================================
PRINCIPI GUIDA
=============================================================================

1. TESTA COMPORTAMENTO, NON IMPLEMENTAZIONE: I test devono verificare
   COSA fa il codice, non COME lo fa. Se cambi l'implementazione
   mantenendo lo stesso risultato, i test non dovrebbero rompersi.

2. PIRAMIDE DEI TEST: Tanti unit test (veloci, isolati),
   alcuni integration test (più lenti, più realistici),
   pochi end-to-end test (lenti, fragili ma completi).

3. COVERAGE ≠ QUALITÀ: 100% coverage con assert banali è peggio
   di 70% coverage con test significativi. Prioritizza la qualità.

4. TEST COME DOCUMENTAZIONE: Un buon test spiega come usare il codice.
   Leggendo il test, dovrebbe essere chiaro il contratto della funzione.

5. FAIL FAST: I test devono fallire velocemente e con messaggi chiari.
   Usa messaggi custom negli assert per debugging più rapido.

6. ISOLA LE DIPENDENZE: Mocka le dipendenze esterne (DB, API, file system)
   nei unit test. Usa le dipendenze reali solo negli integration test.
```
