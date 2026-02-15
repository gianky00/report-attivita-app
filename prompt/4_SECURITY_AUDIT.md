# 4 — Security Audit Completo per Progetti Python

> Prompt universale per eseguire un audit di sicurezza approfondito su qualsiasi progetto Python.
> Va oltre Bandit: copre dipendenze, secrets, configurazioni, input validation, OWASP.
> Compatibile con qualsiasi LLM che abbia accesso al filesystem e al terminale.

---

## Prompt

```
Ruolo: Agisci come un Application Security Engineer specializzato in Python.

Contesto: Devo eseguire un audit di sicurezza completo su un progetto Python.
L'audit deve coprire TUTTE le superfici di attacco, non solo il codice sorgente.

Obiettivo: Analizza il progetto, identifica vulnerabilità, classifica per severità,
e produci un report con remediation per ogni finding.

IMPORTANTE: Questo prompt è GENERICO. Adattati al progetto che trovi.

=============================================================================
FASE 0 — RICOGNIZIONE DEL PROGETTO
=============================================================================

Prima di analizzare la sicurezza, comprendi il progetto:

1. LEGGI pyproject.toml / setup.py / requirements.txt:
   - Identifica TUTTE le dipendenze di produzione
   - Identifica la versione Python target
   - Nota eventuali dipendenze pinned a versioni vecchie

2. IDENTIFICA il tipo di applicazione:
   - Web (Flask, Django, FastAPI) → focus su OWASP Top 10 Web
   - Desktop (Tkinter, Qt, CustomTkinter) → focus su file system, credentials
   - CLI → focus su input validation, path traversal
   - Libreria → focus su API surface, input sanitization
   - Data/ML → focus su pickle, eval, data poisoning

3. CERCA file sensibili nel repository:
   ```bash
   # File che NON dovrebbero essere nel repo
   find . -name ".env" -o -name "*.pem" -o -name "*.key" \
          -o -name "credentials*" -o -name "secret*" \
          -o -name "*.p12" -o -name "token*" 2>/dev/null
   ```

4. LEGGI .gitignore:
   - Verifica che .env, *.key, *.pem, credentials siano ignorati
   - Se mancano pattern critici, segnala come HIGH

5. CERCA nella git history eventuali secrets committati per errore:
   ```bash
   git log --all --diff-filter=D --name-only -- "*.env" "*.key" "*.pem" 2>/dev/null
   git log --all -p -- ".env" 2>/dev/null | head -50
   ```

=============================================================================
FASE 1 — DIPENDENZE VULNERABILI
=============================================================================

Le dipendenze sono la superficie di attacco più grande.

1. INSTALLA e usa pip-audit (se non già presente):
   ```bash
   pip install pip-audit
   pip-audit
   ```
   - Controlla CVE note per ogni dipendenza
   - Suggerisci aggiornamenti per dipendenze vulnerabili

2. Analisi ALTERNATIVA con safety (se pip-audit non disponibile):
   ```bash
   pip install safety
   safety check
   ```

3. VERIFICA dipendenze pinned troppo vecchie:
   ```bash
   pip list --outdated
   ```
   - Dipendenze con più di 2 major version di ritardo → MEDIUM
   - Dipendenze non più mantenute → HIGH

4. CONTROLLA dipendenze con typosquatting risk:
   - Nomi simili a pacchetti popolari ma diversi
   - Pacchetti con pochi download/stars

=============================================================================
FASE 2 — SECRETS E CREDENTIALS
=============================================================================

Cerca secrets hardcoded nel codice sorgente. Questo è CRITICO.

1. PATTERN DA CERCARE in tutti i file .py:
   ```bash
   # API keys, tokens, passwords hardcoded
   grep -rnE "(api[_-]?key|apikey|secret|password|passwd|token|auth)\s*=\s*['\"][^'\"]{8,}" src/ --include="*.py"

   # URLs con credenziali embedded
   grep -rnE "https?://[^:]+:[^@]+@" src/ --include="*.py"

   # Base64 encoded strings (possibili secrets offuscati)
   grep -rnE "['\"][A-Za-z0-9+/]{40,}={0,2}['\"]" src/ --include="*.py"

   # Private keys inline
   grep -rnl "BEGIN.*PRIVATE KEY" src/

   # AWS/GCP/Azure credentials
   grep -rnE "(AKIA|GOOG|AZURE|sk-[a-zA-Z0-9]{20,})" src/ --include="*.py"
   ```

2. VERIFICA gestione credenziali:
   - Le credenziali vengono lette da .env / variabili d'ambiente? → OK
   - Sono hardcoded nel codice? → CRITICAL
   - Sono in un file config committato nel repo? → HIGH
   - Esiste .env.example senza valori reali? → BEST PRACTICE

3. VERIFICA che .env sia in .gitignore:
   ```bash
   grep -E "^\.env$|^\.env\." .gitignore
   ```
   Se mancante → CRITICAL

4. CERCA config files con secrets:
   ```bash
   # JSON config con possibili secrets
   grep -rnE "(key|secret|password|token)" . --include="*.json" | grep -v node_modules | grep -v .git
   ```

=============================================================================
FASE 3 — ANALISI STATICA SICUREZZA (Bandit)
=============================================================================

Bandit è il tool standard per security linting Python.

1. ESEGUI Bandit con report dettagliato:
   ```bash
   bandit -r src/ -f json -o bandit_report.json 2>/dev/null
   bandit -r src/ -ll  # Solo HIGH e MEDIUM
   ```

2. CLASSIFICAZIONE dei finding Bandit:

   Severity HIGH (da correggere):
   - B301/B302: pickle usage (deserializzazione arbitraria)
   - B303: MD5/SHA1 per sicurezza (hash deboli)
   - B306: mktemp (race condition)
   - B307: eval() (code injection)
   - B308: mark_safe in Django (XSS)
   - B320: xml parsing (XXE)
   - B501: ssl no verify (MitM)
   - B602: subprocess shell=True (command injection)
   - B608: SQL injection (string formatting in query)

   Severity MEDIUM (da valutare):
   - B110: try-except-pass (errori silenziati)
   - B311: random (non crittografico)
   - B324: hashlib senza usedforsecurity=False
   - B506: yaml.load senza Loader (code execution)

   Falsi Positivi Comuni (da ignorare con commento):
   - B101: assert (OK nei test)
   - B404: import subprocess (legittimo se usato correttamente)
   - B603: subprocess senza shell (OK se input validato)

3. Per ogni finding HIGH/MEDIUM, verifica:
   - È raggiungibile da input utente? → CRITICAL
   - È in codice di test? → FALSE POSITIVE (ignora)
   - È mitigato da validazione a monte? → MEDIUM→LOW

=============================================================================
FASE 4 — INPUT VALIDATION E INJECTION
=============================================================================

1. CERCA punti di input utente:
   - Form GUI (Entry, Text widget)
   - Argomenti CLI (argparse, sys.argv)
   - File letti dall'utente (open, Path)
   - API request/response
   - Database query con input utente

2. Per ogni punto di input, verifica:

   a. SQL INJECTION:
      ```bash
      # String formatting in query SQL
      grep -rnE "(execute|raw|text)\s*\(.*(%s|\.format|f['\"])" src/ --include="*.py"
      # Concatenazione stringhe in query
      grep -rnE "\".*SELECT.*\"\s*\+" src/ --include="*.py"
      ```
      Remediation: usare SEMPRE query parametrizzate o ORM

   b. COMMAND INJECTION:
      ```bash
      # subprocess con shell=True e variabili
      grep -rnE "subprocess\.(call|run|Popen).*shell\s*=\s*True" src/ --include="*.py"
      # os.system (sempre vulnerabile)
      grep -rn "os\.system" src/ --include="*.py"
      ```
      Remediation: usare subprocess con lista di argomenti, mai shell=True

   c. PATH TRAVERSAL:
      ```bash
      # open() con input non sanitizzato
      grep -rnE "open\s*\(.*\+|open\s*\(.*format|open\s*\(.*f['\"]" src/ --include="*.py"
      ```
      Remediation: usare Path.resolve() e verificare che il path sia dentro la directory attesa

   d. DESERIALIZATION:
      ```bash
      # pickle (code execution arbitrario)
      grep -rn "pickle\.\(load\|loads\)" src/ --include="*.py"
      # yaml senza SafeLoader
      grep -rn "yaml\.load\b" src/ --include="*.py" | grep -v "SafeLoader\|safe_load"
      # eval/exec
      grep -rnE "\b(eval|exec)\s*\(" src/ --include="*.py"
      ```
      Remediation: mai deserializzare dati non fidati, usare json, yaml.safe_load

=============================================================================
FASE 5 — RETE E COMUNICAZIONI
=============================================================================

1. CERCA chiamate HTTP/HTTPS:
   ```bash
   grep -rnE "(requests\.(get|post|put|delete|patch)|urllib|http\.client)" src/ --include="*.py"
   ```

2. Per ogni chiamata HTTP verifica:
   - verify=False in requests? → HIGH (disabilita verifica SSL)
   - Timeout specificato? → Se manca, rischio di hang infinito
   - Risposta validata prima dell'uso? → Se no, rischio injection
   - URL costruita con input utente? → Se sì, rischio SSRF

3. CERCA connessioni database:
   ```bash
   grep -rnE "(connect|create_engine|sessionmaker)" src/ --include="*.py"
   ```
   - Connection string con password in chiaro? → HIGH
   - SSL/TLS abilitato per connessioni remote? → Verifica

4. CERCA WebSocket, gRPC, o altri protocolli:
   ```bash
   grep -rnE "(websocket|grpc|socket\.)" src/ --include="*.py"
   ```

=============================================================================
FASE 6 — FILE SYSTEM E PERMESSI
=============================================================================

1. FILE TEMPORANEI:
   ```bash
   grep -rnE "(tempfile|mktemp|/tmp/)" src/ --include="*.py"
   ```
   - Usa tempfile.mkstemp() o NamedTemporaryFile, MAI mktemp()
   - I file temporanei vengono eliminati dopo l'uso?

2. PERMESSI FILE:
   ```bash
   grep -rnE "(os\.chmod|os\.chown|0o777|0o666)" src/ --include="*.py"
   ```
   - Permessi troppo aperti (777, 666) → MEDIUM

3. LOG E OUTPUT:
   ```bash
   grep -rnE "(logging\.|\.log\(|print\()" src/ --include="*.py" | grep -iE "(password|secret|token|key|credential)"
   ```
   - Credentials nei log → HIGH
   - Stack trace con info sensibili esposti all'utente → MEDIUM

=============================================================================
FASE 7 — REPORT FINALE
=============================================================================

Produci il report con questo formato:

```
╔══════════════════════════════════════════════════════════════╗
║                 SECURITY AUDIT REPORT                       ║
╠══════════════════════════════════════════════════════════════╣
║ Progetto:          <nome>                                   ║
║ Data:              <data>                                   ║
║ Python:            <versione>                               ║
║ Tipo applicazione: <web/desktop/cli/lib>                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ RIEPILOGO                                                    ║
║  🔴 CRITICAL:  N                                             ║
║  🟠 HIGH:      N                                             ║
║  🟡 MEDIUM:    N                                             ║
║  🟢 LOW:       N                                             ║
║  ⚪ INFO:      N                                             ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║ FINDING #1                                                   ║
║ Severity: CRITICAL / HIGH / MEDIUM / LOW                     ║
║ Categoria: Secrets / Injection / Dependencies / Config       ║
║ File: percorso/file.py:riga                                  ║
║ Descrizione: <cosa è stato trovato>                          ║
║ Rischio: <cosa potrebbe succedere se sfruttato>              ║
║ Remediation: <come correggere>                               ║
║ Riferimento: CWE-XXX / OWASP-XXX                            ║
╠══════════════════════════════════════════════════════════════╣
║ ... (ripeti per ogni finding) ...                            ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║ DIPENDENZE VULNERABILI (da pip-audit):                       ║
║  - <pacchetto> <versione> → CVE-XXXX (severity)             ║
║  - ...                                                       ║
║                                                              ║
║ AZIONI PRIORITARIE (top 5):                                  ║
║  1. <azione più urgente>                                     ║
║  2. ...                                                      ║
║  3. ...                                                      ║
║  4. ...                                                      ║
║  5. ...                                                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

