# 6 — Refactoring e Modularizzazione Industriale per Progetti Python

> Prompt universale per eseguire refactoring e modularizzazione di un progetto Python
> secondo standard industriali dell'ingegneria del software (SOLID, Clean Architecture,
> Design Patterns, Martin Fowler's Refactoring Catalog).
> Complementare a `4_REFACTORING_AUDIT.md` (che analizza) — questo prompt ESEGUE.
> Compatibile con qualsiasi LLM che abbia accesso al filesystem e al terminale.

---

## Prompt

```
Ruolo: Agisci come un Senior Software Engineer specializzato in refactoring industriale,
Clean Architecture e design patterns applicati a Python.

Contesto: Devo eseguire un refactoring strutturale di un progetto Python.
Il refactoring deve seguire i principi SOLID, i pattern del catalogo di Fowler,
e le best practice di modularizzazione Python. Ogni modifica deve essere incrementale,
sicura e verificabile.

Obiettivo: Analizza il progetto, progetta la nuova architettura modulare, e guida
il refactoring passo per passo — preservando SEMPRE il comportamento esistente.

IMPORTANTE: Questo prompt è GENERICO. Adattati al progetto che trovi.

=============================================================================
REGOLA ZERO — PRESERVARE IL COMPORTAMENTO
=============================================================================

PRIMA di toccare qualsiasi riga di codice:

1. ESEGUI i test esistenti e salva il risultato come baseline:
   ```bash
   pytest --tb=short -q 2>&1 | tee baseline_tests.txt
   ```

2. SE non ci sono test sufficienti, SCRIVI characterization test:
   - Un characterization test cattura il comportamento ATTUALE (anche se sbagliato)
   - Serve come rete di sicurezza durante il refactoring
   - Formato: chiama la funzione con input noti, assert sul risultato attuale

   ```python
   def test_characterize_funzione_X():
       """Characterization test: cattura comportamento attuale."""
       risultato = funzione_X(input_noto)
       assert risultato == <valore_attuale>  # Scoperto empiricamente
   ```

3. DOPO OGNI SINGOLA modifica di refactoring:
   ```bash
   pytest --tb=short -q
   ```
   Se un test fallisce → la modifica ha rotto qualcosa → ROLLBACK immediato.

4. MAI refactoring + nuove feature nella stessa modifica.
   - Commit di refactoring: cambiano la struttura, NON il comportamento
   - Commit di feature: cambiano il comportamento
   - Mescolarli rende impossibile identificare le regressioni

=============================================================================
FASE 1 — ANALISI ARCHITETTURALE (AS-IS)
=============================================================================

1. MAPPA il grafo delle dipendenze:
   ```bash
   # Tutti gli import interni del progetto
   grep -rnE "^from (src|<package>)\.|^import (src|<package>)\." src/ --include="*.py" | \
     awk -F: '{print $1 " → " $2}' | sort
   ```

   Disegna mentalmente il grafo:
   ```
   modulo_A → modulo_B → modulo_C
              modulo_B → modulo_D
   modulo_A → modulo_D              (dipendenza transitiva OK)
   modulo_C → modulo_A              ← CICLO! Problema architetturale
   ```

2. IDENTIFICA i layer attuali (anche se impliciti):
   - Presentation / GUI / CLI
   - Business Logic / Domain
   - Data Access / Repository
   - Infrastructure / Integrations
   - Utilities / Shared

3. MISURA la dimensione di ogni modulo:
   ```bash
   find src/ -name "*.py" -exec wc -l {} + | sort -rn
   ```

   Classifica:
   - < 200 LOC:  Modulo focalizzato ✅
   - 200-400 LOC: Modulo accettabile, monitorare
   - 400-600 LOC: Candidato per split
   - > 600 LOC:  Split necessario — probabilmente viola SRP

4. PER OGNI file > 400 LOC, rispondi:
   - Quante "responsabilità" diverse ha?
   - Posso descriverlo con UNA frase senza "e" / "anche" / "inoltre"?
   - Se no → viola Single Responsibility → va diviso

=============================================================================
FASE 2 — PRINCIPI SOLID APPLICATI A PYTHON
=============================================================================

Per ogni principio, analizza il codice e identifica violazioni concrete.

────────────────────────────────────────────────────────────────
S — Single Responsibility Principle (SRP)
────────────────────────────────────────────────────────────────

"Una classe/modulo deve avere uno e un solo motivo per cambiare."

VIOLAZIONI COMUNI in Python:
- File che contiene GUI + logica + accesso dati
- Classe che fa parsing, calcolo e rendering
- Funzione che valida input, elabora E salva il risultato

COME CORREGGERE:
1. Identifica le N responsabilità nel modulo
2. Crea N moduli/classi, ognuno con UNA responsabilità
3. Collega con dependency injection (parametri, non import globali)

Pattern di split:
```
PRIMA:                          DOPO:
manager.py (800 LOC)           parser.py (120 LOC)      — parsing
  - parsing                    calculator.py (150 LOC)  — calcolo
  - calcolo                    repository.py (130 LOC)  — persistenza
  - salvataggio DB             formatter.py (80 LOC)    — formattazione
  - formattazione output       manager.py (100 LOC)     — orchestrazione
