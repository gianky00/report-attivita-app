@echo off
REM Questo script ferma i container Docker, forza la ricostruzione dell'immagine e li riavvia.

echo.
echo ===================================================
echo     ARRESTO DEI CONTAINER DOCKER IN CORSO...
echo ===================================================
echo.
docker-compose down

echo.
echo ===================================================
echo   RICOSTRUZIONE DELL'IMMAGINE E RIAVVIO IN CORSO...
echo ===================================================
echo.
docker-compose up --build

echo.
echo ===================================================
echo          PROCESSO COMPLETATO
echo ===================================================
echo.
pause
