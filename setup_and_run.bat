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
set "VENV=%BACKEND%\venv"

set "DATABASE_URL=postgresql+psycopg://postgres:Sany1910@localhost:5432/dbspulsenew"

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
    "%PY%" -m pip install --upgrade pip >nul
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
REM 3. Backend .env (ensure DATABASE_URL is set as requested)
REM ------------------------------------------------------------
echo [3/6] Backend environment file...
set "ENV_FILE=%BACKEND%\.env"
if not exist "%ENV_FILE%" (
    echo    No .env found, creating one from .env.example...
    copy /y "%BACKEND%\.env.example" "%ENV_FILE%" >nul
)

REM Rewrite/insert DATABASE_URL line via the companion helper script
"%PY%" "%ROOT%\_set_env_var.py" "%ENV_FILE%" "DATABASE_URL" "%DATABASE_URL%"

echo    DATABASE_URL set to: %DATABASE_URL%

REM ------------------------------------------------------------
REM 4. Database migrations (Alembic)
REM ------------------------------------------------------------
echo [4/6] Running database migrations...
pushd "%BACKEND%"
set "DATABASE_URL=%DATABASE_URL%"
"%PY%" -m alembic upgrade head
if errorlevel 1 (
    echo [WARNING] Alembic migration failed. Make sure PostgreSQL is running
    echo           and that database "dbspulsenew" exists, then re-run this script.
    pause
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

start "DbsPulse Backend (uvicorn - port 8000)" /D "%BACKEND%" cmd /k ""%VENV%\Scripts\uvicorn.exe" app.main:app --reload --host 0.0.0.0 --port 8000"

start "DbsPulse Frontend (vite - port 5173)" /D "%FRONTEND%" cmd /k "npm run dev"

echo.
echo Waiting for servers to warm up...
timeout /t 6 /nobreak >nul

start "" "http://localhost:5173"

echo.
echo ============================================================
echo  DbsPulse is starting up.
echo  Backend : http://localhost:8000
echo  Frontend: http://localhost:5173
echo  Two console windows were opened for the running servers.
echo  Close those windows (or Ctrl+C inside them) to stop DbsPulse.
echo ============================================================
echo.
pause
endlocal
