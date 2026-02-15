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
set "SCRIPT_VERSION=2.0.0"

REM --- NAVIGAZIONE ALLA ROOT DEL PROGETTO ---
REM Lo script si trova in scripts/, quindi la root e' un livello sopra
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
set "START_DATE=%date%"

REM --- SETUP LOG FILE ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_STAMP=%date:~-4%%date:~-7,2%%date:~-10,2%_%START_TS:~0,2%%START_TS:~3,2%%START_TS:~6,2%"
REM Rimuovi eventuali separatori
set "LOG_STAMP=%LOG_STAMP:/=%"
set "LOG_STAMP=%LOG_STAMP:-=%"
set "LOG_FILE=%LOG_DIR%\docker_build_%LOG_STAMP%.log"

REM --- INIZIO ---
call :BANNER
call :LOG_MSG "Avvio script v%SCRIPT_VERSION%"
call :LOG_MSG "Directory progetto: %CD%"
echo.

REM ===================================================================
REM  FASE 0: PRE-FLIGHT CHECKS
REM ===================================================================
call :PHASE "0" "Pre-flight checks"

REM --- Check .env ---
if not exist ".env" (
    call :WARN "File .env non trovato! Il build potrebbe fallire."
    call :WARN "Crea .env con NGROK_AUTHTOKEN prima di procedere."
    echo.
    set /p "CONTINUE_ENV=  Vuoi continuare comunque? [s/N]: "
    if /i not "!CONTINUE_ENV!"=="s" goto ERROR_EXIT
) else (
    call :OK ".env trovato"
)

REM --- Check docker-compose.yml ---
set "COMPOSE_FILE_FOUND="
if exist "docker-compose.yml" set "COMPOSE_FILE_FOUND=1"
if exist "docker-compose.yaml" set "COMPOSE_FILE_FOUND=1"
if exist "compose.yml" set "COMPOSE_FILE_FOUND=1"
if exist "compose.yaml" set "COMPOSE_FILE_FOUND=1"

if not defined COMPOSE_FILE_FOUND (
    call :FAIL "Nessun file compose trovato (docker-compose.yml/yaml, compose.yml/yaml)"
    goto ERROR_EXIT
)
call :OK "File compose trovato"

REM --- Check spazio disco ---
set "FREE_MB="
for /f "usebackq tokens=3" %%a in (`dir /-c "%CD%" 2^>nul ^| findstr /c:"byte liberi" /c:"bytes free"`) do (
    set "RAW_FREE=%%a"
)
if defined RAW_FREE (
    if "!RAW_FREE:~6,1!" neq "" (
        set /a "FREE_MB=!RAW_FREE:~0,-6!" 2>nul
    )
)
if defined FREE_MB (
    if !FREE_MB! lss %MIN_DISK_MB% (
        call :WARN "Spazio disco basso: ~!FREE_MB! MB liberi (soglia: %MIN_DISK_MB% MB)"
    ) else (
        call :OK "Spazio disco: ~!FREE_MB! MB liberi"
    )
) else (
    call :OK "Check spazio disco saltato"
)

echo.

REM ===================================================================
REM  FASE 1: RILEVAMENTO DOCKER COMPOSE
REM ===================================================================
call :PHASE "1" "Rilevamento Docker Compose"

set "COMPOSE_CMD="

docker compose version >nul 2>&1
if !errorlevel! equ 0 (
    set "COMPOSE_CMD=docker compose"
    call :OK "docker compose v2 (plugin)"
    goto COMPOSE_FOUND
)

docker-compose version >nul 2>&1
if !errorlevel! equ 0 (
    set "COMPOSE_CMD=docker-compose"
    call :WARN "docker-compose v1 (deprecato, considera l'upgrade a v2)"
    goto COMPOSE_FOUND
)

call :FAIL "Ne 'docker compose' ne 'docker-compose' trovati."
call :FAIL "Installa Docker Desktop: https://www.docker.com/products/docker-desktop"
goto ERROR_EXIT

:COMPOSE_FOUND
echo.

REM ===================================================================
REM  FASE 2: VERIFICA DOCKER DAEMON
REM ===================================================================
call :PHASE "2" "Verifica Docker daemon"

docker info >nul 2>&1
if !errorlevel! equ 0 (
    call :OK "Docker daemon attivo"
    echo.
    goto DOCKER_READY
)

call :WARN "Docker daemon non attivo. Avvio automatico..."

REM --- Rilevamento path Docker Desktop ---
set "DOCKER_EXE="

if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    set "DOCKER_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
)

if not defined DOCKER_EXE (
    if exist "%LOCALAPPDATA%\Docker\Docker Desktop.exe" (
        set "DOCKER_EXE=%LOCALAPPDATA%\Docker\Docker Desktop.exe"
    )
)

if not defined DOCKER_EXE (
    for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Docker Inc.\Docker\1.0" /v AppPath 2^>nul') do (
        set "DOCKER_EXE=%%b\Docker Desktop.exe"
    )
)

