@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe ( echo Run Open_Flipcart.bat once first. & pause & exit /b 1 )
set /p KEY=Pexels API key (press Enter to skip and use Wikimedia): 
if "%KEY%"=="" (.venv\Scripts\python fetch_images.py) else (.venv\Scripts\python fetch_images.py --pexels-key %KEY%)
pause
