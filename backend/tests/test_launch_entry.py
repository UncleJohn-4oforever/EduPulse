import importlib.util
from pathlib import Path
from unittest.mock import patch
from test_acceptance import reset

spec=importlib.util.spec_from_file_location('launch',Path(__file__).resolve().parents[2]/'scripts/launch.py')
launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)


def test_custom_port_local_binding_and_html_safety():
    assert launch.local_address('0.0.0.0',8123)=='http://127.0.0.1:8123/'
    assert launch.local_address('192.168.1.20',8443,True)=='https://192.168.1.20:8443/'
    assert launch.local_address('::1',8443,True)=='https://[::1]:8443/'
    page=launch.entry_html('http://127.0.0.1:8123/',['http://192.168.1.20:8123/','http://10.0.0.2:8123/'])
    assert page.count('onclick="copyUrl(this)"')==3
    assert 'http://192.168.1.20:8123/' in page and 'http://10.0.0.2:8123/' in page
    assert '&quot;&gt;&lt;script&gt;' in launch.entry_html('\"><script>',[])
    assert '暂未取得' in launch.entry_html('http://127.0.0.1:8123/',[])


def test_network_detection_filters_loopback_link_local_duplicates_and_bad_addresses():
    rows=[(None,None,None,None,(ip,0)) for ip in ['127.0.0.1','169.254.1.2','198.18.0.1','192.168.5.8','192.168.5.8','10.0.0.8','0.0.0.0','invalid']]
    with patch.object(launch.socket,'getaddrinfo',return_value=rows),patch.object(launch.subprocess,'run',side_effect=OSError):
        assert launch.lan_addresses()==['192.168.5.8','10.0.0.8']


def test_release_contains_the_chinese_launchers():
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('release_files',root/'scripts/release_files.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
    assert {'首次运行.bat','开始.bat','结束后台.bat','重启.bat'}<=release.ROOT_FILES
    for name in ['首次运行.bat','开始.bat','结束后台.bat','重启.bat']:
        raw=(root/name).read_bytes()
        assert raw.startswith(b'@echo off\r\nchcp 65001 >nul\r\n')
        assert b'\n' not in raw.replace(b'\r\n',b'')
