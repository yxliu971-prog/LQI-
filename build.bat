@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto fail
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe scripts\build_release.py
if errorlevel 1 goto fail
echo Build complete. See the releases directory.
pause
exit /b 0
:fail
echo Build failed. Run setup.bat and inspect the error above.
pause
exit /b 1
