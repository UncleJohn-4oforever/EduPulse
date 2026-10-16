"""Schema v2: never reuse student/class identities after deletion."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from sqlalchemy.schema import CreateTable

SCHEMA_VERSION=5

def migrate_stable_ids(engine,data_dir,*tables):
    connection=engine.raw_connection()
    db=connection.driver_connection
    try:
        current=db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0] or 1
        if current>SCHEMA_VERSION: raise RuntimeError('数据库版本比程序新，请使用对应版本的程序')
        if current>=2:return
        rebuild=[table for table in tables if 'AUTOINCREMENT' not in db.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?',('table',table.name)).fetchone()[0].upper()]
        if rebuild:
            backup_dir=data_dir/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
            path=backup_dir/f'migration-v1-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.sqlite3'
            with sqlite3.connect(path) as destination: db.backup(destination)
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('BEGIN IMMEDIATE')
        # A different startup may have completed the migration while we waited.
        current=db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0] or 1
        if current>SCHEMA_VERSION:raise RuntimeError('数据库版本比程序新，请使用对应版本的程序')
        if current>=2:
            db.rollback();return
        rebuild=[table for table in tables if 'AUTOINCREMENT' not in db.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?',('table',table.name)).fetchone()[0].upper()]
        high={table.name:db.execute(f'SELECT COALESCE(MAX(id),0) FROM "{table.name}"').fetchone()[0] for table in tables}
        # Deleted IDs still present in snapshots/audit must not get reused either.
        for (raw,) in db.execute('SELECT data FROM broadcast_snapshots'):
            snapshot=json.loads(raw)
            for name in high:
                high[name]=max(high[name],max((row['id'] for row in snapshot.get(name,[])),default=0))
        for kind,entity,raw in db.execute('SELECT entity_type,entity_id,metadata_json FROM audit_logs'):
            metadata=json.loads(raw)
            if kind in ('class','student') and str(entity).isdigit():
                name='classes' if kind=='class' else 'students';high[name]=max(high[name],int(entity))
            ids=[metadata.get('source_id',0),*metadata.get('student_ids',[])]
            high['students']=max(high['students'],*(int(value) for value in ids))
        for table in rebuild:
            temp='__v2_'+table.name
            ddl=str(CreateTable(table).compile(dialect=engine.dialect))
            ddl=ddl.replace('CREATE TABLE '+table.name,'CREATE TABLE "'+temp+'"',1)
            db.execute(ddl)
            source_columns={row[1] for row in db.execute(f'PRAGMA table_info("{table.name}")')}
            columns=','.join('"'+column.name+'"' for column in table.columns if column.name in source_columns)
            db.execute(f'INSERT INTO "{temp}" ({columns}) SELECT {columns} FROM "{table.name}"')
            extras=db.execute('SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN (?,?) AND sql IS NOT NULL',(table.name,'index','trigger')).fetchall()
            db.execute(f'DROP TABLE "{table.name}"')
            db.execute(f'ALTER TABLE "{temp}" RENAME TO "{table.name}"')
            for (sql,) in extras:db.execute(sql)
        for name,maximum in high.items():
            sequence=db.execute('SELECT seq FROM sqlite_sequence WHERE name=?',(name,)).fetchone()
            if sequence: db.execute('UPDATE sqlite_sequence SET seq=? WHERE name=?',(max(sequence[0],maximum),name))
            elif maximum:db.execute('INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)',(name,maximum))
        if db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('数据库外键检查失败，升级已回滚')
        db.execute('INSERT INTO schema_versions(version,applied_at) VALUES(?,?)',(2,datetime.now(timezone.utc).isoformat()))
        db.commit()
    except Exception:
        db.rollback();raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')
        connection.close()


def legacy_slot_number(label):
    """Map only unambiguous old labels. Never guess arbitrary names."""
    import re
    label=label.strip()
    match=re.fullmatch(r'(?:第)?([1-6一二三四五六])(?:档|档位)?',label)
    if not match:return None
    digit=match.group(1)
    return int(digit) if digit.isdigit() else '一二三四五六'.index(digit)+1


def migrate_frozen_records(engine):
    # The new additive table is created by metadata.create_all; no live rows change.
    with engine.begin() as db:
        current=db.exec_driver_sql('SELECT MAX(version) FROM schema_versions').scalar() or 1
        if current>SCHEMA_VERSION:raise RuntimeError('数据库版本比程序新，请使用对应版本')
        if current<5:db.exec_driver_sql('INSERT INTO schema_versions(version,applied_at) VALUES(5,?)',(datetime.now(timezone.utc).isoformat(),))


def migrate_student_schedules(engine,data_dir):
    connection=engine.raw_connection();db=connection.driver_connection
    try:
        current=db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0] or 1
        if current>SCHEMA_VERSION:raise RuntimeError('数据库版本比程序新，请使用对应版本')
        if current>=3:return
        old_columns={table:{row[1] for row in db.execute(f'PRAGMA table_info("{table}")')} for table in ('users','dictionaries')}
        if any('deleted_at' not in columns for columns in old_columns.values()) or db.execute('SELECT EXISTS(SELECT 1 FROM users)').fetchone()[0]:
            directory=data_dir/'backups';directory.mkdir(parents=True,exist_ok=True)
            path=directory/f'migration-v2-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.sqlite3'
            with sqlite3.connect(path) as backup:db.backup(backup)
        db.execute('BEGIN IMMEDIATE')
        current=db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0] or 1
        if current>SCHEMA_VERSION:raise RuntimeError('数据库版本比程序新，请使用对应版本')
        if current>=3:
            db.rollback();return
        old_columns={table:{row[1] for row in db.execute(f'PRAGMA table_info("{table}")')} for table in ('users','dictionaries')}
        for table,columns in old_columns.items():
            if 'deleted_at' not in columns:db.execute(f'ALTER TABLE "{table}" ADD COLUMN deleted_at VARCHAR')
        db.execute('''CREATE TABLE IF NOT EXISTS student_weekly_slots (
            id INTEGER NOT NULL PRIMARY KEY, enrollment_id INTEGER NOT NULL REFERENCES enrollments(id),
            weekday INTEGER NOT NULL CHECK(weekday BETWEEN 1 AND 7),
            slot_number INTEGER CHECK(slot_number IS NULL OR slot_number BETWEEN 1 AND 6),
            slot_label VARCHAR(80) NOT NULL, start_time VARCHAR, end_time VARCHAR)''')
        for enrollment,weekday,label,start,end in db.execute('''SELECT e.id,w.weekday,w.slot_label,w.start_time,w.end_time
                FROM enrollments e JOIN weekly_slots w ON e.class_id=w.class_id ORDER BY e.id,w.id''').fetchall():
            number=legacy_slot_number(label)
            db.execute('''INSERT INTO student_weekly_slots(enrollment_id,weekday,slot_number,slot_label,start_time,end_time)
                VALUES(?,?,?,?,?,?)''',(enrollment,weekday,number,f'第{number}档' if number else label,start,end))
        if db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('外键检查失败，升级已回滚')
        db.execute('INSERT INTO schema_versions(version,applied_at) VALUES(3,?)',(datetime.now(timezone.utc).isoformat(),))
        db.commit()
    except Exception:db.rollback();raise
    finally:connection.close()


def migrate_class_names(engine, data_dir):
    """v4: preserve legacy names; persist explicit manual/automatic naming."""
    connection=engine.raw_connection();db=connection.driver_connection
    try:
        current=db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0] or 1
        if current>SCHEMA_VERSION:raise RuntimeError('数据库版本比程序新，请使用对应版本')
        if current>=4:return
        columns={row[1] for row in db.execute('PRAGMA table_info(classes)')}
        if 'name_is_manual' not in columns:
            directory=data_dir/'backups';directory.mkdir(parents=True,exist_ok=True)
            path=directory/f'migration-v3-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.sqlite3'
            with sqlite3.connect(path) as backup:db.backup(backup)
        db.execute('BEGIN IMMEDIATE')
        current=db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0] or 1
        if current>SCHEMA_VERSION:raise RuntimeError('数据库版本比程序新，请使用对应版本')
        if current>=4:
            db.rollback();return
        columns={row[1] for row in db.execute('PRAGMA table_info(classes)')}
        if 'name_is_manual' not in columns:
            db.execute('ALTER TABLE classes ADD COLUMN name_is_manual BOOLEAN NOT NULL DEFAULT 1')
        if db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('外键检查失败，升级已回滚')
        db.execute('INSERT INTO schema_versions(version,applied_at) VALUES(4,?)',(datetime.now(timezone.utc).isoformat(),))
        db.commit()
    except Exception:db.rollback();raise
    finally:connection.close()
