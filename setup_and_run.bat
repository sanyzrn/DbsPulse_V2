@echo off
setlocal enabledelayedexpansion
title DbsPulse - Setup and Run

REM ============================================================
REM  DbsPulse - local development bootstrap (Windows)
REM
REM  *** DEVELOPMENT ONLY - DO NOT RUN ON A REAL DEPLOYMENT ***
REM
REM  This script deliberately writes ENVIRONMENT=development, a
REM  fixed JWT_SECRET_KEY, SEED_DEMO_DATA=true (sample accounts
REM  whose shared password is published in the repository) and
REM  MIN_COHORT_SIZE=1, which turns OFF the suppression that
REM  keeps a three-person "unit average" from being read back as
REM  those three people's scores.
REM
REM  For a real deployment see deploy/PRODUCTION.md - it ships
REM  built container images and never puts any of the above on
REM  the server.
REM
REM  TWO DESIGN RULES FOR THIS SCRIPT:
REM
REM  1. Never open the browser on a broken stack. A dead backend
REM     still serves a perfectly healthy-looking login page that
REM     simply cannot log anyone in, and that is the single most
REM     confusing way for this to fail.
REM
REM  2. Never end on an instruction the user cannot follow. The
REM     old version stopped with "run psql -U postgres ..." - but
REM     the PostgreSQL installer does not put psql on PATH, so
REM     that command failed too and the setup dead-ended. Where
REM     this script can fix something itself, it does; where it
REM     genuinely cannot, it says exactly what to do.
REM
REM  Checks verify that a thing WORKS, not that it EXISTS. "python
REM  is on PATH" is not the same as "python runs and is new
REM  enough" - on a fresh Windows 11, `python` is usually a Store
REM  stub that satisfies the first and fails the second.
REM ============================================================

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV=%BACKEND%\.venv"

REM Minimum versions, kept next to each other so they are easy to
REM find when a dependency raises the bar.
REM   Python 3.11 - app code imports `datetime.UTC`, added in 3.11.
REM   Node 20.19  - required by Vite 8 (see frontend/package.json).
set "MIN_PY_MAJOR=3"
set "MIN_PY_MINOR=11"

REM UTF-8 mode, set once and inherited by both server windows.
REM
REM Without this, `import app.main` dies before binding a port:
REM slowapi builds its Limiter by reading backend\.env through
REM starlette's Config, which uses the OS default encoding. On a
REM Persian Windows install that is cp1252, and a single Persian
REM comment in .env raises UnicodeDecodeError. The generated .env
REM is kept ASCII as well (step 4) so a manually started uvicorn
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
echo [1/8] Checking prerequisites...

if not exist "%BACKEND%" call :fail "Backend folder not found at %BACKEND%" "You are running this script from the wrong place. Keep setup_and_run.bat in the repository root."
if not exist "%FRONTEND%" call :fail "Frontend folder not found at %FRONTEND%" "You are running this script from the wrong place. Keep setup_and_run.bat in the repository root."

REM --- Python: must actually run, and be new enough ---------------
REM `where python` is deliberately NOT used. On a fresh Windows 11
REM it finds %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe - an
REM App Execution Alias that opens the Microsoft Store and prints
REM nothing. It satisfies `where`, creates no venv, and the first
REM real symptom is a confusing failure several steps later.
REM Running it and reading the version back is the only check that
REM distinguishes a real interpreter from the stub.
REM Detection lives in a subroutine because the probe command contains
REM parentheses - `print(...)`. Inside a parenthesised if/for block, cmd
REM matches the first `)` it sees against the block instead of the
REM command, and the line silently does the wrong thing. At subroutine
REM top level there is no enclosing block to confuse it.
call :detect_python

if not defined PYCMD (
    echo.
    echo    Python did not run. If `python` opens the Microsoft Store,
    echo    that is the placeholder, not a real install:
    echo        Settings ^> Apps ^> Advanced app settings ^>
    echo        App execution aliases ^> turn OFF both "python" entries
    echo.
    call :fail "No working Python interpreter found." "Install Python %MIN_PY_MAJOR%.%MIN_PY_MINOR% or newer from https://python.org and tick 'Add python.exe to PATH', then open a NEW terminal."
)

set /a MIN_PY_ENC=%MIN_PY_MAJOR%*1000+%MIN_PY_MINOR%
if !PYVER! LSS !MIN_PY_ENC! (
    set /a FOUND_MAJOR=!PYVER!/1000
    set /a FOUND_MINOR=!PYVER!%%1000
    echo.
    echo    Found Python !FOUND_MAJOR!.!FOUND_MINOR!, but this project needs %MIN_PY_MAJOR%.%MIN_PY_MINOR% or newer.
    echo    The backend imports `datetime.UTC`, which only exists from 3.11 on,
    echo    so an older interpreter fails at import time - after everything
    echo    else in this script has already reported success.
    echo.
    call :fail "Python is too old." "Install Python %MIN_PY_MAJOR%.%MIN_PY_MINOR%+ from https://python.org, then open a NEW terminal and run this script again."
)

