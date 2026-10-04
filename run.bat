@echo off
setlocal
title ScamShield Bharat
cd /d "%~dp0backend"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 was not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this again.
  pause
  exit /b 1
)
if not exist .venv\Scripts\activate.bat (
  echo Setting up for the first time...
  %PY% -m venv .venv || (echo Could not create the virtual environment. & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt || (echo Package install failed. Check your internet connection and try again. & pause & exit /b 1)
where tesseract >nul 2>nul || if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" echo NOTE: Tesseract OCR is not installed, so screenshot reading is off. Everything else works. See README.
echo.
echo ScamShield is starting. Open http://localhost:8000 in Chrome or Edge. Close this window or press Ctrl+C to stop.
echo.
python -m uvicorn app.main:app --port 8000
pause
