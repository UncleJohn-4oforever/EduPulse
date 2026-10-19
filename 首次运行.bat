@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo EduPulse 首次运行：安装环境并创建教学主管账号。
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 (
  echo 请先安装 Python 3.12（64 位，并勾选 Python Launcher），然后重新双击本文件。
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import sys, struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
  if errorlevel 1 (
    echo 正在修复已有运行环境……
    py -3.12 -m venv --upgrade .venv
    if errorlevel 1 goto failed
  )
) else (
  py -3.12 -m venv .venv
)
if errorlevel 1 goto failed
if exist "backend\wheels-win-py312\fastapi-0.115.12-py3-none-any.whl" (
  .venv\Scripts\python.exe -m pip install --no-index --find-links backend\wheels-win-py312 -r backend\requirements.lock.txt
) else (
  .venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
)
if errorlevel 1 goto failed
.venv\Scripts\python.exe run.py init-db
if errorlevel 1 goto failed
.venv\Scripts\python.exe run.py init-admin
if errorlevel 1 (
  echo 如果已创建过主管账号，请双击“开始”。否则请检查上方提示后重试。
  pause
  exit /b 1
)
echo 首次设置完成！以后请双击“开始”，自动打开登录入口。
pause
exit /b 0
:failed
echo 首次设置未完成，请查看上方错误提示。
pause
exit /b 1