REM --- Node: must be new enough for Vite 8 -----------------------
REM Same reasoning as Python. Node 18 was LTS until recently and is
REM still widely installed; `npm install` succeeds on it and only
REM `npm run dev` fails, which points the blame at the wrong step.
call :detect_node

if not defined NODEVER call :fail "Node.js was not found (or did not run)." "Install Node.js 20.19+ or 22.12+ from https://nodejs.org, then open a NEW terminal so PATH is refreshed."

REM Vite 8 wants ^20.19 || >=22.12. Anything at or above 20.19 that
REM is not a 21.x or an early 22.x satisfies it.
set "NODE_OK=0"
if !NODEVER! GEQ 22012 set "NODE_OK=1"
if !NODEVER! GEQ 20019 if !NODEVER! LSS 21000 set "NODE_OK=1"
if "!NODE_OK!"=="0" (
    echo.
    echo    Found Node !NODE_TEXT!, which Vite 8 refuses to start on.
    echo    `npm install` will still succeed on it - only `npm run dev`
    echo    fails, which makes it look like a frontend bug.
    echo.
    call :fail "Node.js is too old." "Install Node.js 20.19+ or 22.12+ from https://nodejs.org, then open a NEW terminal and run this script again."
)

echo    OK  python ^(!PYCMD!^) and node are present and new enough
echo.

REM ------------------------------------------------------------
REM  2. Python virtual environment
REM ------------------------------------------------------------
echo [2/8] Backend virtual environment...
if not exist "%VENV%\Scripts\python.exe" (
    echo    Creating venv at "%VENV%"...
    %PYCMD% -m venv "%VENV%"
    if errorlevel 1 call :fail "Could not create the Python virtual environment." "Check that you have write permission in %BACKEND%, then run this script again."
)

REM `python -m venv` can report success and still leave an unusable
REM venv (interrupted run, antivirus, a half-deleted folder). Test
REM the interpreter rather than trusting the exit code.
if not exist "%VENV%\Scripts\python.exe" call :fail "The virtual environment is missing its interpreter." "Delete the folder %VENV% and run this script again."

set "PY=%VENV%\Scripts\python.exe"
"%PY%" -c "import sys" >nul 2>nul
if errorlevel 1 call :fail "The virtual environment's Python does not run." "Delete the folder %VENV% and run this script again - it is usually a half-created venv."
echo    OK  venv ready
echo.

REM ------------------------------------------------------------
REM  3. Backend dependencies
REM ------------------------------------------------------------
echo [3/8] Backend dependencies...

REM Reinstall only when requirements.txt actually changed. The marker
REM is a copy of the file, so `fc /b` is an exact content comparison.
set "REQ_MARKER=%VENV%\.deps_installed"
set "REQ_FILE=%BACKEND%\requirements.txt"
set "NEED_INSTALL=1"
if exist "%REQ_MARKER%" (
    fc /b "%REQ_MARKER%" "%REQ_FILE%" >nul 2>nul
    if not errorlevel 1 set "NEED_INSTALL=0"
)

