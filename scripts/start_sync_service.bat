@echo off
title Servizio Sincronizzazione Horizon
color 0B
mode con cols=80 lines=25
set PYTHONUTF8=1

:: Percorso assoluto allo script di sincronizzazione
set SCRIPT_PATH=%~dp0\sync_data.py
set LOG_FILE=%~dp0\..\logs\sync_service.log

echo ========================================================
echo   HORIZON DATA SYNC SERVICE (H24)
echo ========================================================
echo.
echo Avvio del servizio di sincronizzazione in background...
echo Lo script si avviera' ogni 5 minuti (300 secondi).
echo Non chiudere questa finestra.
echo.

:loop
echo [%date% %time%] Avvio ciclo di sincronizzazione...
python -m poetry run python "%SCRIPT_PATH%" >> "%LOG_FILE%" 2>&1
if errorlevel 2 (
    echo [%date% %time%] Nessuna modifica rilevata in rete.
) else if errorlevel 1 (
    echo [%date% %time%] Errore durante la sincronizzazione. Controlla i log.
) else (
    echo [%date% %time%] Sincronizzazione completata con successo! Nuovi dati estratti.
)
echo.
echo In attesa per 5 minuti...
timeout /t 300 /nobreak > NUL
goto loop