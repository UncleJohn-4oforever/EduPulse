@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先双击“首次运行”，完成安装及主管账号设置。
  pause
  exit /b 1
)
echo 正在启动 EduPulse 并打开登录入口，请稍候……
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0scripts\launch.py"
if errorlevel 1 (
  pause
  exit /b 1
)
exit /b 0
