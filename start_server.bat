@echo off
setlocal enabledelayedexpansion

title GitHub Repository Analyzer Server

cd /d "%~dp0"

echo ===================================================
echo     Starting GitHub Repository Analyzer Server
echo ===================================================
echo.

:: 1. Check virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv\
    echo Please create the virtual environment first:
    echo     python -m venv .venv
    echo     .\.venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: 2. Check .env file
if not exist ".env" (
    echo [WARNING] .env file not found. Creating from .env.example...
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [INFO] Created .env file. Please add your GITHUB_TOKEN.
    )
)

:: 3. Free port 8000 if already in use by a stale process
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":8000\>"') do (
    if not "%%a"=="" if not "%%a"=="0" (
        echo [INFO] Port 8000 in use by PID %%a. Terminating stale process...
        taskkill /F /PID %%a >nul 2>&1
    )
)

:: 4. Open default web browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: 5. Launch FastAPI application server
echo [INFO] Server running at: http://localhost:8000
echo [INFO] Press Ctrl+C in this window to stop the server.
echo.

".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-dir frontend

pause
