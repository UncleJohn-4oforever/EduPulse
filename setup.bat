@echo off
setlocal
cd /d "%~dp0"
echo EduPulse 1.2 setup - requires Python 3.12 x64.
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 (
  echo Please install Python 3.12 x64 with the Python launcher, then retry.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import sys, struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
  if errorlevel 1 (
    echo Repairing the existing Python environment...
    py -3.12 -m venv --upgrade .venv
    if errorlevel 1 goto failed
  )
) else (
  py -3.12 -m venv .venv
)
if errorlevel 1 goto failed
if exist "backend\wheels-win-py312\fastapi-0.115.12-py3-none-any.whl" (
  .venv\Scripts\python.exe -m pip install --no-index --find-links backend\wheels-win-py312 -r backend\requirements.lock.txt
) else (
  .venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
)
if errorlevel 1 goto failed
.venv\Scripts\python.exe run.py init-db
if errorlevel 1 goto failed
.venv\Scripts\python.exe run.py init-admin
if errorlevel 1 (
  echo If an administrator already exists, use start.bat. Otherwise retry setup.
  pause
  exit /b 1
)
echo Setup complete. Run start.bat to launch EduPulse.
pause
exit /b 0
:failed
echo Setup failed. See the error above.
pause
exit /b 1
