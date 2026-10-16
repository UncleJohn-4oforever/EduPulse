"""Create a fresh isolated browser-test database. Never seed production data."""
import os, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not os.environ.get('EDUPULSE_DATA_DIR'):
    print('请显式设置隔离的 EDUPULSE_DATA_DIR（不能使用正式数据目录）');sys.exit(1)
data=Path(os.environ['EDUPULSE_DATA_DIR'])
if (data/'edupulse.sqlite3').exists():
    print('测试目录已有数据库，拒绝覆盖。请使用新的空目录。');sys.exit(1)
sys.path.insert(0,str(root/'backend'))
from app.db import init_db,SessionLocal,User
from app.security import ph
init_db()
with SessionLocal.begin() as db:
    db.add(User(username='browser-admin',display_name='验收主管',role='admin',password_hash=ph.hash('BrowserTestOnly2026')))
print('仅隔离测试管理员已创建；本脚本不会被启动程序自动运行。')
