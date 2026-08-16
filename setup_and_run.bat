@echo off
setlocal enabledelayedexpansion
title DbsPulse - Setup and Run

REM ============================================================
REM  DbsPulse - local development bootstrap (Windows)
REM
REM  DESIGN RULE FOR THIS SCRIPT: never open the browser on a
REM  broken stack. The previous version checked whether the
REM  backend came up, stored the answer in a variable, and then
REM  never looked at it - so a dead backend produced a perfectly
REM  healthy-looking login page and no clue why sign-in failed.
REM  Every check below either passes or stops with the reason
REM  and the exact command that fixes it.
REM ============================================================

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV=%BACKEND%\.venv"

REM UTF-8 mode, set once and inherited by both server windows.
REM
REM Without this, `import app.main` dies before binding a port:
REM slowapi builds its Limiter by reading backend\.env through
REM starlette's Config, which uses the OS default encoding. On a
REM Persian Windows install that is cp1252, and a single Persian
REM comment in .env raises UnicodeDecodeError. The generated .env
REM is kept ASCII as well (step 3) so a manually started uvicorn
REM works too - but this line means it works either way.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM Sample users/personnel are seeded on purpose here: this script
REM bootstraps a LOCAL DEVELOPMENT environment. The flag is read by
REM the backend at startup and is never set in production.
set "SEED_DEMO_DATA=true"

echo ============================================================
echo  DbsPulse setup
echo  Root: %ROOT%
echo ============================================================
echo.

REM ------------------------------------------------------------
REM  1. Prerequisites
REM ------------------------------------------------------------
echo [1/7] Checking prerequisites...

if not exist "%BACKEND%" call :fail "Backend folder not found at %BACKEND%" "You are running this script from the wrong place. Keep setup_and_run.bat in the repository root."
if not exist "%FRONTEND%" call :fail "Frontend folder not found at %FRONTEND%" "You are running this script from the wrong place. Keep setup_and_run.bat in the repository root."

where python >nul 2>nul
if errorlevel 1 call :fail "Python was not found in PATH." "Install Python 3.11 or newer from https://python.org and tick 'Add python.exe to PATH' during setup."

where node >nul 2>nul
if errorlevel 1 call :fail "Node.js was not found in PATH." "Install Node.js 20 or newer from https://nodejs.org, then open a NEW terminal so PATH is refreshed."

echo    OK  python and node are available
echo.

REM ------------------------------------------------------------
REM  2. Python virtual environment + dependencies
REM ------------------------------------------------------------
echo [2/7] Backend virtual environment...
if not exist "%VENV%\Scripts\python.exe" (
    echo    Creating venv at "%VENV%"...
    python -m venv "%VENV%"
    if errorlevel 1 call :fail "Could not create the Python virtual environment." "Check that you have write permission in %BACKEND%, then run this script again."
) else (
    echo    OK  venv already exists
)

set "PY=%VENV%\Scripts\python.exe"

REM Reinstall only when requirements.txt actually changed. The marker
REM is a copy of the file, so `fc /b` is an exact content comparison.
set "REQ_MARKER=%VENV%\.deps_installed"
set "REQ_FILE=%BACKEND%\requirements.txt"
set "NEED_INSTALL=1"
if exist "%REQ_MARKER%" (
    fc /b "%REQ_MARKER%" "%REQ_FILE%" >nul 2>nul
    if not errorlevel 1 set "NEED_INSTALL=0"
)

if "!NEED_INSTALL!"=="1" (
    echo    Installing Python packages ^(this can take a few minutes^)...
    "%PY%" -m pip install --upgrade pip --quiet
    if errorlevel 1 call :fail "Could not upgrade pip." "Check your internet connection or proxy settings, then run this script again."
    "%PY%" -m pip install -r "%REQ_FILE%"
    if errorlevel 1 call :fail "pip install failed - see the output above." "The most common cause is no internet access. Fix that and run this script again."
    copy /y "%REQ_FILE%" "%REQ_MARKER%" >nul
    echo    OK  packages installed
) else (
    echo    OK  packages already match requirements.txt
)
echo.