if not defined DOCKER_EXE (
    call :FAIL "Docker Desktop non trovato. Avvialo manualmente."
    goto ERROR_EXIT
)

call :LOG_MSG "Avvio: !DOCKER_EXE!"
start "" "!DOCKER_EXE!"

REM --- Polling con timeout ---
set /a ELAPSED=0
echo.
echo|set /p="  Attesa daemon "

:WAIT_DOCKER
if !ELAPSED! geq %DOCKER_TIMEOUT% (
    echo.
    call :FAIL "TIMEOUT: daemon non avviato entro %DOCKER_TIMEOUT%s."
    goto ERROR_EXIT
)
timeout /t 3 /nobreak >nul
set /a ELAPSED+=3
echo|set /p="."
docker info >nul 2>&1
if !errorlevel! neq 0 goto WAIT_DOCKER

echo.
call :OK "Docker daemon avviato (!ELAPSED!s)"
echo.

:DOCKER_READY

REM ===================================================================
REM  FASE 3: ARRESTO CONTAINER
REM ===================================================================
call :PHASE "3" "Arresto container"

!COMPOSE_CMD! down >> "%LOG_FILE%" 2>&1
if !errorlevel! neq 0 (
    call :WARN "Nessun container attivo da fermare (o errore minore)"
) else (
    call :OK "Container arrestati"
)
echo.

REM ===================================================================
REM  FASE 4: RICOSTRUZIONE E AVVIO
REM ===================================================================
if defined NO_CACHE (
    call :PHASE "4" "Ricostruzione SENZA CACHE e avvio"
) else (
    call :PHASE "4" "Ricostruzione e avvio"
)

echo.
echo  %DIM%--- Inizio output docker build ---%RESET%
echo.

!COMPOSE_CMD! up --build !NO_CACHE! !DETACH! 2>&1
set "BUILD_RESULT=!errorlevel!"

if !BUILD_RESULT! neq 0 (
    echo.
    call :FAIL "La ricostruzione e' fallita (exit code: !BUILD_RESULT!)."
    call :FAIL "Controlla il log: %LOG_FILE%"
    goto ERROR_EXIT
)
echo.
call :OK "Build e avvio completati"
echo.

REM ===================================================================
REM  FASE 5: PULIZIA IMMAGINI (opzionale)
REM ===================================================================
if defined PRUNE (
    call :PHASE "5" "Pulizia immagini dangling"
    set "DANGLING=0"
    for /f %%n in ('docker images -f "dangling=true" -q 2^>nul ^| find /c /v ""') do set "DANGLING=%%n"
    if !DANGLING! gtr 0 (
        docker image prune -f >> "%LOG_FILE%" 2>&1
        call :OK "Rimosse !DANGLING! immagini dangling"
    ) else (
        call :OK "Nessuna immagine dangling da rimuovere"
    )
    echo.
)

REM ===================================================================
REM  FASE 6: HEALTH CHECK CONTAINER
REM ===================================================================
call :PHASE "6" "Verifica stato container"

timeout /t 3 /nobreak >nul

set "RUNNING_COUNT=0"
for /f %%c in ('docker ps -q 2^>nul ^| find /c /v ""') do set "RUNNING_COUNT=%%c"

if !RUNNING_COUNT! equ 0 (
    if defined DETACH (
        call :WARN "Nessun container in esecuzione dopo il deploy"
    ) else (
        call :OK "Modalita' attached terminata normalmente"
    )
) else (
    call :OK "!RUNNING_COUNT! container in esecuzione"

    set "UNHEALTHY_COUNT=0"
    for /f %%c in ('docker ps --filter "health=unhealthy" -q 2^>nul ^| find /c /v ""') do set "UNHEALTHY_COUNT=%%c"
    if !UNHEALTHY_COUNT! gtr 0 (
        call :WARN "!UNHEALTHY_COUNT! container con stato 'unhealthy'"
    )

    echo.
    echo  %CYAN%%BOLD% CONTAINER ATTIVI%RESET%
    echo  %DIM%-----------------------------------------------------------------------%RESET%
    docker ps --format "  {{.Names}}	{{.Status}}	{{.Ports}}" 2>nul
    echo  %DIM%-----------------------------------------------------------------------%RESET%
)
echo.

REM ===================================================================
REM  COMPLETAMENTO
REM ===================================================================
set "END_TS=%time: =0%"
set "END_DISP=%END_TS:~0,8%"

REM Calcolo durata
set /a "S1=(1%START_TS:~0,2%-100)*3600 + (1%START_TS:~3,2%-100)*60 + (1%START_TS:~6,2%-100)"
set /a "S2=(1%END_TS:~0,2%-100)*3600 + (1%END_TS:~3,2%-100)*60 + (1%END_TS:~6,2%-100)"
set /a "DURATION=S2-S1"
if !DURATION! lss 0 set /a "DURATION+=86400"
set /a "DUR_M=DURATION/60"
set /a "DUR_S=DURATION%%60"

