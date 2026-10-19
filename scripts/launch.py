"""Start this installation once, then open a locally generated login guide."""
import html
import ipaddress
import json
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parents[1]

def lan_addresses():
    candidates=[]
    if os.name=='nt':
        command="Get-NetIPConfiguration | Where-Object { $_.NetAdapter.Status -eq 'Up' -and $_.IPv4DefaultGateway } | Sort-Object @{Expression={if ($_.NetAdapter.HardwareInterface) {0} else {1}}} | ForEach-Object { $_.IPv4Address.IPAddress } | ConvertTo-Json -Compress"
        try:
            result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,timeout=12,creationflags=subprocess.CREATE_NO_WINDOW)
            value=json.loads(result.stdout) if result.returncode==0 and result.stdout.strip() else []
            candidates.extend([value] if isinstance(value,str) else value)
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
    try:candidates.extend(row[4][0] for row in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET))
    except OSError:pass
    addresses=[]
    for value in candidates:
        try:address=ipaddress.ip_address(value)
        except (ValueError,TypeError):continue
        # Proxy/TUN benchmark addresses are not reachable from teachers' devices.
        if address.version==4 and not (address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast or address in ipaddress.ip_network('198.18.0.0/15')) and value not in addresses:addresses.append(value)
    return addresses

def entry_html(local_url,teacher_urls):
    def card(title,url,note,style=""):
        safe=html.escape(url,quote=True)
        return f'<section class="{style}"><h2>{title}</h2><p>{note}</p><input readonly aria-label="{title}网址" value="{safe}"><div class="actions"><a href="{safe}" target="_blank" rel="noopener">打开网页</a><button type="button" onclick="copyUrl(this)">复制网址</button></div></section>'
    cards=''
    if teacher_urls:
        cards=card('校区统一登录网址',teacher_urls[0],'主管、老师都用这个网址。输入各自账号密码，自动进入对应工作区。','primary-entry')
        if len(teacher_urls)>1:
            cards+='<details class="other-networks"><summary>其它网络地址（上方网址无法打开时再尝试）</summary>'
            for index,url in enumerate(teacher_urls[1:],2):
                cards+=card(f'备用网络地址 {index}',url,'同样支持主管和教师账号登录。','secondary-entry')
            cards+='</details>'
    else:cards+='<section><h2>校区统一登录网址</h2><p class="warning">暂未取得可供其它设备访问的网址。请确认主机已连接校区网络，且系统允许局域网访问，再双击“开始”。</p></section>'
    cards+=card('主管备用网址',local_url,'仅在这台主机上使用；通用网址暂时打不开时可尝试。','local-backup')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EduPulse · 校区登录入口</title>
