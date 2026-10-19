"""Bundle the unchanged, verified PSF installer beside a clean EduPulse release."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
INSTALLER_NAME='python-3.12.10-amd64.exe'
INSTALLER_SHA256='67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb'
SOURCE='https://www.python.org/ftp/python/3.12.10/'+INSTALLER_NAME

def main():
    parser=argparse.ArgumentParser(description='生成含 Python 官方安装程序的校区完整分发包')
    parser.add_argument('--installer',type=Path,required=True)
    parser.add_argument('--license',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    installer=args.installer.read_bytes()
    if hashlib.sha256(installer).hexdigest()!=INSTALLER_SHA256:raise ValueError('Python installer hash mismatch; package cancelled')
    license_text=args.license.read_text(encoding='utf-8-sig')
    if 'PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2' not in license_text:raise ValueError('Missing Python license')
    (ROOT/'exports').mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix='.zip',prefix='edupulse-base-',dir=ROOT/'exports',delete=False) as temporary:base=Path(temporary.name)
    try:
        subprocess.run([sys.executable,str(ROOT/'scripts/package.py'),'--output',str(base)],check=True)
        install_bat='''@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
  echo 本机已有 Python 3.12（64 位），可直接打开 EduPulse 文件夹，双击“首次运行”。
  pause
  exit /b 0
)
echo 即将打开 Python 官方安装程序。请保留 Python Launcher，点击 Install Now 完成安装。
echo 安装完成后，打开旁边的 EduPulse 文件夹，双击“首次运行”。
start "" /wait "%~dp0python-3.12.10-amd64.exe" InstallAllUsers=0 Include_launcher=1 InstallLauncherAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
if errorlevel 1 (
  echo 安装程序已退出。若安装未完成，请重新运行，或将提示信息发给技术人员。
  pause
  exit /b 1
)
echo Python 安装程序已结束。请打开 EduPulse 文件夹，双击“首次运行”。
pause
'''
        guide='''EduPulse 校区完整分发包（含 Python 官方安装程序）

请先把整个压缩包完整解压到电脑，例如 D:\\校区教学系统。

一、这台电脑没有 Python，或不确定是否安装过？
打开 Python 文件夹，双击“安装Python.bat”。
若已安装合适的 Python，会直接提示跳过；否则会打开官方安装程序。
按提示点击 Install Now（立即安装），等待安装完成。保留 Python Launcher 选项。
也可直接双击 python-3.12.10-amd64.exe 安装。

二、首次使用 EduPulse
打开 EduPulse 文件夹，双击“首次运行.bat”，创建本校区教学主管账号和密码。
再双击“开始.bat”，自动打开校区登录入口。

三、以后使用
只需打开 EduPulse 文件夹，双击“开始.bat”。无需重复安装 Python。
需要停止或重启时，使用“结束后台.bat”或“重启.bat”。
复制醒目的“校区统一登录网址”，发给同一校区网络中的老师或其他主管。
所有角色使用同一个网址，凭各自账号密码进入相应工作区。
老师和其他主管的设备只需浏览器，不必安装这个包。

本包供 Windows 64 位校区主机使用，适合 Windows 10/11。
Python 安装程序和 EduPulse 依赖均已随包提供，不必另外下载 Python 或 Node.js。
本包不含原校区的教师账号、学生名单、数据库及密码。
详细说明见 EduPulse 文件夹中的“使用前请先看.txt”。
'''
        source=f'Python 3.12.10 Windows 64-bit installer\nOfficial source: {SOURCE}\nRelease: https://www.python.org/downloads/release/python-31210/\nSHA256: {INSTALLER_SHA256}\nDigital signature verified during preparation: Valid; Python Software Foundation\nThe official installer is redistributed unchanged. It is not automatically executed by packaging.\n'
        output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(base) as original,ZipFile(output,'w',ZIP_DEFLATED,compresslevel=9) as result:
            for item in original.infolist():result.writestr(item,original.read(item.filename))
            result.writestr('Python/'+INSTALLER_NAME,installer)
            result.writestr('Python/安装Python.bat',install_bat.replace('\n','\r\n').encode('utf-8'))
            result.writestr('Python/Python许可证.txt',license_text.encode('utf-8-sig'))
            result.writestr('Python/来源与校验.txt',source.encode('utf-8-sig'))
            result.writestr('先看这里.txt',guide.replace('\n','\r\n').encode('utf-8-sig'))
        with ZipFile(output) as result:
            assert result.testzip() is None
            assert hashlib.sha256(result.read('Python/'+INSTALLER_NAME)).hexdigest()==INSTALLER_SHA256
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        output.with_name(output.name+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='utf-8')
        print(f'{output}\n{output.stat().st_size/1024/1024:.2f} MiB\nSHA256 {digest}')
    finally:base.unlink(missing_ok=True)

if __name__=='__main__':main()
