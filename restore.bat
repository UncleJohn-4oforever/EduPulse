@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: restore.bat "D:\path\backup.sqlite3"
  exit /b 1
)
echo Stop EduPulse first. Existing data will be overwritten.
set /p "EDUPULSE_RESTORE_APPROVAL=Type RESTORE to confirm: "
if not "%EDUPULSE_RESTORE_APPROVAL%"=="RESTORE" exit /b 1
.venv\Scripts\python.exe run.py backup
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe run.py restore "%~1" --confirm
pause
