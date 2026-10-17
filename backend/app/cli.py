import argparse, getpass, sqlite3, os, sys
from pathlib import Path
from datetime import datetime
from .db import init_db, SessionLocal, User, DATA, engine, Base
from .migrations import SCHEMA_VERSION
from .security import ph, audit

def main():
    parser=argparse.ArgumentParser(description='EduPulse 数据管理（不提供公开默认密码）')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init-admin'); p.add_argument('--username',default='admin'); p.add_argument('--name',default='教学主管')
    p=sub.add_parser('backup'); p.add_argument('--output')
    p=sub.add_parser('restore'); p.add_argument('file'); p.add_argument('--confirm',action='store_true')
    sub.add_parser('init-db')
    args=parser.parse_args()
    if args.command=='restore':
        if not args.confirm: parser.error('请先停止服务并备份现有数据库，然后加 --confirm')
        src=Path(args.file)
        if not src.is_file(): parser.error('备份文件不存在')
        target_path=DATA/'edupulse.sqlite3'
        if src.resolve()==target_path.resolve() or (target_path.exists() and src.samefile(target_path)):
            parser.error('不能将当前数据库恢复到自身，请选择独立备份文件')
        with sqlite3.connect(src) as check:
            if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok': parser.error('备份完整性检查失败')
            tables={row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'schema_versions' not in tables:parser.error('备份缺少版本信息')
            version=check.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0]
            if not version or version>SCHEMA_VERSION:parser.error('备份数据库版本不受支持')
            for table in Base.metadata.sorted_tables:
                # Older backups predate the optional workspace display name.
                if table.name=='workspace_settings' and table.name not in tables:continue
                if version<5 and table.name=='frozen_records':continue
                if version<3 and table.name=='student_weekly_slots':continue
                columns={row[1] for row in check.execute(f'PRAGMA table_info("{table.name}")')}
                required={column.name for column in table.columns}
                if version<4 and table.name=='classes':required.discard('name_is_manual')
                if version<3 and table.name in ('users','dictionaries'):required.discard('deleted_at')
                if table.name not in tables or not required<=columns:parser.error('备份缺少必要表或字段，不能恢复')
            if check.execute('PRAGMA foreign_key_check').fetchall(): parser.error('备份外键完整性检查失败')
        engine.dispose()
        with sqlite3.connect(src) as origin, sqlite3.connect(DATA/'edupulse.sqlite3') as target:
            origin.backup(target)
            # Backups must never resurrect previously logged-out/revoked sessions.
            target.execute('DELETE FROM sessions')
            target.execute('UPDATE users SET session_version=session_version+1')
        print('恢复成功。重启服务前请检查数据。'); return
    init_db()
    if args.command=='init-admin':
        if not args.username or len(args.username)>80 or not args.name or len(args.name)>80: parser.error('账号或姓名长度无效')
        with SessionLocal.begin() as db:
            if db.query(User).filter_by(username=args.username).first(): parser.error('账号已存在；不会自动重置现有管理员')
            password=getpass.getpass('管理员密码（至少14位，含字母和数字）：')
            if not 14<=len(password)<=256 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password): parser.error('密码须14至256位，含字母和数字')
            if password!=getpass.getpass('再次输入密码：'): parser.error('两次密码不一致')
            u=User(username=args.username,display_name=args.name,role='admin',password_hash=ph.hash(password)); db.add(u); db.flush(); audit(db,u,'admin.initialize','user',u.id)
        print('管理员创建成功；请妥善保管密码。')
    elif args.command=='backup':
        output=Path(args.output) if args.output else DATA/'backups'/f"edupulse-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
        output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists(): parser.error('备份文件已存在，请使用新文件名')
        with sqlite3.connect(DATA/'edupulse.sqlite3') as origin, sqlite3.connect(output) as target:
            origin.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise RuntimeError('备份完整性检查失败')
        print('备份完成：',output)
    else: print(f'数据库 schema v{SCHEMA_VERSION} 已创建/核验')
if __name__=='__main__': main()
