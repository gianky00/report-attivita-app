# 3 — Refactoring Audit per Progetti Python

> Prompt universale per analizzare debito tecnico, complessità, duplicazioni e architettura
> di qualsiasi progetto Python. Produce un report con priorità e azioni concrete.
> Compatibile con qualsiasi LLM che abbia accesso al filesystem e al terminale.

---

## Prompt

```
Ruolo: Agisci come un Software Architect specializzato in Python code quality e refactoring.

Contesto: Devo valutare lo stato di salute del codice di un progetto Python.
L'audit deve identificare debito tecnico, code smell, violazioni architetturali
e opportunità di miglioramento — con priorità e costo/beneficio.

Obiettivo: Analizza la codebase, misura metriche oggettive, e produci un report
con azioni ordinate per impatto.

IMPORTANTE: Questo prompt è GENERICO. Adattati al progetto che trovi.

=============================================================================
FASE 0 — MAPPA DEL PROGETTO
=============================================================================

1. COMPRENDI la struttura:
   ```bash
   # Struttura directory (3 livelli)
   find . -type f -name "*.py" | head -50
   # oppure su Windows:
   dir /s /b *.py | findstr /V __pycache__ | findstr /V .venv
   ```

2. MISURA le dimensioni:
   ```bash
   # Linee di codice per file (ordinate per dimensione)
   find . -name "*.py" -not -path "./.venv/*" -not -path "./__pycache__/*" \
     -exec wc -l {} + | sort -rn | head -20
   ```

   Soglie di allarme per singolo file:
   - > 500 LOC → candidato per split
   - > 800 LOC → split necessario
   - > 1000 LOC → split urgente (God Object probabile)

3. IDENTIFICA l'architettura:
   - Esiste una separazione a layer (GUI/Logic/Data)?
   - Ci sono dipendenze circolari tra moduli?
   - Il codice segue un pattern riconoscibile (MVC, Layered, Hexagonal)?

4. LEGGI pyproject.toml per capire:
   - Dipendenze e loro scopo
   - Tool di qualità già configurati
   - Versione Python target

=============================================================================
FASE 1 — COMPLESSITÀ CICLOMATICA (Xenon + Radon)
=============================================================================

La complessità ciclomatica misura quanti percorsi indipendenti ha il codice.
Più percorsi = più difficile da testare e mantenere.

1. ESEGUI Xenon con soglie standard:
   ```bash
   # Soglie: -b B (modulo) -m A (metodo) -a A (media)
   xenon src/ -b B -m A -a A
   ```

   Se xenon fallisce (exit code != 0), ci sono funzioni troppo complesse.

2. ESEGUI Radon per dettaglio:
   ```bash
   # Complessità per funzione (ordine decrescente)
   radon cc src/ -s -n C --no-assert

   # Maintainability Index per file
   radon mi src/ -s -n B
   ```

   Grading complessità:
   - A (1-5):   Semplice, facilmente testabile
   - B (6-10):  Moderata, accettabile
   - C (11-15): Complessa, candidata per refactoring
   - D (16-20): Troppo complessa, refactoring necessario
   - F (21+):   Non mantenibile, refactoring urgente

3. PER OGNI funzione con grade C o peggio:
   - Identifica la causa (troppi if/elif, loop annidati, try/except multipli)
   - Suggerisci strategia di semplificazione:
     * Extract Method: sposta blocchi logici in funzioni dedicate
     * Replace Conditional with Polymorphism
     * Early Return: elimina nesting con guard clause
     * Strategy Pattern: sostituisci catene if/elif con dizionario
     * Decompose Conditional: estrai condizioni complesse in funzioni bool

=============================================================================
FASE 2 — CODICE MORTO (Vulture)
=============================================================================

Codice morto è debito tecnico puro: occupa spazio, confonde, rallenta la comprensione.

1. ESEGUI Vulture:
   ```bash
   vulture src/ --min-confidence 80
   ```

   --min-confidence 80 riduce i falsi positivi.

2. CLASSIFICA i risultati:

   Certamente morto (rimuovere):
   - Funzioni mai chiamate da nessun modulo
   - Variabili assegnate ma mai lette
   - Import mai usati (Ruff F401 li trova anche)
   - Classi mai istanziate

   Probabili falsi positivi (verificare):
   - Callback GUI (chiamati dal framework, non dal codice)
   - Metodi __dunder__ (chiamati da Python internamente)
   - Funzioni esposte come API pubblica
   - Variabili usate tramite getattr/globals
   - Funzioni registrate come hook/handler

3. QUANTIFICA il debito:
   - Conta le LOC di codice morto confermato
   - Calcola la percentuale sul totale: (dead_loc / total_loc) * 100
   - > 5% → debito significativo
   - > 10% → pulizia urgente

=============================================================================
FASE 3 — DUPLICAZIONI
=============================================================================

Il codice duplicato è il peggior code smell: ogni bug va corretto N volte.

1. CERCA duplicazioni con approccio manuale:
   ```bash
   # Funzioni con nomi simili (possibili duplicati)
   grep -rnE "def (get_|fetch_|load_|save_|update_|create_)" src/ --include="*.py" | sort

   # Blocchi try/except ripetuti
   grep -c "try:" src/**/*.py 2>/dev/null | sort -t: -k2 -rn

   # Pattern ripetuti (ad es. stessa sequenza open/read/parse)
   grep -rnE "(open\(|with open)" src/ --include="*.py"
   ```

2. SE disponibile, usa tool dedicati:
   ```bash
   # CPD (Copy-Paste Detector) - parte di PMD
   # oppure
   pip install pylint
   pylint --disable=all --enable=duplicate-code src/
   ```

3. PER OGNI duplicazione trovata, suggerisci:
   - Extract Function: codice comune → funzione condivisa
   - Template Method: algoritmo comune con variazioni → classe base
   - Strategy: stessa struttura, logica diversa → pattern strategy
   - Configuration: stessi passi con parametri diversi → config-driven

=============================================================================
FASE 4 — CODE SMELLS
=============================================================================

Analizza il codice per i code smell più impattanti:

1. GOD CLASS / GOD METHOD:
   ```bash
   # Classi con troppi metodi
   grep -c "def " src/**/*.py 2>/dev/null | sort -t: -k2 -rn | head -10

   # Metodi con troppi parametri (> 5)
   grep -rnE "def \w+\(self(, \w+){5,}" src/ --include="*.py"
   ```

   Soglie:
   - Classe con > 20 metodi → God Class, considerare split
   - Metodo con > 5 parametri → troppi, usare dataclass/dict
   - Metodo con > 50 LOC → troppo lungo, extract method

2. FEATURE ENVY:
   - Metodo che usa più attributi di un'altra classe che della propria
   - Cerca catene di chiamate: obj.attr.method().result
   ```bash
   grep -rnE "\.\w+\.\w+\.\w+\." src/ --include="*.py"
   ```

3. PRIMITIVE OBSESSION:
   - Dizionari usati dove servirebbe una dataclass/NamedTuple
   - Stringhe usate come enum (invece di Enum)
   - Tuple usate per dati strutturati
   ```bash
   grep -rnE "dict\[str,\s*(str|int|float|Any)\]" src/ --include="*.py"
   ```

4. MAGIC NUMBERS / STRINGS:
   ```bash
   # Numeri magici (esclusi 0, 1, -1)
   grep -rnE "==\s*[2-9][0-9]*|>\s*[2-9][0-9]*|<\s*[2-9][0-9]*" src/ --include="*.py" | head -20

   # Stringhe magiche ripetute
   grep -rnE "['\"]([^'\"]{5,})['\"]" src/ --include="*.py" | \
     awk -F"['\"]" '{print $2}' | sort | uniq -c | sort -rn | head -20
   ```

5. COUPLING (accoppiamento eccessivo):
   ```bash
   # Import tra moduli — grafo delle dipendenze
   grep -rn "^from \|^import " src/ --include="*.py" | \
     grep -v "__pycache__" | sort
   ```
   - Moduli con > 10 import da altri moduli interni → accoppiamento alto
   - Import circolari → problema architetturale

=============================================================================
FASE 5 — ANALISI ARCHITETTURALE
=============================================================================

1. VERIFICA SEPARATION OF CONCERNS:
   - Il layer GUI importa direttamente il database? → violazione
   - La logica di business dipende dal framework GUI? → violazione
   - I moduli dati contengono logica di presentazione? → violazione

2. VERIFICA SINGLE RESPONSIBILITY:
   Per ogni file principale:
   - Quante "responsabilità" ha? (parsing, calcolo, I/O, rendering)
   - Potrebbe essere descritto con una singola frase senza "e"/"anche"?

3. VERIFICA DEPENDENCY DIRECTION:
   Le dipendenze dovrebbero andare in UNA direzione:
   ```
   GUI → Logic → Data    ✅ corretto
   Data → Logic → GUI    ❌ invertito
   GUI ↔ Logic           ❌ circolare
   ```

4. IDENTIFICA ANTI-PATTERN:
   - Singleton nascosto (variabili globali di modulo)
   - Service Locator (import condizionali sparsi)
   - Anemic Domain Model (classi solo con getter/setter)
   - Blob/God Object (un file che fa tutto)

=============================================================================
FASE 6 — METRICHE RIEPILOGATIVE
=============================================================================

Raccogli queste metriche per il report:

```bash
# 1. Linee totali di codice (esclusi test e venv)
find src/ -name "*.py" -exec cat {} + | wc -l

