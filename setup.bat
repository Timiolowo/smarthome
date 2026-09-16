@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv" (
    echo Virtual environment not found. Running installer first...
    call install.bat
)

call .venv\Scripts\activate.bat
python setup.py %*
