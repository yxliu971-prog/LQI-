@echo off
setlocal
cd /d "%~dp0"
if exist "dist\LQI\LQI.exe" (
  start "" "dist\LQI\LQI.exe"
  exit /b 0
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "main.py"
  exit /b 0
)
echo Run setup.bat first to restore the source environment.
pause
exit /b 1