REM ------------------------------------------------------------
REM  3. Backend .env
REM ------------------------------------------------------------
echo [3/7] Backend environment file...
set "ENV_FILE=%BACKEND%\.env"
if not exist "%ENV_FILE%" (
    echo    Creating "%ENV_FILE%" with local defaults...
    REM Written here rather than copied from .env.example on purpose:
    REM .env.example is annotated in Persian, and those comments are
    REM exactly what crashes a non-UTF-8 reader. Read .env.example for
    REM the explanations; this file stays ASCII so it always parses.
    >"%ENV_FILE%" echo # DbsPulse - local development settings
    >>"%ENV_FILE%" echo #
    >>"%ENV_FILE%" echo # ASCII only, on purpose: this file is also read by starlette's
    >>"%ENV_FILE%" echo # Config using the OS default encoding, which is cp1252 on a
    >>"%ENV_FILE%" echo # Persian Windows install. One Persian comment here and the
    >>"%ENV_FILE%" echo # backend dies at import time with UnicodeDecodeError.
    >>"%ENV_FILE%" echo #
    >>"%ENV_FILE%" echo # The annotated Persian reference lives in .env.example.
    >>"%ENV_FILE%" echo.
    >>"%ENV_FILE%" echo ENVIRONMENT=development
    >>"%ENV_FILE%" echo DATABASE_URL=postgresql+psycopg://dbspulse:dbspulse_dev_password@localhost:5432/dbspulse
    >>"%ENV_FILE%" echo JWT_SECRET_KEY=local-development-only-not-a-real-secret
    >>"%ENV_FILE%" echo CORS_ORIGINS=http://localhost:5173,http://localhost:8080
    >>"%ENV_FILE%" echo PUBLIC_BASE_URL=http://localhost:5173
    >>"%ENV_FILE%" echo SEED_DEMO_DATA=true
    echo    OK  created - edit it if your PostgreSQL user/password/database differ
) else (
    REM An existing .env may still carry Persian comments from an older
    REM run of this script, which is the failure this whole block exists
    REM to prevent. Detect it and say so, rather than letting uvicorn die
    REM later with a stack trace nobody reads.
    "%PY%" -c "import sys,pathlib; d=pathlib.Path(r'%ENV_FILE%').read_bytes(); sys.exit(0 if all(b<128 for b in d) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo    [!] "%ENV_FILE%" contains non-ASCII characters ^(probably Persian comments^).
        echo        That is harmless while PYTHONUTF8=1 is set - this script sets it -
        echo        but starting uvicorn by hand without it will fail with
        echo        UnicodeDecodeError. Remove the non-ASCII comment lines to be safe.
    ) else (
        echo    OK  .env exists and is ASCII-clean
    )
)
echo.

REM ------------------------------------------------------------
REM  4. PostgreSQL reachability
REM ------------------------------------------------------------
REM Checked before Alembic so the message names the real cause. A failed
REM migration can mean a dozen things; "nothing is listening on 5432"
REM means one.
echo [4/7] PostgreSQL...
"%PY%" -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex(('127.0.0.1',5432)))" >nul 2>nul
if errorlevel 1 (
    echo.
    echo    Nothing is listening on 127.0.0.1:5432
    echo.
    echo    Start the PostgreSQL service, for example:
    echo        net start postgresql-x64-16
    echo    ^(run `sc query state^= all ^| findstr /i postgres` to find the exact name^)
    echo.
    call :fail "PostgreSQL is not reachable." "See the commands above, then run this script again."
)
echo    OK  something is listening on 127.0.0.1:5432
echo.

REM ------------------------------------------------------------
REM  5. Database migrations
REM ------------------------------------------------------------
echo [5/7] Applying database migrations...
pushd "%BACKEND%"
"%PY%" -m alembic upgrade head
if errorlevel 1 (
    popd
    echo.
    echo    PostgreSQL is running, so this is almost certainly the database
    echo    or role not existing yet. Create them once with:
    echo.
    echo        psql -U postgres -c "CREATE ROLE dbspulse LOGIN PASSWORD 'dbspulse_dev_password';"
    echo        psql -U postgres -c "CREATE DATABASE dbspulse OWNER dbspulse;"
    echo.
    echo    If your credentials differ, edit DATABASE_URL in "%ENV_FILE%".
    echo.
    call :fail "Alembic migration failed." "See the commands above, then run this script again."
)
popd
echo    OK  schema is up to date
echo.