=============================================================================
CLASSIFICAZIONE SEVERITÀ
=============================================================================

CRITICAL: Sfruttabile da remoto senza autenticazione, impatto totale.
          Secrets esposti, RCE, SQL injection su endpoint pubblico.

HIGH:     Sfruttabile con interazione minima, impatto significativo.
          Credenziali in chiaro, SSL disabilitato, dipendenza con CVE critica.

MEDIUM:   Sfruttabile in condizioni specifiche, impatto limitato.
          Input validation debole, permessi file troppo aperti, hash deboli.

LOW:      Rischio teorico, difficile da sfruttare, impatto minimo.
          Info disclosure in log, assert in produzione, random non crypto.

INFO:     Best practice non rispettate, nessun rischio diretto.
          Manca .env.example, manca security policy, manca rate limiting.

=============================================================================
PRINCIPI GUIDA
=============================================================================

1. ZERO FALSE CONFIDENCE: Non dire "il progetto è sicuro" se non hai
   controllato tutto. Dì "non ho trovato vulnerabilità nelle aree analizzate".

2. CONTEXT MATTERS: eval() in un template engine è diverso da eval() su
   input utente. Valuta sempre il contesto.

3. DEFENSE IN DEPTH: Una singola protezione non basta. Cerca layered security.

4. LEAST PRIVILEGE: Ogni componente dovrebbe avere i permessi minimi necessari.

5. REMEDIATION SEMPRE: Ogni finding DEVE avere una remediation concreta
   con esempio di codice corretto.
```
