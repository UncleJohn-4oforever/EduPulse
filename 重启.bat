@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
call "%~dp0结束后台.bat" --no-pause
if errorlevel 1 (
  echo 结束后台失败，已取消重启。请先处理上方提示。
  pause
  exit /b 1
)
call "%~dp0开始.bat"