echo  %GREEN%%BOLD%====================================================%RESET%
echo  %GREEN%%BOLD%  COMPLETATO CON SUCCESSO%RESET%
echo  %GREEN%  Inizio:   %START_DISP%%RESET%
echo  %GREEN%  Fine:     %END_DISP%%RESET%
echo  %GREEN%  Durata:   !DUR_M!m !DUR_S!s%RESET%
echo  %GREEN%  Log:      %LOG_FILE%%RESET%
echo  %GREEN%%BOLD%====================================================%RESET%
echo.

REM --- Notifica sonora (3 beep) ---
for /l %%i in (1,1,3) do (
    echo|set /p=""
    timeout /t 1 /nobreak >nul
)

pause
goto :EOF

REM ===================================================================
REM  HELP
REM ===================================================================
:SHOW_HELP
echo.
echo  %BOLD%REBUILD DOCKER v%SCRIPT_VERSION%%RESET%
echo  Script per ricostruzione automatica container Docker.
echo.
echo  %BOLD%USO:%RESET%
echo    rebuild_docker.bat [opzioni]
echo.
echo  %BOLD%OPZIONI:%RESET%
echo    --no-cache   Ricostruisce le immagini senza usare la cache Docker
echo    --detach     Avvia i container in background (modalita' detached)
echo    --prune      Rimuove le immagini dangling dopo il build
echo    --help, -h   Mostra questo messaggio di aiuto
echo.
echo  %BOLD%ESEMPI:%RESET%
echo    rebuild_docker.bat                         Standard rebuild
echo    rebuild_docker.bat --no-cache              Rebuild da zero
echo    rebuild_docker.bat --detach --prune        Background + pulizia
echo    rebuild_docker.bat --no-cache --prune      Full rebuild + pulizia
echo.
echo  %BOLD%PRE-REQUISITI:%RESET%
echo    - Docker Desktop installato
echo    - File .env con NGROK_AUTHTOKEN
echo    - File docker-compose.yml nella root del progetto
echo.
goto :EOF

REM ===================================================================
REM  FUNZIONI HELPER
REM ===================================================================

:BANNER
echo.
echo  %CYAN%%BOLD%____            _           ____        _ _     _ %RESET%
echo  %CYAN%%BOLD%^|  _ \  ___   ___^| ^| _____ _ ^|  _ \ _   _(_) ^| __^| ^|%RESET%
echo  %CYAN%%BOLD%^| ^| ^| ^|/ _ \ / __^| ^|/ / _ \ '^| ^| ^|) ^| ^| ^| ^| ^| ^| / _` ^|%RESET%
echo  %CYAN%%BOLD%^| ^|_^| ^| (_) ^| (__^|   ^<  __/ ^|  _ /^| ^|_^| ^| ^| ^| ^| (_^| ^|%RESET%
echo  %CYAN%%BOLD%^|____/ \___/ \___^|_^|\_\___^|_^|_^| \_\\__,_^|_^|_^|_^|\__,_^|%RESET%
echo  %DIM%v%SCRIPT_VERSION% - Report Attivita App%RESET%
echo.
goto :EOF

:PHASE
set "P_TS=%time: =0%"
set "P_DISP=!P_TS:~0,8!"
echo  %BOLD%%CYAN%[!P_DISP!] FASE %~1: %~2%RESET%
echo [!P_DISP!] FASE %~1: %~2 >> "%LOG_FILE%" 2>nul
goto :EOF

:OK
echo  %GREEN%  [OK]  %~1%RESET%
echo   [OK]  %~1 >> "%LOG_FILE%" 2>nul
goto :EOF

:WARN
echo  %YELLOW%  [!!]  %~1%RESET%
echo   [!!]  %~1 >> "%LOG_FILE%" 2>nul
goto :EOF

:FAIL
echo  %RED%  [XX]  %~1%RESET%
echo   [XX]  %~1 >> "%LOG_FILE%" 2>nul
goto :EOF

:LOG_MSG
set "L_TS=%time: =0%"
set "L_DISP=!L_TS:~0,8!"
echo  %DIM%[!L_DISP!] %~1%RESET%
echo [!L_DISP!] %~1 >> "%LOG_FILE%" 2>nul
goto :EOF

REM ===================================================================
REM  ERROR EXIT
REM ===================================================================
:ERROR_EXIT
echo.
echo  %RED%%BOLD%====================================================%RESET%
echo  %RED%%BOLD%  PROCESSO TERMINATO CON ERRORI%RESET%
if defined LOG_FILE (
    echo  %RED%  Log: %LOG_FILE%%RESET%
)
echo  %RED%%BOLD%====================================================%RESET%
echo.
REM --- Beep errore ---
echo|set /p=""
pause
exit /b 1
