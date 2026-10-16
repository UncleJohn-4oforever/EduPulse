"""Production entry point: one process serves the prebuilt frontend and API."""
import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
config=ROOT/'.env'
if config.exists():
    for line in config.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        key,separator,value=line.partition('=')
        if separator and key.strip().startswith('EDUPULSE_'):
            os.environ.setdefault(key.strip(),os.path.expandvars(value.strip().strip('"').strip("'")))
sys.path.insert(0,str(ROOT/'backend'))
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]!='start':
        from app.cli import main
        main()
    else:
        import uvicorn
        from app.db import init_db,SessionLocal,User
        init_db()
        with SessionLocal() as db:
            if not db.query(User).filter_by(role='admin',enabled=True).first():
                print('请先安全初始化主管：python run.py init-admin');sys.exit(1)
        if not (ROOT/'frontend/dist/index.html').exists():
            print('请先构建前端：cd frontend && npm ci && npm run build');sys.exit(1)
        ssl={}
        if os.getenv('EDUPULSE_SSL_CERT') or os.getenv('EDUPULSE_SSL_KEY'):
            ssl={'ssl_certfile':os.getenv('EDUPULSE_SSL_CERT'),'ssl_keyfile':os.getenv('EDUPULSE_SSL_KEY')}
        uvicorn.run('app.main:app',host=os.getenv('EDUPULSE_HOST','0.0.0.0'),port=int(os.getenv('EDUPULSE_PORT','8000')),workers=1,proxy_headers=False,**ssl)
