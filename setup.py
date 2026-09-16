#!/usr/bin/env python3
"""
SmartHome Assistant — Setup & Onboarding Wizard Entrypoint
Run this script to configure your AI assistant parameters and download models via an intuitive web UI.
Usage: python setup.py
"""
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(SCRIPT_DIR, ".venv", "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(SCRIPT_DIR, ".venv", "bin", "python")

# If .venv exists and we are not currently running under it, re-exec with .venv python
if os.path.exists(VENV_PYTHON) and os.path.normcase(sys.executable) != os.path.normcase(VENV_PYTHON):
    try:
        os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)
    except Exception:
        import subprocess
        sys.exit(subprocess.call([VENV_PYTHON] + sys.argv))

sys.path.insert(0, SCRIPT_DIR)

from src.setup_wizard import launch_setup_wizard

if __name__ == "__main__":
    launch_setup_wizard()
