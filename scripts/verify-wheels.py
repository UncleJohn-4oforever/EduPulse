"""Check dependency closure of bundled Windows Python3.12 wheels without installation."""
from pathlib import Path
from zipfile import ZipFile
from email.parser import Parser
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.markers import default_environment
root=Path(__file__).resolve().parents[1]
env=default_environment()|{'os_name':'nt','sys_platform':'win32','platform_system':'Windows','platform_machine':'AMD64','python_version':'3.12','python_full_version':'3.12.14','implementation_name':'cpython','extra':''}
wheels={}
for path in (root/'backend/wheels-win-py312').glob('*.whl'):
    with ZipFile(path) as z:
        assert z.testzip() is None,path
        meta=Parser().parsestr(z.read(next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))).decode())
        wheels[canonicalize_name(meta['Name'])]=(meta['Version'],meta.get_all('Requires-Dist',[]))
checks=[]
for line in (root/'backend/requirements.lock.txt').read_text().splitlines():
    if line.strip() and not line.startswith('#'): checks.append(Requirement(line))
for version,dependencies in wheels.values(): checks.extend(Requirement(r) for r in dependencies)
for req in checks:
    if req.marker and not req.marker.evaluate(env): continue
    key=canonicalize_name(req.name)
    assert key in wheels,f'Missing Windows dependency: {req}'
    assert wheels[key][0] in req.specifier,f'Incompatible version: {req}, bundled {wheels[key][0]}'
print(f'PASS: {len(wheels)} Windows Python3.12 wheels, dependency closure and ZIP integrity checked.')