```

────────────────────────────────────────────────────────────────
O — Open/Closed Principle (OCP)
────────────────────────────────────────────────────────────────

"Aperto per estensione, chiuso per modifica."

VIOLAZIONI COMUNI:
- Catene if/elif per gestire tipi diversi
- Switch su stringhe per selezionare comportamento
- Funzione che cresce ogni volta che si aggiunge un caso

COME CORREGGERE:
```python
# ❌ PRIMA: Ogni nuovo tipo richiede modifica
def processa(tipo, dati):
    if tipo == "A":
        return logica_a(dati)
    elif tipo == "B":
        return logica_b(dati)
    elif tipo == "C":  # Aggiunto dopo
        return logica_c(dati)

# ✅ DOPO: Strategy pattern — estensibile senza modifica
STRATEGIES: dict[str, Callable] = {
    "A": logica_a,
    "B": logica_b,
    "C": logica_c,
}

def processa(tipo: str, dati: Any) -> Any:
    strategy = STRATEGIES.get(tipo)
    if strategy is None:
        raise ValueError(f"Tipo sconosciuto: {tipo}")
    return strategy(dati)
```

Oppure con Protocol/ABC per casi più complessi:
```python
from typing import Protocol

class Processor(Protocol):
    def process(self, data: Any) -> Result: ...

class ProcessorA:
    def process(self, data: Any) -> Result: ...

class ProcessorB:
    def process(self, data: Any) -> Result: ...
```

────────────────────────────────────────────────────────────────
L — Liskov Substitution Principle (LSP)
────────────────────────────────────────────────────────────────

"Le sottoclassi devono essere sostituibili alla classe base."

VIOLAZIONI COMUNI:
- Sottoclasse che lancia NotImplementedError su un metodo della base
- Override che cambia la semantica (es. add() che sottrae)
- Sottoclasse che richiede precondizioni più strette

COME VERIFICARE:
```bash
grep -rn "NotImplementedError\|raise NotImplemented" src/ --include="*.py"
```
Se trovati in una sottoclasse → probabilmente viola LSP.
Soluzione: usare composizione invece di ereditarietà, oppure ABC.

────────────────────────────────────────────────────────────────
I — Interface Segregation Principle (ISP)
────────────────────────────────────────────────────────────────

"Nessun client dovrebbe dipendere da metodi che non usa."

IN PYTHON si applica con Protocol (typing) invece di interface Java:

```python
# ❌ PRIMA: Interfaccia grassa — chi legge non ha bisogno di write
class DataStore(ABC):
    def read(self, key): ...
    def write(self, key, value): ...
    def delete(self, key): ...
    def list_keys(self): ...

# ✅ DOPO: Protocol segregati
class Readable(Protocol):
    def read(self, key: str) -> Any: ...

class Writable(Protocol):
    def write(self, key: str, value: Any) -> None: ...

# Il client dichiara SOLO ciò che usa
def report_generator(store: Readable) -> Report:
    data = store.read("metrics")
    ...
