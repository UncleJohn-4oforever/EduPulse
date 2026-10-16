@echo off
setlocal
cd /d "%~dp0"
echo Stopping EduPulse. Active requests may be interrupted.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-service.ps1"
set "EDUPULSE_STOP_RESULT=%ERRORLEVEL%"
if /I not "%~1"=="--no-pause" pause
exit /b %EDUPULSE_STOP_RESULT%