# 2. Numero di file Python
find src/ -name "*.py" | wc -l

# 3. LOC media per file
# totale_loc / numero_file

# 4. File più grandi (top 10)
find src/ -name "*.py" -exec wc -l {} + | sort -rn | head -11

# 5. Rapporto test/codice
find tests/ -name "*.py" -exec cat {} + 2>/dev/null | wc -l
# test_loc / src_loc — ideale: > 0.5 (50%)

# 6. Complessità media (da radon)
radon cc src/ -a -s 2>/dev/null | tail -1
```

=============================================================================
FASE 7 — REPORT FINALE
=============================================================================

```
╔══════════════════════════════════════════════════════════════╗
║               REFACTORING AUDIT REPORT                      ║
╠══════════════════════════════════════════════════════════════╣
║ Progetto:           <nome>                                  ║
║ Data:               <data>                                  ║
║ LOC totali (src):   N                                       ║
║ File Python (src):  N                                       ║
║ LOC media/file:     N                                       ║
║ Test/Code ratio:    N%                                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ HEALTH SCORE:  ★★★☆☆  (3/5)                                ║
║                                                              ║
║ METRICHE CHIAVE:                                             ║
║  Complessità media:        A/B/C/D/F                        ║
║  Funzioni complesse (C+):  N                                ║
║  Codice morto stimato:     N LOC (N%)                       ║
║  Duplicazioni trovate:     N blocchi                        ║
║  God Objects (>500 LOC):   N file                           ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ TOP 5 FILE DA REFACTORARE (per impatto):                    ║
║                                                              ║
║  1. path/file.py (N LOC)                                    ║
║     Problemi: God Class, complessità F, N duplicazioni      ║
║     Azione: Split in X moduli + extract Y metodi            ║
║     Effort: Alto / Medio / Basso                            ║
║                                                              ║
║  2. ...                                                      ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ CODE SMELLS PER CATEGORIA:                                   ║
║  God Class/Method:      N                                   ║
║  Feature Envy:          N                                   ║
║  Primitive Obsession:   N                                   ║
║  Magic Numbers:         N                                   ║
║  High Coupling:         N                                   ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ ARCHITETTURA:                                                ║
║  Separazione layer:     ✅ / ⚠️ / ❌                         ║
║  Dipendenze circolari:  Sì (elenco) / No                   ║
║  Single Responsibility: ✅ / ⚠️ / ❌                         ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ PIANO DI AZIONE (ordinato per ROI):                          ║
║                                                              ║
║  Sprint 1 (Quick Wins — basso effort, alto impatto):        ║
║   □ Rimuovere codice morto (N LOC)                          ║
║   □ Estrarre costanti magiche                               ║
║   □ ...                                                      ║
║                                                              ║
║  Sprint 2 (Refactoring mirati):                              ║
║   □ Split God Object X in A, B, C                           ║
║   □ Eliminare duplicazione pattern Y                        ║
║   □ ...                                                      ║
║                                                              ║
║  Sprint 3 (Architettura):                                    ║
║   □ Risolvere dipendenze circolari                          ║
║   □ Introdurre layer X                                      ║
║   □ ...                                                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

=============================================================================
PRINCIPI GUIDA
=============================================================================

1. MISURA PRIMA, OPINA DOPO: Ogni osservazione deve essere supportata
   da una metrica oggettiva (LOC, complessità, conteggio).

2. ROI DEL REFACTORING: Prioritizza per impatto/effort.
   Non tutto il debito tecnico va pagato subito.

3. REFACTORING ≠ REWRITE: Suggerisci cambiamenti incrementali.
   Mai proporre di riscrivere tutto da zero.

4. TESTS FIRST: Prima di refactorare, verifica che esistano test.
   Se non ci sono, il primo passo è scriverli.

5. BOY SCOUT RULE: "Lascia il codice più pulito di come lo hai trovato."
   Non serve un big bang, basta migliorare ogni file che tocchi.
```
