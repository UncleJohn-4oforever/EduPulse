@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo 正在结束 EduPulse 后台。已保存的账号和数据会保留。
echo 尚未保存的内容请先保存；结束可能中断正在提交的请求。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-service.ps1"
set "EDUPULSE_STOP_RESULT=%ERRORLEVEL%"
if /I not "%~1"=="--no-pause" pause
exit /b %EDUPULSE_STOP_RESULT%
