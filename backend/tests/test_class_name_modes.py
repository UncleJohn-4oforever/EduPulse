import json
import sqlite3
import subprocess
import sys
import os
from sqlalchemy import create_engine
from test_acceptance import reset, setup, student, body_of, broadcast
from app.db import Base, now
from app.migrations import migrate_class_names, migrate_stable_ids, migrate_student_schedules


def test_auto_and_manual_names_survive_save_and_snapshot():
    admin, teachers, campus, subject, _ = setup()
    teacher = teachers[0][1]
    sid = student(teacher, campus)
    body = {'display_name': '旧自动名称', 'name_is_manual': False, 'subject_id': subject, 'capacity': 3,
            'students': [{'student_id': sid, 'weekly_slots': [{'weekday': 6, 'slot_number': 1}]}]}
    r = teacher.post('/api/teacher/classes', json=body)
    assert r.status_code == 200, r.text
    room = r.json()
    assert room['display_name'] == '周六一档' and room['name_is_manual'] is False
    bid = broadcast(admin, campus)
    admin.post(f'/api/admin/broadcasts/{bid}/close')
    snapshot = admin.get(f'/api/admin/broadcasts/{bid}/snapshot').json()
    body = body_of(room) | {'name_is_manual': False}
    body['students'][0]['weekly_slots'][0]['weekday'] = 3
    r = teacher.patch(f"/api/teacher/classes/{room['id']}", json=body)
    assert r.status_code == 200, r.text
    assert r.json()['display_name'] == '周三一档'
    # An explicitly typed name equal to a generated name is still manual.
    body = body_of(r.json()) | {'name_is_manual': True}
    body['students'][0]['weekly_slots'][0]['weekday'] = 7
    r = teacher.patch(f"/api/teacher/classes/{room['id']}", json=body)
    assert r.status_code == 200 and r.json()['display_name'] == '周三一档'
    assert r.json()['name_is_manual'] is True
    # Older clients have no mode field: preserve their submitted names.
    body = body_of(r.json()); body['display_name'] = '旧客户端自定义名'
    r = teacher.patch(f"/api/teacher/classes/{room['id']}", json=body)
    assert r.status_code == 200 and r.json()['display_name'] == '旧客户端自定义名'
    assert admin.get(f'/api/admin/broadcasts/{bid}/snapshot').json() == snapshot
    assert snapshot['classes'][0]['display_name'] == '周六一档'


def legacy_engine(tmp_path, version):
    path = tmp_path/'legacy.sqlite3'
    engine = create_engine('sqlite:///'+str(path))
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        db.exec_driver_sql('ALTER TABLE classes DROP COLUMN name_is_manual')
        db.exec_driver_sql('INSERT INTO schema_versions VALUES (?,?)', (version, now()))
        db.exec_driver_sql("INSERT INTO dictionaries(id,kind,name) VALUES (1,'campus','原校区'),(2,'subject','语文')")
        db.exec_driver_sql("INSERT INTO users(id,username,display_name,role,campus_id,enabled,session_version,created_at) VALUES(1,'legacy','原老师','teacher',1,1,0,?)", (now(),))
        db.exec_driver_sql("INSERT INTO classes(id,teacher_id,subject_id,campus_id,grade,display_name,capacity,version,created_at,updated_at) VALUES(1,1,2,1,'高一','周六一档',3,1,?,?)", (now(),now()))
        if version == 1:
            # Exercise the real v1 non-AUTOINCREMENT rebuild without the new column.
            db.exec_driver_sql('ALTER TABLE classes RENAME TO old_classes')
            ddl = db.exec_driver_sql("SELECT sql FROM sqlite_master WHERE name='old_classes'").scalar()
            db.exec_driver_sql(ddl.replace('"old_classes"', 'classes').replace('AUTOINCREMENT',''))
            db.exec_driver_sql('INSERT INTO classes SELECT * FROM old_classes')
            db.exec_driver_sql('DROP TABLE old_classes')
    return engine, path


def test_v3_upgrade_backs_up_preserves_names_and_is_idempotent(tmp_path):
    engine, path = legacy_engine(tmp_path, 3)
    migrate_class_names(engine, tmp_path)
    migrate_class_names(engine, tmp_path)
    with engine.connect() as db:
        assert db.exec_driver_sql('SELECT display_name,name_is_manual FROM classes').one() == ('周六一档', 1)
        assert db.exec_driver_sql('SELECT MAX(version) FROM schema_versions').scalar() == 4
    backups = list((tmp_path/'backups').glob('migration-v3-*.sqlite3'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert 'name_is_manual' not in {c[1] for c in db.execute('PRAGMA table_info(classes)')}
        assert db.execute('SELECT display_name FROM classes').fetchone()[0] == '周六一档'
    # Old v3 backups still pass restore validation before migration.
    target = tmp_path/'restored'
    env = dict(os.environ, EDUPULSE_DATA_DIR=str(target), PYTHONUTF8='1')
    result = subprocess.run([sys.executable,'-m','app.cli','restore',str(backups[0]),'--confirm'],env=env,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    engine.dispose()


def test_v1_upgrade_without_naming_column_still_preserves_class(tmp_path):
    from app.db import Student, ClassRoom
    engine, _ = legacy_engine(tmp_path, 1)
    migrate_stable_ids(engine, tmp_path, Student.__table__, ClassRoom.__table__)
    migrate_student_schedules(engine, tmp_path)
    migrate_class_names(engine, tmp_path)
    with engine.connect() as db:
        assert db.exec_driver_sql('SELECT display_name,name_is_manual FROM classes').one() == ('周六一档', 1)
        assert db.exec_driver_sql('SELECT MAX(version) FROM schema_versions').scalar() == 4
    engine.dispose()
