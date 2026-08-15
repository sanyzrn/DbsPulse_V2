@echo off
setlocal enabledelayedexpansion
title DbsPulse - Setup and Run
color 0A

REM ============================================================
REM  DbsPulse full setup + run script (Windows)
REM  - Creates/uses backend Python venv, installs deps
REM  - Runs Alembic migrations
REM  - Installs frontend deps (skipped if already installed)
REM  - Starts backend (uvicorn) and frontend (vite) in their own
REM    console windows
REM  - Opens the app in the default browser
REM ============================================================

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV=%BACKEND%\.venv"

echo ============================================================
echo  DbsPulse setup starting
echo  Root: %ROOT%
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 0. Sanity checks
REM ------------------------------------------------------------
if not exist "%BACKEND%" (
    echo [ERROR] Backend folder not found at "%BACKEND%"
    pause
    exit /b 1
)
if not exist "%FRONTEND%" (
    echo [ERROR] Frontend folder not found at "%FRONTEND%"
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.11+ and try again.
    pause
    exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js not found in PATH. Please install Node.js and try again.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 1. Backend venv
REM ------------------------------------------------------------
echo [1/6] Backend virtual environment...
if not exist "%VENV%\Scripts\python.exe" (
    echo    Creating venv at "%VENV%"...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo    Venv already exists, skipping creation.
)

set "PY=%VENV%\Scripts\python.exe"
set "PIP=%VENV%\Scripts\pip.exe"

REM ------------------------------------------------------------
REM 2. Backend dependencies (skip if marker file matches requirements hash)
REM ------------------------------------------------------------
echo [2/6] Backend dependencies...
set "REQ_MARKER=%VENV%\.deps_installed"
set "REQ_FILE=%BACKEND%\requirements.txt"

set "NEED_INSTALL=1"
if exist "%REQ_MARKER%" (
    fc /b "%REQ_MARKER%" "%REQ_FILE%" >nul 2>nul
    if not errorlevel 1 set "NEED_INSTALL=0"
)

if "%NEED_INSTALL%"=="1" (
    echo    Installing/updating Python packages ^(this can take a while^)...
    "%PY%" -m pip install --upgrade pip
    if errorlevel 1 (
        echo [ERROR] Failed to upgrade pip. Check the log above.
        pause
        exit /b 1
    )
    "%PIP%" install -r "%REQ_FILE%"
    if errorlevel 1 (
        echo [ERROR] pip install failed. Check the log above.
        pause
        exit /b 1
    )
    copy /y "%REQ_FILE%" "%REQ_MARKER%" >nul
) else (
    echo    Dependencies already installed, skipping.
)

REM ------------------------------------------------------------
REM 3. Backend .env
REM ------------------------------------------------------------
echo [3/6] Backend environment file...
set "ENV_FILE=%BACKEND%\.env"
if not exist "%ENV_FILE%" (
    echo    No .env found, creating one from .env.example ^(safe local defaults^)...
    copy /y "%BACKEND%\.env.example" "%ENV_FILE%" >nul
    echo    Edit "%ENV_FILE%" if your local PostgreSQL user/password/database differ
    echo    from the defaults in .env.example.
) else (
    echo    .env already exists, leaving your settings untouched.
)

REM ------------------------------------------------------------
REM 4. Database migrations (Alembic)
REM ------------------------------------------------------------
echo [4/6] Running database migrations...
pushd "%BACKEND%"
REM This script bootstraps a LOCAL DEVELOPMENT environment, so the sample
REM users/personnel are seeded on purpose. They are gated behind this flag and are
REM never created in production - see README.md, "کاربران نمونه".
set "SEED_DEMO_DATA=true"
"%PY%" -m alembic upgrade head
if errorlevel 1 (
    popd
    echo [ERROR] Alembic migration failed. Make sure PostgreSQL is running and that
    echo         the database/user in "%ENV_FILE%" ^(DATABASE_URL^) exist, then re-run
    echo         this script. See README.md for the local PostgreSQL setup commands.
    pause
    exit /b 1
)
popd

REM ------------------------------------------------------------
REM 5. Frontend dependencies (skip if node_modules already present)
REM ------------------------------------------------------------
echo [5/6] Frontend dependencies...
if exist "%FRONTEND%\node_modules" (
    echo    node_modules already present, skipping npm install.
) else (
    echo    Installing frontend packages...
    pushd "%FRONTEND%"
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed. Check the log above.
        popd
        pause
        exit /b 1
    )
    popd
)

REM ------------------------------------------------------------
REM 6. Start backend + frontend servers
REM ------------------------------------------------------------
echo [6/6] Starting servers...

set "LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1 -ExpandProperty IPAddress); if ($ip) { $ip }"`) do set "LAN_IP=%%I"

start "DbsPulse Backend (uvicorn - port 8000)" /D "%BACKEND%" cmd /k ""%VENV%\Scripts\uvicorn.exe" app.main:app --reload --host 0.0.0.0 --port 8000"

start "DbsPulse Frontend (vite - port 5173)" /D "%FRONTEND%" cmd /k "npm run dev -- --host"

echo.
echo Waiting for the backend to come up...
set "BACKEND_READY=0"
where curl >nul 2>nul
if errorlevel 1 (
    REM curl not available on this system — fall back to a fixed wait
    timeout /t 8 /nobreak >nul
) else (
    for /l %%i in (1,1,30) do (
        if "!BACKEND_READY!"=="0" (
            curl -s -o nul -f "http://localhost:8000/api/health"
            if not errorlevel 1 (
                set "BACKEND_READY=1"
            ) else (
                timeout /t 1 /nobreak >nul
            )
        )
    )
)

start "" "http://localhost:5173"

echo.
echo ============================================================
echo  DbsPulse is starting up.
echo  Backend : http://localhost:8000
echo  Frontend: http://localhost:5173
if defined LAN_IP (
    echo  LAN Link: http://!LAN_IP!:5173
) else (
    echo  LAN Link: unavailable - no active non-loopback IPv4 address detected.
)
echo  Two console windows were opened for the running servers.
echo  Close those windows (or Ctrl+C inside them) to stop DbsPulse.
echo ============================================================
echo.
pause
endlocal