```

────────────────────────────────────────────────────────────────
D — Dependency Inversion Principle (DIP)
────────────────────────────────────────────────────────────────

"I moduli di alto livello non devono dipendere da moduli di basso livello.
 Entrambi devono dipendere da astrazioni."

VIOLAZIONE TIPICA in Python:
```python
# ❌ La logica business importa direttamente il database
# logic/analytics.py
from data.database import DatabaseManager

class Analytics:
    def __init__(self):
        self.db = DatabaseManager()  # Accoppiamento diretto!
```

CORREZIONE con Dependency Injection:
```python
# ✅ La logica business riceve la dipendenza dall'esterno
# logic/analytics.py
from typing import Protocol

class DataReader(Protocol):
    def get_records(self, date_range: tuple) -> list[dict]: ...

class Analytics:
    def __init__(self, data_source: DataReader):
        self.data_source = data_source

# Nell'entry point (main.py / composition root):
db = DatabaseManager()
analytics = Analytics(data_source=db)  # DatabaseManager implementa DataReader
```

=============================================================================
FASE 3 — CATALOGO REFACTORING (Martin Fowler)
=============================================================================

Applica queste tecniche nell'ordine, dalla più semplice alla più complessa.
Ogni tecnica è un SINGOLO commit atomico.

────────────────────────────────────
3.1 — EXTRACT METHOD
────────────────────────────────────
Quando: Funzione > 20 LOC, o blocco con commento "# fai X"
```python
# PRIMA
def processo_complesso(dati):
    # Validazione
    if not dati: raise ValueError()
    if dati.tipo not in TIPI_VALIDI: raise ValueError()

    # Calcolo
    risultato = 0
    for item in dati.items:
        risultato += item.valore * coefficiente(item)

    # Formattazione
    return f"{risultato:.2f}%"

# DOPO
def processo_complesso(dati):
    _valida(dati)
    risultato = _calcola(dati)
    return _formatta(risultato)

def _valida(dati): ...
def _calcola(dati) -> float: ...
def _formatta(valore: float) -> str: ...
```

────────────────────────────────────
3.2 — EXTRACT CLASS
────────────────────────────────────
Quando: Classe con > 2 responsabilità o > 15 metodi
```python
# PRIMA: UserManager gestisce autenticazione + profilo + notifiche
class UserManager:
    def login(self): ...
    def logout(self): ...
    def update_profile(self): ...
    def get_profile(self): ...
    def send_notification(self): ...
    def get_notifications(self): ...

# DOPO: 3 classi con responsabilità singola
class Authenticator:
    def login(self): ...
    def logout(self): ...

class ProfileManager:
    def update(self): ...
    def get(self): ...

class NotificationService:
    def send(self): ...
    def list(self): ...
```

────────────────────────────────────
3.3 — EXTRACT MODULE
────────────────────────────────────
Quando: File > 400 LOC con sezioni logicamente separate.
Procedura SICURA:

1. Identifica le sezioni (classi/funzioni raggruppabili per responsabilità)
2. Crea il nuovo file con le classi/funzioni da spostare
3. Nel file originale, importa dal nuovo file e ri-esporta:
   ```python
   # vecchio.py — fase transitoria
   from nuovo_modulo import ClasseSpostata  # re-export per compatibilità
   ```
4. Aggiorna tutti i file che importavano da vecchio.py
5. Rimuovi il re-export dal file originale
6. Esegui test dopo OGNI passo

────────────────────────────────────
3.4 — REPLACE CONDITIONAL WITH POLYMORPHISM
────────────────────────────────────
Quando: if/elif con > 3 rami che fanno operazioni diverse sullo stesso concetto

────────────────────────────────────
3.5 — INTRODUCE PARAMETER OBJECT
────────────────────────────────────
Quando: Funzione con > 4 parametri correlati
```python
# PRIMA
def crea_report(nome, cognome, email, telefono, indirizzo, cap):
    ...

# DOPO
@dataclass
class Contatto:
    nome: str
    cognome: str
    email: str
    telefono: str
    indirizzo: str
    cap: str

def crea_report(contatto: Contatto):
    ...