REM ------------------------------------------------------------
REM  6. Frontend dependencies
REM ------------------------------------------------------------
echo [6/7] Frontend dependencies...
if exist "%FRONTEND%\node_modules" (
    echo    OK  node_modules already present
) else (
    echo    Running npm install ^(this can take a few minutes^)...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        popd
        call :fail "npm install failed - see the output above." "The most common cause is no internet access. Fix that and run this script again."
    )
    popd
    echo    OK  packages installed
)
echo.

REM ------------------------------------------------------------
REM  7. Start the servers
REM ------------------------------------------------------------
echo [7/7] Starting servers...

REM A stale process on 8000 makes uvicorn exit instantly in its own
REM window, which is easy to miss. Name it now rather than let the
REM health check time out for 40 seconds first.
"%PY%" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1',8000)) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo    Port 8000 is already in use. Find and stop the process with:
    echo        netstat -ano ^| findstr :8000
    echo        taskkill /PID ^<pid^> /F
    echo.
    call :fail "Port 8000 is occupied." "Stop whatever is using it, then run this script again."
)

start "DbsPulse Backend (port 8000)" /D "%BACKEND%" cmd /k ""%VENV%\Scripts\uvicorn.exe" app.main:app --reload --host 0.0.0.0 --port 8000"
start "DbsPulse Frontend (port 5173)" /D "%FRONTEND%" cmd /k "npm run dev -- --host"

echo    Waiting for the backend to answer on /api/health...
set "BACKEND_READY=0"
for /l %%i in (1,1,40) do (
    if "!BACKEND_READY!"=="0" (
        "%PY%" -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status==200 else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "BACKEND_READY=1"
        ) else (
            <nul set /p "=."
            timeout /t 1 /nobreak >nul
        )
    )
)
echo.

REM THE CHECK THAT WAS MISSING. Everything above can succeed and the
REM backend can still die on startup - and when it does, the frontend
REM still serves a perfectly normal login page that simply cannot log
REM anyone in. Opening the browser here would hide the real failure
REM behind a working-looking screen.
if "!BACKEND_READY!"=="0" (
    echo.
    echo ============================================================
    echo  [X] The backend did not come up within 40 seconds.
    echo ============================================================
    echo.
    echo  The frontend may still be running, but SIGN-IN WILL FAIL:
    echo  every /api request returns 502 through the Vite proxy. That is
    echo  exactly what a working login page with a dead backend looks like.
    echo.
    echo  Reproducing the failure here so you can read it:
    echo  ------------------------------------------------------------
    REM Importing the app triggers the same startup work uvicorn does, so
    REM whatever killed it surfaces here as a normal traceback. Cheaper
    REM and more reliable than scraping the other window's scrollback -
    REM and this output cannot have scrolled away.
    pushd "%BACKEND%"
    "%PY%" -c "import app.main" 2>&1
    popd
    echo  ------------------------------------------------------------
    echo.
    echo  If nothing was printed above, the import succeeds and the
    echo  problem is at bind time - check the backend console window.
    echo.
    echo  Common causes:
    echo    * UnicodeDecodeError     -^> backend\.env has non-ASCII comments
    echo    * Address already in use -^> something else grabbed port 8000
    echo    * OperationalError       -^> DATABASE_URL in backend\.env is wrong
    echo.
    pause
    exit /b 1
)

echo    OK  backend is healthy
echo.

set "LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$ip = (Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } ^| Select-Object -First 1 -ExpandProperty IPAddress); if ($ip) { $ip }"`) do set "LAN_IP=%%I"

start "" "http://localhost:5173"

echo ============================================================
echo  DbsPulse is running.
echo.
echo  Frontend : http://localhost:5173
echo  Backend  : http://localhost:8000
if defined LAN_IP echo  On LAN   : http://!LAN_IP!:5173
echo.
echo  Demo sign-in: hr1 / sup1 / dep1 / ceo1 / emp1
echo  Password    : DbsPulse@12345
echo.
echo  Two console windows are running the servers.
echo  Close them (or press Ctrl+C inside) to stop DbsPulse.
echo ============================================================
echo.
pause
endlocal
exit /b 0

REM ------------------------------------------------------------
REM  :fail "<what went wrong>" "<what to do about it>"
REM
REM  Every stop goes through here, so no failure can end with a
REM  bare "press any key" and no explanation.
REM ------------------------------------------------------------
:fail
echo.
echo ============================================================
echo  [X] %~1
echo ============================================================
echo.
echo  %~2
echo.
pause
exit 1
