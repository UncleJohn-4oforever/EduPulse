@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe run.py backup
if errorlevel 1 exit /b 1