```

────────────────────────────────────
3.6 — REPLACE MAGIC NUMBERS/STRINGS WITH CONSTANTS
────────────────────────────────────
```python
# PRIMA
if pressione > 140:
    return "alto"

# DOPO
SOGLIA_PRESSIONE_ALTA = 140
STATUS_ALTO = "alto"

if pressione > SOGLIA_PRESSIONE_ALTA:
    return STATUS_ALTO
```
Per set fissi di valori, preferire Enum:
```python
class PressioneStatus(Enum):
    NORMALE = "normale"
    ALTO = "alto"
    CRITICO = "critico"
```

────────────────────────────────────
3.7 — REPLACE INHERITANCE WITH COMPOSITION
────────────────────────────────────
Quando: Ereditarietà usata solo per riutilizzare codice, senza relazione "is-a".
```python
# ❌ PRIMA: Widget eredita da DataLoader solo per usare load()
class DashboardWidget(DataLoader, Renderer):
    ...

# ✅ DOPO: Composizione — Widget USA un DataLoader
class DashboardWidget:
    def __init__(self, loader: DataLoader, renderer: Renderer):
        self.loader = loader
        self.renderer = renderer
```

=============================================================================
FASE 4 — ARCHITETTURA MODULARE TARGET (TO-BE)
=============================================================================

Progetta la struttura modulare target. Ogni progetto Python dovrebbe tendere
a questa organizzazione (adattala al contesto):

```
project/
├── src/
│   ├── __init__.py
│   │
│   ├── domain/              # Layer 1: Logica di dominio PURA
│   │   ├── __init__.py      # (nessuna dipendenza esterna)
│   │   ├── models.py        # Entità, Value Objects, dataclass
│   │   ├── rules.py         # Regole di business
│   │   ├── calculators.py   # Algoritmi e calcoli
│   │   └── exceptions.py    # Eccezioni di dominio
│   │
│   ├── application/         # Layer 2: Use Cases / Servizi applicativi
│   │   ├── __init__.py      # (orchestra domain + ports)
│   │   ├── services.py      # Servizi che implementano i use case
│   │   └── ports.py         # Protocol/ABC — interface verso l'esterno
│   │
│   ├── infrastructure/      # Layer 3: Implementazioni concrete
│   │   ├── __init__.py      # (database, API, file system)
│   │   ├── database.py      # Repository concreto (SQLAlchemy, ecc.)
│   │   ├── api_client.py    # Client API esterne
│   │   ├── file_storage.py  # Lettura/scrittura file
│   │   └── migrations.py    # Migrazioni schema DB
│   │
│   ├── presentation/        # Layer 4: Interfaccia utente
│   │   ├── __init__.py      # (GUI, CLI, Web)
│   │   ├── app.py           # Entry point GUI/CLI
│   │   ├── views.py         # Layout, widget, pagine
│   │   ├── controllers.py   # Gestione eventi UI → servizi
│   │   └── formatters.py    # Formattazione dati per la UI
│   │
│   └── shared/              # Utility condivise (cross-cutting)
│       ├── __init__.py
│       ├── config.py        # Configurazione applicazione
│       ├── logging.py       # Setup logging
│       └── constants.py     # Costanti globali
│
├── tests/
│   ├── conftest.py
│   ├── domain/              # Specchia la struttura src/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
│
└── pyproject.toml
```

REGOLA DELLE DIPENDENZE (Dependency Rule):
```
presentation → application → domain     ✅ Corretto
presentation → domain                   ✅ OK (skip di layer)
domain → infrastructure                 ❌ VIETATO
domain → presentation                   ❌ VIETATO
infrastructure → domain                 ✅ OK (implementa ports)
application → infrastructure            ❌ VIETATO (usa ports)
```

Il domain layer NON DEVE importare nulla dagli altri layer.
Se il domain ha bisogno di dati esterni, dichiara un Protocol in ports.py
e l'infrastructure lo implementa.

NOTA: Questa è l'architettura target IDEALE. Per progetti piccoli/medi
è accettabile semplificare a 3 layer (presentation / logic / data)
mantenendo la regola delle dipendenze.

=============================================================================
FASE 5 — DESIGN PATTERNS PYTHON (quando usarli)
=============================================================================

Usa un pattern SOLO quando risolve un problema concreto. Mai "perché è elegante."

PATTERN              │ QUANDO USARLO                        │ PYTHON IDIOMATICO
─────────────────────┼──────────────────────────────────────┼──────────────────
Strategy             │ Algoritmo intercambiabile             │ Dict[str, Callable]
Observer             │ Notificare N listener di un evento    │ callbacks list
Factory              │ Creazione oggetti con logica          │ classmethod / funzione
Facade               │ API semplice su sottosistema complesso│ Classe wrapper
Template Method      │ Algoritmo fisso, passi variabili      │ ABC + sottoclassi
Decorator            │ Aggiungere comportamento              │ @decorator nativo
Repository           │ Astrarre accesso dati                 │ Protocol + classe
Builder              │ Costruzione oggetti complessi         │ @dataclass + metodi
Singleton            │ Istanza unica (raro in Python)        │ variabile di modulo
Adapter              │ Interfaccia incompatibile             │ Classe wrapper

ANTI-PATTERN DA EVITARE:
- Singleton ovunque → usa dependency injection
- Abstract Factory per 2 casi → basta un if
- Observer per 1 listener → basta un callback
- Strategy per 2 varianti → basta un parametro bool

REGOLA: Se il pattern aggiunge più codice di quello che semplifica, NON usarlo.

=============================================================================
FASE 6 — PROCEDURA DI REFACTORING INCREMENTALE
=============================================================================

MAI refactoring big-bang. SEMPRE incrementale.

METODO STRANGLER FIG (per moduli grandi):

1. CREA il nuovo modulo accanto al vecchio
2. SPOSTA una funzione/classe alla volta nel nuovo modulo
3. Nel vecchio modulo, importa e ri-esporta dalla nuova posizione
4. AGGIORNA i client uno alla volta
5. Quando il vecchio modulo è vuoto (solo re-export), eliminalo

```
Iterazione 1:
  old_module.py  (800 LOC)  →  new_parser.py (150 LOC) + old_module.py (650 LOC)

