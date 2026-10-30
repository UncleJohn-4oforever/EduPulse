@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 未找到运行环境，请确认您正在原校区主机及原项目文件夹中操作。
  pause
  exit /b 1
)
echo 此操作仅重置选定教学主管的密码，不删除班级和学生数据。
echo 请使用平时启动系统的同一个 Windows 用户运行。
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0run.py" reset-admin-password
set "EDUPULSE_RESET_RESULT=%ERRORLEVEL%"
pause
exit /b %EDUPULSE_RESET_RESULT%
