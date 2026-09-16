@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ======================================================
echo     Smart Home AI Assistant - Windows Setup
echo ======================================================

:: 1. Check Python installation
echo.
echo [Step 1/5] Checking Python Installation...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python was not found in your PATH.
    echo Please install Python 3.9 - 3.12 from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python 3.9 or higher is required.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo Found compatible Python: %%i

:: 2. Create Virtual Environment
echo.
echo [Step 2/5] Setting up Virtual Environment (.venv)...
if not exist ".venv" (
    echo Creating .venv...
    python -m venv .venv
) else (
    echo .venv already exists.
)

if not exist ".venv\Scripts\python.exe" (
    echo Note: Incomplete .venv detected. Re-creating...
    rmdir /s /q .venv 2>nul
    python -m venv .venv
)

call .venv\Scripts\activate.bat

:: 3. Install Requirements
echo.
echo [Step 3/5] Installing dependencies from requirements.txt...
python -m pip install --upgrade pip setuptools wheel
pip install --prefer-binary -r requirements.txt

:: 4. Initialize Config and Directories
echo.
echo [Step 4/4] Initializing Config and Directories...
if not exist "data" mkdir data
if not exist "models\llm" mkdir models\llm
if not exist "models\tts" mkdir models\tts
if not exist "models\stt" mkdir models\stt

if not exist "config.json" (
    if exist "config.json.example" (
        copy config.json.example config.json >nul
        echo Created config.json from template.
    )
) else (
    echo config.json found.
)

if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo Created local .env from .env.example template.
    )
) else (
    echo .env found (kept local and private).
)

:: 5. Check and Download Local AI Models
echo.
echo [Step 5/5] Checking Local Offline AI Models...
if not exist "models\llm\Llama-3.2-3B-Instruct-Q4_K_M.gguf" (
    if not exist "models\llm\Llama-3.2-1B-Instruct-Q4_K_M.gguf" (
        echo Local model files not found. Starting automatic model download...
        python -m src.downloader
    ) else (
        echo Local LLM model found in models\llm.
    )
) else (
    echo Local LLM model found in models\llm.
)

echo.
echo ======================================================
echo        Setup Completed Successfully!
echo ======================================================
echo To start the assistant on Windows, run:
echo    run.bat
echo.
pause
