@echo off
setlocal
cd /d "%~dp0"
call "%~dp0stop.bat" --no-pause
if errorlevel 1 (
  echo Restart cancelled. Fix the stop error above first.
  pause
  exit /b 1
)
call "%~dp0start.bat"
