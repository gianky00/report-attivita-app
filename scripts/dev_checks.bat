@echo off
setlocal enabledelayedexpansion

echo.
echo ===================================================
echo     GESTIONALE TECNICI - SUITE DI QUALITA'
echo ===================================================
echo.

echo [1/7] RUFF (Linting e Formattazione)...
python -m ruff check src/ scripts/ --fix
python -m ruff format src/ scripts/

echo [2/7] MYPY (Controllo Tipi)...
python -m mypy src/

echo [3/7] BANDIT (Sicurezza Codice)...
python -m bandit -r src/ -ll -q

echo [4/7] VULTURE (Ricerca Codice Morto)...
python -m vulture src/ --min-confidence 80

echo [5/7] XENON (Complessita' Ciclotomatica)...
python -m xenon --max-absolute B --max-modules B --max-average A src/

echo [6/7] INTERROGATE (Copertura Docstrings)...
python -m interrogate src/

echo [7/7] PIP-AUDIT (Vulnerabilita' Dipendenze)...
python -m pip_audit

echo.
echo ===================================================
echo          CONTROLLI COMPLETATI
echo ===================================================
echo.
pause
