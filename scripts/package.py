"""Build a clean ZIP release; never includes runtime databases or credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib, json, argparse
from release_files import release_files
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='生成不含运行数据的交付包')
parser.add_argument('--output',type=Path,default=root.parent/'EduPulse-1.2.2-Windows.zip')
out=parser.parse_args().output.resolve()
out.parent.mkdir(parents=True,exist_ok=True)
files=list(release_files(root))
manifest={str(p.relative_to(root)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
manifest_file=root/'PACKAGE_MANIFEST.json'
manifest_file.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
files.append(manifest_file)
with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
    for p in files: z.write(p,'EduPulse/'+str(p.relative_to(root)))
with ZipFile(out) as z:
    assert z.testzip() is None
    assert 'EduPulse/frontend/dist/index.html' in z.namelist()
    assert 'EduPulse/setup.bat' in z.namelist()
    assert not any(n.endswith(('.sqlite3','.db','.env')) for n in z.namelist())
checksum=hashlib.sha256(out.read_bytes()).hexdigest()
(out.parent/(out.name+'.sha256')).write_text(checksum+'  '+out.name+'\n')
print(f'{out}\n{len(files)} files · {out.stat().st_size/1024/1024:.2f} MiB\nSHA256 {checksum}')