Iterazione 2:
  old_module.py  (650 LOC)  →  new_calculator.py (200 LOC) + old_module.py (450 LOC)

Iterazione 3:
  old_module.py  (450 LOC)  →  new_repository.py (180 LOC) + old_module.py (270 LOC)

Iterazione 4:
  old_module.py  (270 LOC)  →  new_formatter.py (100 LOC) + orchestrator.py (170 LOC)
  old_module.py  ELIMINATO ✅
```

CHECKLIST PER OGNI ITERAZIONE:
  □ Test verdi PRIMA della modifica
  □ Sposta UNA responsabilità alla volta
  □ Re-export temporaneo per non rompere i client
  □ Test verdi DOPO la modifica
  □ Commit atomico con messaggio descrittivo
  □ Aggiorna import nei client
  □ Test verdi dopo aggiornamento client
  □ Rimuovi re-export quando tutti i client sono aggiornati

=============================================================================
FASE 7 — METRICHE DI QUALITÀ (before/after)
=============================================================================

Misura PRIMA e DOPO ogni sprint di refactoring:

```bash
# 1. LOC per file (i file grandi devono diminuire)
find src/ -name "*.py" -exec wc -l {} + | sort -rn | head -15

# 2. Complessità ciclomatica (deve diminuire)
radon cc src/ -a -s -n C

# 3. Maintainability Index (deve aumentare)
radon mi src/ -s -n B

# 4. Numero di import per file (coupling — deve diminuire)
for f in $(find src/ -name "*.py"); do
  count=$(grep -cE "^(from|import) " "$f" 2>/dev/null)
  echo "$count $f"
done | sort -rn | head -15

# 5. Test coverage (non deve diminuire MAI)
pytest --cov=src --cov-report=term-missing -q

