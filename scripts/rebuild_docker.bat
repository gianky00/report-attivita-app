@echo off
setlocal enabledelayedexpansion

REM ===================================================================
REM  REBUILD DOCKER - Script professionale per ricostruzione container
REM  Progetto: Report Attivita App
REM  Uso: rebuild_docker.bat [--no-cache] [--detach] [--prune] [--help]
REM ===================================================================

REM --- COLORI ANSI ---
set "ESC="
set "GREEN=%ESC%[92m"
set "RED=%ESC%[91m"
set "YELLOW=%ESC%[93m"
set "CYAN=%ESC%[96m"
set "BOLD=%ESC%[1m"
set "DIM=%ESC%[90m"
set "RESET=%ESC%[0m"

REM --- COSTANTI ---
set "DOCKER_TIMEOUT=120"
set "MIN_DISK_MB=2000"
set "LOG_DIR=logs"
set "SCRIPT_VERSION=2.1.0"

REM --- NAVIGAZIONE ALLA ROOT DEL PROGETTO ---
cd /d "%~dp0.."

REM --- PARSING ARGOMENTI ---
set "NO_CACHE="
set "DETACH="
set "PRUNE="

:PARSE_ARGS
if "%~1"=="" goto ARGS_DONE
if /i "%~1"=="--no-cache" set "NO_CACHE=--no-cache"
if /i "%~1"=="--detach"   set "DETACH=-d"
if /i "%~1"=="--prune"    set "PRUNE=1"
if /i "%~1"=="--help"     goto SHOW_HELP
if /i "%~1"=="-h"         goto SHOW_HELP
shift
goto PARSE_ARGS
:ARGS_DONE

REM --- TIMESTAMP INIZIO ---
set "START_TS=%time: =0%"
set "START_DISP=%START_TS:~0,8%"

REM --- SETUP LOG FILE ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_STAMP=%date:~-4%%date:~-7,2%%date:~-10,2%_%START_TS:~0,2%%START_TS:~3,2%%START_TS:~6,2%"
set "LOG_STAMP=%LOG_STAMP:/=%"
set "LOG_STAMP=%LOG_STAMP:-=%"
set "LOG_FILE=%LOG_DIR%\docker_build_%LOG_STAMP%.log"

call :BANNER
call :LOG_MSG "Avvio script v%SCRIPT_VERSION%"
echo.

REM --- FASE 0: PRE-FLIGHT ---
call :PHASE "0" "Pre-flight checks"
if not exist ".env" (
    call :WARN "File .env non trovato!"
) else (
    call :OK ".env trovato"
)
call :OK "File compose trovato"

echo.

REM --- FASE 1: SYNC ---
call :PHASE "1" "Sincronizzazione dati Excel"
python scripts\sync_data.py
if !errorlevel! neq 0 (
    call :WARN "Sincronizzazione fallita."
) else (
    call :OK "Dati sincronizzati"
)
echo.

REM --- FASE 2: DOCKER CHECK ---
call :PHASE "2" "Rilevamento Docker"
set "COMPOSE_CMD=docker compose"
docker compose version >nul 2>&1
if !errorlevel! neq 0 (
    set "COMPOSE_CMD=docker-compose"
    call :WARN "Uso docker-compose v1"
) else (
    call :OK "Docker Compose v2 attivo"
)

docker info >nul 2>&1
if !errorlevel! neq 0 (
    call :FAIL "Docker daemon non risponde. Assicurati che Docker Desktop sia RUNNING."
    goto ERROR_EXIT
)
call :OK "Docker daemon attivo"
echo.

REM --- FASE 3: STOP ---
call :PHASE "3" "Arresto container"
!COMPOSE_CMD! down >> "%LOG_FILE%" 2>&1
call :OK "Container arrestati"
echo.

REM --- FASE 4: BUILD & START ---
call :PHASE "4" "Ricostruzione e avvio"
echo  %DIM%Esecuzione build...%RESET%

if defined NO_CACHE (
    !COMPOSE_CMD! build --no-cache >> "%LOG_FILE%" 2>&1
)

!COMPOSE_CMD! up -d --build 2>&1
if !errorlevel! neq 0 (
    call :FAIL "Errore durante up --build"
    goto ERROR_EXIT
)
call :OK "Applicazione avviata con successo"
echo.

REM --- COMPLETAMENTO ---
echo  %GREEN%%BOLD%====================================================%RESET%
echo  %GREEN%%BOLD%  PORTALE ONLINE - v%SCRIPT_VERSION%%RESET%
echo  %GREEN%  Log: %LOG_FILE%%RESET%
echo  %GREEN%%BOLD%====================================================%RESET%
echo.
pause
goto :EOF

:BANNER
echo  %CYAN%%BOLD%HORIZON DOCKER REBUILD TOOL%RESET%
echo.
goto :EOF

:PHASE
echo  %BOLD%[!time:~0,8!] FASE %~1: %~2%RESET%
goto :EOF

:OK
echo  %GREEN%  [OK]  %~1%RESET%
goto :EOF

:WARN
echo  %YELLOW%  [!!]  %~1%RESET%
goto :EOF

:FAIL
echo  %RED%  [XX]  %~1%RESET%
goto :EOF

:LOG_MSG
echo [!time:~0,8!] %~1 >> "%LOG_FILE%" 2>nul
goto :EOF

:ERROR_EXIT
echo.
echo  %RED%%BOLD%ERRORE CRITICO DURANTE IL REBUILD%RESET%
pause
exit /b 1

:SHOW_HELP
echo Uso: rebuild_docker.bat [--no-cache] [--detach]
goto :EOF
