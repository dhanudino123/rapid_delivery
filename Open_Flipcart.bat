@echo off
setlocal
cd /d "%~dp0"
title Flipcart server

set PY=
where py >nul 2>nul && set PY=py
if "%PY%"=="" where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo Python is not installed. Download it from https://www.python.org/downloads/
  echo and tick "Add Python to PATH" during install. Then run this file again.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo First run: setting up, please wait...
  %PY% -m venv .venv
  if errorlevel 1 ( echo Could not create virtual environment. & pause & exit /b 1 )
  .venv\Scripts\python -m pip install -r requirements.txt
  if errorlevel 1 ( echo Could not install Flask - check your internet connection. & pause & exit /b 1 )
)

echo Starting Flipcart at http://localhost:8000  (keep this window open)
start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:8000"
.venv\Scripts\python app.py
pause