REM The marker says "we installed these requirements". It does NOT say
REM the packages are still there - and that gap is the failure that has
REM cost the most time on this project: a venv loses packages (an
REM interrupted pip, antivirus, a partly-deleted folder), the marker
REM still matches requirements.txt, this step prints "packages already
REM match", uvicorn dies with ModuleNotFoundError in its own window, and
REM the frontend shows ECONNREFUSED with nothing pointing at the cause.
REM Checking for uvicorn.exe is not enough either - it survives while
REM other packages are gone. So ask the venv the real question: can it
REM import what the app imports? scripts/check_deps.py holds the list
REM (and knows weasyprint is optional).
pushd "%BACKEND%"
"%PY%" -m scripts.check_deps >nul 2>nul
set "DEPS_OK=!errorlevel!"
popd
if not "!DEPS_OK!"=="0" (
    if "!NEED_INSTALL!"=="0" echo    Marker says installed, but the venv cannot import them - reinstalling.
    set "NEED_INSTALL=1"
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

REM Same question again, now as the last word of this step. If pip said
REM it succeeded and the imports still fail, the venv itself is damaged
REM and no amount of re-running pip will fix it - say so here instead of
REM letting it surface four steps later as a dead backend.
pushd "%BACKEND%"
"%PY%" -m scripts.check_deps
set "DEPRC=!errorlevel!"
popd
if not "!DEPRC!"=="0" call :fail "The venv is missing packages even after pip install." "Delete the folder %VENV% and run this script again - a rebuilt venv fixes this."
echo.

REM ------------------------------------------------------------
REM  4. Backend .env
REM ------------------------------------------------------------
echo [4/8] Backend environment file...
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
    >>"%ENV_FILE%" echo.
    >>"%ENV_FILE%" echo # Aggregate averages are hidden below this many evaluations, so that
    >>"%ENV_FILE%" echo # a "unit average" over two people cannot be read back as those two
    >>"%ENV_FILE%" echo # people's scores. The production default is 5; the demo data set is
    >>"%ENV_FILE%" echo # smaller than that, so every dashboard chart would come up empty
    >>"%ENV_FILE%" echo # and look broken. 1 disables suppression - LOCAL DEMO ONLY.
    >>"%ENV_FILE%" echo MIN_COHORT_SIZE=1
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
REM  5. PostgreSQL: reachable, and the database actually exists
REM ------------------------------------------------------------
REM Checked before Alembic so the message names the real cause. A failed
REM migration can mean a dozen things; "nothing is listening on 5432"
REM means one.
echo [5/8] PostgreSQL...
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

REM The role and database are created here instead of being demanded
REM from the user, because the instructions we used to print could not
REM be followed: psql is not on PATH after a default Windows install.
REM psycopg is already in the venv by this point, so we can just do it.
pushd "%BACKEND%"
"%PY%" -m scripts.ensure_database
set "DBRC=!errorlevel!"

if "!DBRC!"=="3" (
    echo.
    echo    The database does not exist yet, and creating it needs the
    echo    PostgreSQL admin password - the one set during installation
    echo    for the "postgres" user.
    echo.
    REM Read into PGPASSWORD rather than a command line argument: libpq
    REM picks it up from the environment, and it never shows up in the
    REM process list where other users could read it. Subroutine again -
    REM the PowerShell one-liner is full of brackets and parentheses.
    call :read_pgpassword
    echo.
    "%PY%" -m scripts.ensure_database
    set "DBRC=!errorlevel!"
    set "PGPASSWORD="
)

popd

if not "!DBRC!"=="0" (
    echo.
    echo    Could not create the database automatically.
    echo.
    echo    If you have pgAdmin ^(installed alongside PostgreSQL^), create:
    echo        role      dbspulse   password  dbspulse_dev_password
    echo        database  dbspulse   owner     dbspulse
    echo.
    echo    Or from the PostgreSQL bin folder, which is usually
    echo        C:\Program Files\PostgreSQL\16\bin
    echo    run:
    echo        psql -U postgres -c "CREATE ROLE dbspulse LOGIN PASSWORD 'dbspulse_dev_password';"
    echo        psql -U postgres -c "CREATE DATABASE dbspulse OWNER dbspulse;"
    echo.
    echo    If your credentials differ, edit DATABASE_URL in "%ENV_FILE%".
    echo.
    call :fail "The application database is not available." "See the options above, then run this script again."
)
echo    OK  database is available
echo.

REM ------------------------------------------------------------
REM  6. Database migrations
REM ------------------------------------------------------------
echo [6/8] Applying database migrations...
pushd "%BACKEND%"
"%PY%" -m alembic upgrade head
if errorlevel 1 (
    popd
    echo.
    echo    The database exists and is reachable, so this is a migration
    echo    error rather than a connection problem - read the traceback
    echo    above for the failing revision.
    echo.
    call :fail "Alembic migration failed." "See the output above, then run this script again."
)
popd
echo    OK  schema is up to date
echo.

REM ------------------------------------------------------------
REM  7. Frontend dependencies
REM ------------------------------------------------------------
echo [7/8] Frontend dependencies...
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
REM  8. Start the servers
REM ------------------------------------------------------------
echo [8/8] Starting servers...

REM Anything wrong with port 8000 makes uvicorn exit instantly in its own
REM window, which is easy to miss. Name it now rather than let the health
REM check time out for 40 seconds first and then say nothing useful.
REM
REM This used to be a `connect` test, which answers the wrong question.
REM `connect` asks "is someone listening there?"; we need "can WE listen
REM there?". On Windows those differ: Hyper-V / WSL2 / Docker Desktop
REM reserve whole ranges of ports, and inside such a range nobody is
REM listening (so connect says "free") while bind fails with WSAEACCES
REM 10013. check_port binds for real - on 0.0.0.0, the same address
REM uvicorn is started with below - and tells the two cases apart.
pushd "%BACKEND%"
"%PY%" -m scripts.check_port --port 8000
set "PORTRC=!errorlevel!"
popd

if "!PORTRC!"=="2" (
    echo.
    echo    Port 8000 is already in use. Find and stop the process with:
    echo        netstat -ano ^| findstr :8000
    echo        taskkill /PID ^<pid^> /F
    echo.
    call :fail "Port 8000 is occupied." "Stop whatever is using it, then run this script again."
)

if "!PORTRC!"=="3" (
    echo.
    echo    Port 8000 falls inside a range Windows has reserved for itself
    echo    ^(listed above^). Nothing is listening there, so the port LOOKS
    echo    free - but no program is allowed to bind to it, so the backend
    echo    would start and die in the same second.
    echo.
    echo    From an Administrator terminal, either:
    echo      a^) release the reserved ranges and let them be re-picked:
    echo         net stop winnat
    echo         net start winnat
    echo      b^) or claim 8000 permanently so Windows stops taking it:
    echo         netsh int ipv4 add excludedportrange protocol=tcp startport=8000 numberofports=1 store=persistent
    echo         ^(needs a reboot; after it, programs can bind 8000 again^)
    echo.
    echo    Moving the backend to another port also works, but the frontend
    echo    proxy target lives in frontend\vite.config.ts and would have to
    echo    be changed to match.
    echo.
    call :fail "Port 8000 is reserved by Windows." "See the options above, then run this script again."
)

