@echo off
setlocal
cd /d "%~dp0backend"
..\.venv\Scripts\python.exe -m pytest -q
pause
