"""Explicit release boundaries: local business documents are never distributable."""
from pathlib import Path

ROOT_FILES={'.env.example','README.md','run.py','setup.bat','start.bat','start.sh',
            'stop.bat','restart.bat','backup.bat','restore.bat','test.bat','.gitignore'}
EXCLUDED={'.git','.venv','node_modules','__pycache__','.pytest_cache','exports','backups'}

def release_files(root):
    root=Path(root).resolve()
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):continue
        rel=path.relative_to(root);parts=rel.parts
        if any(p in EXCLUDED or p.startswith('.') and p not in {'.env.example','.gitignore'} for p in parts):continue
        allowed=len(parts)==1 and path.name in ROOT_FILES
        if len(parts)>1:
            top=parts[0];suffix=path.suffix.lower()
            allowed|=top=='backend' and ((parts[1] in {'app','tests'} and suffix=='.py') or (len(parts)==2 and path.name in {'requirements.txt','requirements.lock.txt'}) or (parts[1]=='wheels-win-py312' and suffix=='.whl'))
            allowed|=top=='frontend' and ((parts[1] in {'src','dist'} and suffix in {'.ts','.tsx','.js','.css','.html','.svg','.woff','.woff2','.png','.ico'}) or (len(parts)==2 and suffix in {'.json','.js','.ts','.html'}))
            allowed|=top=='scripts' and len(parts)==2 and suffix in {'.py','.ps1','.cjs'}
            allowed|=top=='docs' and ((len(parts)==2 and suffix=='.md') or (len(parts)==3 and parts[1]=='licenses' and suffix in {'.txt','.md'}))
        if allowed:yield path