# 6. Codice morto (deve diminuire)
vulture src/ --min-confidence 80 2>/dev/null | wc -l
```

Formato tabella comparativa:
```
Metrica                    │ Prima   │ Dopo    │ Delta
───────────────────────────┼─────────┼─────────┼──────
File > 500 LOC             │ 5       │ 1       │ -4 ✅
LOC max singolo file       │ 1,200   │ 380     │ -68% ✅
Complessità media          │ C (12)  │ B (7)   │ -42% ✅
Funzioni complessità D+    │ 8       │ 1       │ -7 ✅
Maintainability Index avg  │ 45      │ 72      │ +60% ✅
Import medi per file       │ 12      │ 6       │ -50% ✅
Test coverage              │ 65%     │ 68%     │ +3% ✅
Codice morto (vulture)     │ 45      │ 12      │ -73% ✅
```

=============================================================================
FASE 8 — REPORT FINALE
=============================================================================

```
╔══════════════════════════════════════════════════════════════╗
║          REFACTORING EXECUTION REPORT                       ║
╠══════════════════════════════════════════════════════════════╣
║ Progetto:           <nome>                                  ║
║ Data:               <data>                                  ║
║ Sprint:             N di M                                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ PRINCIPI SOLID — STATO:                                     ║
║  S - Single Responsibility:  ✅ / ⚠️ / ❌                    ║
║  O - Open/Closed:            ✅ / ⚠️ / ❌                    ║
║  L - Liskov Substitution:    ✅ / ⚠️ / ❌                    ║
║  I - Interface Segregation:  ✅ / ⚠️ / ❌                    ║
║  D - Dependency Inversion:   ✅ / ⚠️ / ❌                    ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ MODULI CREATI / MODIFICATI:                                  ║
║                                                              ║
║  [NEW] src/domain/calculators.py (150 LOC)                  ║
║    ← Estratto da src/old_manager.py                         ║
║    Responsabilità: calcoli di dominio puri                  ║
║                                                              ║
║  [NEW] src/infrastructure/repository.py (130 LOC)           ║
║    ← Estratto da src/old_manager.py                         ║
║    Responsabilità: persistenza dati                         ║
║                                                              ║
║  [MOD] src/old_manager.py: 800 → 170 LOC (-79%)            ║
║    Ora è solo orchestrazione                                ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ DESIGN PATTERNS APPLICATI:                                   ║
║  - Strategy: src/domain/rules.py (sostituisce if/elif)      ║
║  - Facade: src/application/services.py                      ║
║  - Repository: src/infrastructure/database.py               ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ METRICHE BEFORE / AFTER:                                     ║
║  (tabella comparativa come in Fase 7)                       ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ TEST:                                                        ║
║  Prima: N test, N% coverage                                ║
║  Dopo:  N test, N% coverage                                ║
║  Regressioni: 0 ✅                                           ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ DEBITO TECNICO RESIDUO:                                      ║
║  □ <cosa resta da fare nel prossimo sprint>                 ║
║  □ ...                                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

=============================================================================
PRINCIPI GUIDA
=============================================================================

1. REFACTORING ≠ REWRITE: Non riscrivere mai da zero.
   Migliora incrementalmente. Il codice che funziona ha valore.

2. COMMIT ATOMICI: Ogni commit fa UNA cosa. "Extract ClasseX da modulo.py"
   non "Refactoring generale del modulo". Se qualcosa si rompe, il rollback
   è chirurgico, non una bomba nucleare.

3. TEST PRIMA DI TUTTO: Niente test = niente refactoring.
   Se non ci sono test, il primo refactoring è scrivere i test.

4. YAGNI: Non progettare per il futuro ipotetico.
   Refactora per i problemi di OGGI. Il futuro avrà i suoi problemi.

5. REGOLA DEL TRE: La prima volta scrivi. La seconda copi.
   La TERZA volta refactora. Non astrarre troppo presto.

6. MISURA SEMPRE: Senza metriche before/after non puoi dimostrare
   che il refactoring ha migliorato qualcosa. Misura, refactora, misura.

7. STRANGLER FIG > BIG BANG: Sostituisci pezzo per pezzo.
   Il vecchio e il nuovo coesistono fino alla migrazione completa.

8. DIREZIONE DELLE DIPENDENZE: Le dipendenze puntano SEMPRE
   verso l'interno (verso il dominio). Mai il dominio dipende
   dall'infrastruttura. Questa è la regola che tiene in piedi tutto.
```
