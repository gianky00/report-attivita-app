@echo off
TITLE Avvio Servizi Report - Procedura Completa

echo =======================================================
echo  AVVIO AUTOMATICO DI NGROK, GENERATORE LINK E STREAMLIT
echo =======================================================
echo.

REM --- 1. Avvia ngrok in una nuova finestra ---
echo [1/3] Avvio di ngrok per esporre la porta 8501...
START "Ngrok" cmd /c "ngrok http 8501"

REM --- Attende qualche secondo per dare a ngrok il tempo di avviarsi e creare l'API ---
echo.
echo Attendo 5 secondi per la stabilizzazione di ngrok...
timeout /t 5 /nobreak >nul

REM --- 2. Esegue lo script Python per generare i link ---
echo.
echo [2/3] Eseguo genera_link.py per aggiornare i contatti con il nuovo URL...
python genera_link.py

REM --- Controlla se lo script precedente ha avuto successo ---
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ ERRORE: Lo script genera_link.py ha fallito.
    echo Controlla i messaggi di errore qui sopra. L'app non verra' avviata.
    echo.
    pause
    exit /b
)

REM --- 3. Avvia l'app Streamlit ---
echo.
echo [3/3] Avvio dell'applicazione Streamlit (app.py)...
echo.
streamlit run app.py

echo.
echo ===============================================
echo  Tutte le operazioni sono state avviate.
echo ===============================================
echo.
pause