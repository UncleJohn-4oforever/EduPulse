@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
echo EduPulse - open http://127.0.0.1:8000 on this PC.
echo Other devices: http://LAN-IP:8000. Custom port is in .env.
echo Keep this window open. Press Ctrl+C to stop safely.
"%~dp0.venv\Scripts\python.exe" "%~dp0run.py" start
pause