if not "!PORTRC!"=="0" (
    echo.
    call :fail "Port 8000 could not be tested - see the error above." "Fix the reported problem, then run this script again."
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
REM Only the accounts the seed migration actually creates are listed.
REM An account that does not exist looks identical to a broken backend
REM from the login screen, so a wrong name here costs real debugging time.
echo  Demo sign-in: hr1 / sup1 / sup2 / dep1 / ceo1
echo  Password    : DbsPulse@12345
echo.
echo  The base seed is only 3 people, so most charts stay empty. For a
echo  realistic org (every workflow stage, a returned case, an expiring
echo  contract), run once in the backend folder:
echo      .venv\Scripts\python -m scripts.seed_demo_scenarios
echo.
echo  Two console windows are running the servers.
echo  Close them (or press Ctrl+C inside) to stop DbsPulse.
echo ============================================================
echo.
pause
endlocal
exit /b 0

REM ------------------------------------------------------------
REM  :detect_python -> sets PYCMD and PYVER, or leaves both unset
REM
REM  Tries `python` first, then the `py` launcher, which is often
REM  present and working even when `python` is the Store stub.
REM  PYVER is major*1000+minor, so 3.11 -> 3011 and plain integer
REM  comparison gives correct ordering (3.9 -> 3009 < 3011).
REM ------------------------------------------------------------
:detect_python
set "PYVER="
for /f "usebackq delims=" %%V in (`python -c "import sys;print(sys.version_info[0]*1000+sys.version_info[1])" 2^>nul`) do set "PYVER=%%V"
if defined PYVER (
    set "PYCMD=python"
    exit /b 0
)
for /f "usebackq delims=" %%V in (`py -3 -c "import sys;print(sys.version_info[0]*1000+sys.version_info[1])" 2^>nul`) do set "PYVER=%%V"
if defined PYVER (
    set "PYCMD=py -3"
    exit /b 0
)
exit /b 1

REM ------------------------------------------------------------
REM  :detect_node -> sets NODEVER (major*1000+minor) and NODE_TEXT
REM ------------------------------------------------------------
:detect_node
set "NODEVER="
set "NODE_TEXT="
for /f "usebackq delims=" %%V in (`node -e "const p=process.versions.node.split('.');console.log(Number(p[0])*1000+Number(p[1]))" 2^>nul`) do set "NODEVER=%%V"
for /f "usebackq delims=" %%V in (`node -p "process.versions.node" 2^>nul`) do set "NODE_TEXT=%%V"
exit /b 0

REM ------------------------------------------------------------
REM  :read_pgpassword -> sets PGPASSWORD from a masked prompt
REM ------------------------------------------------------------
:read_pgpassword
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$s=Read-Host -AsSecureString 'postgres password'; [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"`) do set "PGPASSWORD=%%P"
exit /b 0

REM ------------------------------------------------------------
REM  :fail "<what went wrong>" "<what to do about it>"
REM
REM  Every stop goes through here, so no failure can end with a
REM  bare "press any key" and no explanation. `exit` without /b is
REM  deliberate: this is CALLed, and `exit /b` would return to the
REM  caller and let the script carry on past a fatal error.
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