<style>*{box-sizing:border-box}body{margin:0;background:#161e24;color:#e9e5d7;font:18px/1.6 "Microsoft YaHei",sans-serif}main{max-width:1050px;margin:48px auto;padding:0 24px}h1,h2{color:#e0bf73}h1{font-size:32px}h2{font-size:23px;margin-top:0}p{color:#c3c8c9}.cards{display:grid;gap:20px}.primary-entry{padding:32px;border-color:#cbaa5b}.primary-entry h2{font-size:28px}.primary-entry input{font-size:clamp(20px,3vw,32px);font-weight:bold;padding:18px}.primary-entry .actions a{background:#a17b32}.local-backup{padding:16px 20px;background:#1b252c;border-color:#46515a;max-width:640px}.local-backup h2{font-size:18px;color:#c1c8cb;margin-bottom:6px}.local-backup p{font-size:15px;margin:6px 0 12px}.local-backup input{font-size:17px;padding:8px}.local-backup .actions{margin-top:10px}.local-backup button,.local-backup a{font-size:15px;padding:6px 14px;background:#27363e;border-color:#627079}.other-networks summary{cursor:pointer;color:#bec6ca}.other-networks section{margin-top:14px}.eyebrow{font-size:15px;color:#d1b16c;letter-spacing:2px}section{background:#222e35;border:1px solid #72613d;border-radius:12px;padding:26px}input{width:100%;font:20px/1.5 Consolas,monospace;padding:12px;color:#fff;background:#131c22;border:1px solid #65717a;border-radius:6px}.actions{display:flex;gap:12px;margin-top:18px}button,a{font:inherit;border-radius:6px;border:1px solid #b99a52;background:#8b6b2f;color:white;padding:9px 18px;text-decoration:none;cursor:pointer}button{background:#27363e}.note{padding:18px 0}.warning{color:#ffd18b}#message{min-height:32px;color:#e0bf73}small{color:#aeb8be}input:focus,button:focus,a:focus{outline:3px solid #e0bf73;outline-offset:3px}</style>
<main><h1>校区登录入口</h1><p>后台已启动。打开通用网址，或复制发给同事，就可以开始使用。</p><div class="cards">'''+cards+'''</div><p id="message" role="status" aria-live="polite"></p><div class="note"><p>使用通用网址的电脑、手机需要连接校区同一网络。网址可同时发给老师和其他主管。</p><p>后台运行期间请保持主机开机。关闭这个网页不会结束后台；需要停止时，双击“结束后台”。</p><p>网络或 IP 地址变化后，再次双击“开始”即可更新本页；无需先结束后台。</p><small>主管与老师使用同一个系统登录页，由各自账号决定进入哪个工作区。请通过私下方式分发账号密码。</small></div></main>
<script>async function copyUrl(button){const input=button.closest('section').querySelector('input');let copied=false;try{await navigator.clipboard.writeText(input.value);copied=true}catch(e){input.focus();input.select();try{copied=document.execCommand('copy')}catch(e){}}document.getElementById('message').textContent=copied?'网址已复制，可以粘贴发送。':'请选中上方网址，按 Ctrl+C 复制。'}</script></html>'''

def local_address(host,port,secure=False):
    address='127.0.0.1' if host in ('0.0.0.0','::','localhost') else host
    if ':' in address:address=f'[{address}]'
    return f"{'https' if secure else 'http'}://{address}:{port}/"

def healthy(url):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url+'api/health',timeout=2) as response:
            data=json.load(response)
            return data.get('status')=='ok' and data.get('version')=='1.2.2'
    except (OSError,ValueError):return False

def main():
    runpy.run_path(str(ROOT/'run.py'),run_name='launcher_config')
    host=os.getenv('EDUPULSE_HOST','0.0.0.0');port=int(os.getenv('EDUPULSE_PORT','8000'))
    if not 1<=port<=65535:raise ValueError('端口设置无效，请检查 .env')
    secure=bool(os.getenv('EDUPULSE_SSL_CERT') or os.getenv('EDUPULSE_SSL_KEY'))
    local=local_address(host,port,secure)
    logs=ROOT/'.logs';logs.mkdir(exist_ok=True)
    import msvcrt
    with (logs/'launcher.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('另一个启动窗口正在处理，请稍后再次双击“开始”。')
        verified=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/stop-service.ps1'),'-CheckOnly'],creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True)
        if verified.returncode:raise RuntimeError('无法确认端口上的程序属于本系统。请检查是否有其他程序占用端口，后台未作更改。')
        process=None
        if not healthy(local):
            # A verified listener may still be starting. Never start a second server.
            with socket.socket() as probe:
                probe.settimeout(2)
                occupied=probe.connect_ex((host if host not in ('0.0.0.0','::','localhost') else '127.0.0.1',port))==0
            if not occupied:
                with (logs/'service.out.log').open('ab') as out,(logs/'service.err.log').open('ab') as err:
                    process=subprocess.Popen([sys.executable,str(ROOT/'run.py'),'start'],cwd=ROOT,stdout=out,stderr=err,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(45):
                if healthy(local):break
                if process and process.poll() is not None:raise RuntimeError('后台启动失败。请确认已完成“首次运行”，错误记录保存在 .logs/service.err.log。')
                time.sleep(1)
            else:raise RuntimeError('后台尚未就绪，请稍后再次双击“开始”。错误记录保存在 .logs/service.err.log。')
        addresses=lan_addresses() if host in ('0.0.0.0','::') else ([host] if host not in ('127.0.0.1','localhost','::1') else [])
        urls=[local_address(address,port,secure) for address in addresses]
        page=logs/'登录入口.html';page.write_text(entry_html(local,urls),encoding='utf-8')
        if not webbrowser.open(page.as_uri()):print('请打开此登录入口：'+str(page))
        print('后台已运行，登录入口已打开。可关闭本启动窗口；结束服务请双击“结束后台”。')

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('启动未完成：'+str(error));sys.exit(1)
