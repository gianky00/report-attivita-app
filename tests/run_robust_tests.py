import argparse
import datetime
import io
import json
import os
import signal
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

# --- AGGIUNTA PATH PER ARCHITETTURA PROGETTO ---
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from core.logging import get_logger
    HAS_ENTERPRISE_LOGGING = True
except ImportError:
    HAS_ENTERPRISE_LOGGING = False
# ------------------------------------------------

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

STATE_FILE = Path(__file__).parent / ".test_session_state.json"
REPORT_FILE = Path(__file__).parent / "test_report.md"
DEFAULT_TIMEOUT = 120

class Console:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"

    @staticmethod
    def print(msg, color=ENDC, end="\n"):
        print(f"{color}{msg}{Console.ENDC}", end=end, flush=True)

    @staticmethod
    def info(msg): Console.print(f"ℹ️  {msg}", Console.CYAN)
    @staticmethod
    def success(msg): Console.print(f"✅ {msg}", Console.GREEN)
    @staticmethod
    def warning(msg): Console.print(f"⚠️  {msg}", Console.WARNING)
    @staticmethod
    def error(msg): Console.print(f"❌ {msg}", Console.FAIL)
    @staticmethod
    def header(msg): Console.print(f"\n{Console.BOLD}{msg}{Console.ENDC}", Console.HEADER)

class TestRunner:
    def __init__(self):
        self.failed_tests = []
        self.passed_tests = 0
        self.queue_files = []
        self.interrupted = False
        self.start_time = 0
        
        if HAS_ENTERPRISE_LOGGING:
            self.logger = get_logger("test_runner")
        else:
            self.logger = None

        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        if not self.interrupted:
            self.interrupted = True
            Console.warning("\n🛑 Interrupt ricevuto! Salvataggio stato...")
            self.save_state()
            self.generate_report(time.time() - self.start_time)
            sys.exit(130)

    def save_state(self):
        state = {
            "queue": self.queue_files,
            "failed": self.failed_tests,
            "passed": self.passed_tests,
            "timestamp": time.time(),
        }
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def run_tests(self, resume=False):
        Console.header("🚀 AVVIO SUITE DI TEST ROBUSTA (STOP-ON-FAIL)")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_DIR) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")

        state = self.load_state() if resume else None
        
        if state and state.get("queue"):
            Console.info(f"Ripresa sessione precedente ({len(state['queue'])} file rimanenti)")
            self.queue_files = state["queue"]
            self.failed_tests = state.get("failed", [])
            self.passed_tests = state.get("passed", 0)
        else:
            test_dir = ROOT_DIR / "tests"
            self.queue_files = sorted([str(p.relative_to(ROOT_DIR)) for p in test_dir.rglob("test_*.py")])
            self.failed_tests = []
            self.passed_tests = 0
            Console.info(f"Rilevati {len(self.queue_files)} file di test.")

        self.start_time = time.time()
        
        while self.queue_files:
            test_file = self.queue_files[0]
            current_total = self.passed_tests + len(self.failed_tests) + len(self.queue_files)
            current_progress = self.passed_tests + len(self.failed_tests) + 1
            
            Console.print(f"[{current_progress}/{current_total}] Esecuzione: {test_file}...", end=" ")
            
            cmd = [sys.executable, "-m", "pytest", test_file, "-q", "--no-header"]
            
            try:
                result = subprocess.run(
                    cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=ROOT_DIR,
                    timeout=DEFAULT_TIMEOUT
                )
                
                if result.returncode == 0:
                    Console.success("PASS")
                    self.passed_tests += 1
                    # Se il test era fallito in precedenza, lo rimuoviamo dai fallimenti
                    self.failed_tests = [f for f in self.failed_tests if f["file"] != test_file]
                    self.queue_files.pop(0)
                    self.save_state()
                else:
                    Console.error("FAIL")
                    # Aggiorna o aggiunge il fallimento
                    existing = next((f for f in self.failed_tests if f["file"] == test_file), None)
                    if existing:
                        existing["output"] = result.stdout
                    else:
                        self.failed_tests.append({"file": test_file, "output": result.stdout})
                    
                    self.save_state()
                    self.generate_report(time.time() - self.start_time)
                    Console.warning(f"\n🛑 Interruzione per fallimento. Risolvi l'errore in: {test_file}")
                    Console.info("Usa --resume per ripartire dopo il fix.")
                    return

            except subprocess.TimeoutExpired:
                Console.error("TIMEOUT")
                self.failed_tests.append({"file": test_file, "output": "Timeout expired."})
                self.save_state()
                self.generate_report(time.time() - self.start_time)
                return
            except Exception as e:
                Console.error(f"ERRORE: {e}")
                self.save_state()
                return

        # Fine suite con successo
        Console.success("\n✨ Suite completata con successo!")
        self.generate_report(time.time() - self.start_time)
        if STATE_FILE.exists():
            STATE_FILE.unlink()

    def generate_report(self, duration):
        total_executed = self.passed_tests + len(self.failed_tests)
        total_remaining = len(self.queue_files)
        
        report = [
            "# Test Session Report (Stop-on-Fail Mode)",
            f"**Data:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Durata sessione:** {duration:.2f}s",
            f"**Test Passati:** {self.passed_tests}",
            f"**Test Falliti:** {len(self.failed_tests)}",
            f"**Test Rimanenti:** {total_remaining}",
            "\n## Stato Fallimenti"
        ]
        
        if not self.failed_tests:
            report.append("✅ Nessun fallimento registrato nell'ultima esecuzione.")
        else:
            for fail in self.failed_tests:
                report.append(f"### ❌ {fail['file']}")
                report.append(f"```\n{fail['output']}\n```")
        
        if total_remaining > 0:
            report.append(f"\n## Prossimo test in coda: `{self.queue_files[0]}`")
            
        REPORT_FILE.write_text("\n".join(report), encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Riprende dall'ultimo test fallito")
    args = parser.parse_args()
    
    runner = TestRunner()
    runner.run_tests(resume=args.resume)
