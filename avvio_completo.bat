@echo off
TITLE Avvio Servizi Report - Procedura Completa

echo =======================================================
echo  AVVIO AUTOMATICO DI NGROK, GENERATORE LINK E STREAMLIT
echo =======================================================
echo.

REM --- 1. Installazione delle dipendenze Python ---
echo [1/7] Installazione/aggiornamento delle dipendenze da requirements.txt...
REM Questo comando installa solo le librerie mancanti o aggiorna quelle la cui versione
REM e' cambiata in requirements.txt. E' sicuro da eseguire ad ogni avvio.
REM Per aggiornare una libreria, modificare la sua versione nel file requirements.txt.
pip install -r requirements.txt
echo.

REM --- 2. Download dei pacchetti NLTK necessari ---
echo [2/7] Download dei pacchetti NLTK (punkt, stopwords, punkt_tab)...
python -m nltk.downloader punkt
python -m nltk.downloader stopwords
python -m nltk.downloader punkt_tab
echo.

REM --- 3. Creazione e Sincronizzazione del Database ---
echo [3/7] Preparazione del database locale...
python crea_database.py
echo.
echo [4/7] Sincronizzazione dei dati da Excel al database...
python sincronizzatore.py
echo.

REM --- 5. Avvia ngrok in una nuova finestra ---
echo [5/7] Avvio di ngrok per esporre la porta 8501...
START "Ngrok" cmd /c "ngrok http --domain opencircuit-grimily-mirta.ngrok-free.app 8501"

REM --- Attende qualche secondo per dare a ngrok il tempo di avviarsi e creare l'API ---
echo.
echo Attendo 5 secondi per la stabilizzazione di ngrok...
timeout /t 5 /nobreak >nul

REM --- 6. Esegue lo script Python per generare i link ---
echo.
echo [6/7] Eseguo genera_link.py per aggiornare i contatti con il nuovo URL...
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

REM --- 7. Avvia l'app Streamlit ---
echo.
echo [7/7] Avvio dell'applicazione Streamlit (app.py)...
echo.
streamlit run app.py

echo.
echo ===============================================
echo  Tutte le operazioni sono state avviate.
echo ===============================================
echo.
pause
