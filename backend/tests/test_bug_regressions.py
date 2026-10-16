"""Regression cases found by independent source/runtime review."""
import sqlite3, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import event
from fastapi.testclient import TestClient
from test_acceptance import reset, setup, student, classroom, body_of
from app.db import SessionLocal, engine, User, ClassRoom, WeeklySlot
from app.security import ph
from app.reports import report
from app.main import app


def test_deleted_class_id_cannot_retarget_stale_editor():
    _,ts,campus,math,_=setup();t=ts[0][1]
    old=classroom(t,math,3,[])
    assert t.delete(f"/api/teacher/classes/{old['id']}?confirmed=true&version={old['version']}").status_code==200
    new=classroom(t,math,3,[])
    assert new['id']!=old['id']
    assert t.patch(f"/api/teacher/classes/{old['id']}",json=body_of(old)).status_code==404


def test_merged_student_id_never_belongs_to_new_person():
    a,ts,campus,_,_=setup();t=ts[0][1]
    keep=student(t,campus,'保留档案');removed=student(t,campus,'重复档案')
    assert a.post('/api/admin/students/merge',json={'source_id':removed,'target_id':keep}).status_code==200
    assert student(t,campus,'不同学生')>removed


def test_password_whitespace_is_not_silently_modified():
    password=' TestOnlyPassword2026 '
    with SessionLocal.begin() as db: db.query(User).filter_by(username='test-admin').one().password_hash=ph.hash(password)
    c=TestClient(app)
    assert c.post('/api/auth/login',json={'username':' test-admin ','password':password}).status_code==200
    assert c.post('/api/auth/login',json={'username':'test-admin','password':password.strip()}).status_code==401


def test_unusual_or_large_numeric_queries_are_validated():
    _,ts,_,_,_=setup();t=ts[0][1]
    for q in ('²','9'*30,'１２'):
        response=t.get('/api/students/search',params={'q':q})
        assert response.status_code==200 and response.json()==[]
    assert t.get('/api/students/search',params={'q':'9'*1000}).status_code==422
    assert t.get('/api/teacher/classes/'+str(10**100)).status_code==422


def test_report_cannot_mix_two_database_revisions():
    _,ts,campus,math,_=setup();t=ts[0][1];classroom(t,math,3,[])
    triggered=False
    def hook(conn,cursor,statement,parameters,context,executemany):
        nonlocal triggered
        if triggered or not statement.lstrip().startswith('SELECT') or 'FROM classes' not in statement:return
        triggered=True
        def concurrent_write():
            with SessionLocal.begin() as db:
                u=User(username='concurrent-teacher',display_name='并发教师',role='teacher',campus_id=campus)
                db.add(u);db.flush()
                db.add(ClassRoom(teacher_id=u.id,subject_id=math,campus_id=campus,grade='高一',display_name='并发新班',capacity=3,slots=[WeeklySlot(weekday=1,slot_label='一档')]))
        with ThreadPoolExecutor(max_workers=1) as executor: executor.submit(concurrent_write).result(timeout=5)
    event.listen(engine,'before_cursor_execute',hook)
    try:
        with SessionLocal() as db: data=report(db)
    finally:event.remove(engine,'before_cursor_execute',hook)
    assert triggered
    assert len(data['classes'])==sum(t['class_count'] for t in data['teachers'])
    assert {c['teacher_id'] for c in data['classes']} <= {t['id'] for t in data['teachers']}


def test_restore_rejects_incomplete_database_before_overwrite(tmp_path):
    a,_,_,_,_=setup();invalid=tmp_path/'incomplete.sqlite3'
    with sqlite3.connect(invalid) as db: db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)')
    result=subprocess.run([sys.executable,'-m','app.cli','restore',str(invalid),'--confirm'],capture_output=True,timeout=10)
    assert result.returncode!=0
    assert a.get('/api/admin/teachers').status_code==200


def test_restore_revokes_sessions_from_backup(tmp_path):
    a,_,_,_,_=setup();output=tmp_path/'backup.sqlite3'
    subprocess.run([sys.executable,'-m','app.cli','backup','--output',str(output)],check=True,capture_output=True)
    subprocess.run([sys.executable,'-m','app.cli','restore',str(output),'--confirm'],check=True,capture_output=True,timeout=10)
    assert a.get('/api/auth/me').status_code==401


def test_restore_to_same_file_is_rejected_without_hanging(tmp_path):
    import os
    from app.db import DATA
    original=DATA/'edupulse.sqlite3'
    hardlink=tmp_path/'linked.sqlite3';os.link(original,hardlink)
    for source in (original,hardlink):
        result=subprocess.run([sys.executable,'-m','app.cli','restore',str(source),'--confirm'],capture_output=True,timeout=5)
        assert result.returncode!=0 and '自身' in result.stderr.decode()


def test_parallel_failed_logins_cannot_bypass_ip_limit():
    from threading import Barrier
    from app.main import failures
    failures.clear();barrier=Barrier(16)
    def attempt(_):
        c=TestClient(app);barrier.wait()
        return c.post('/api/auth/login',json={'username':'absent','password':'incorrect'}).status_code
    with ThreadPoolExecutor(max_workers=16) as executor: responses=list(executor.map(attempt,range(16)))
    assert responses.count(401)==10 and responses.count(429)==6


def test_v1_migration_preserves_relations_and_historical_id_highwater(tmp_path):
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.orm import Session
    from app.db import Base, Student, Enrollment, Evaluation, now
    from app.migrations import migrate_stable_ids
    path=tmp_path/'legacy.sqlite3';legacy=create_engine('sqlite:///'+str(path));stamp=now()
    with sqlite3.connect(path) as db:
        for table in Base.metadata.sorted_tables:
            db.execute(str(CreateTable(table).compile(dialect=legacy.dialect)).replace(' AUTOINCREMENT',''))
        db.execute('INSERT INTO schema_versions VALUES(?,?)',(1,stamp))
        db.execute('INSERT INTO dictionaries(id,kind,name) VALUES(?,?,?)',(1,'campus','迁移校区'))
        db.execute('INSERT INTO dictionaries(id,kind,name) VALUES(?,?,?)',(2,'subject','数学'))
        db.execute('INSERT INTO users(id,username,display_name,role,campus_id,enabled,session_version,created_at) VALUES(1,?,?,?,?,1,0,?)',('legacy','迁移教师','teacher',1,stamp))
        db.execute('INSERT INTO students(id,display_name,grade,campus_id,created_at,updated_at) VALUES(8,?,?,?,?,?)',('保留学生','高一',1,stamp,stamp))
        db.execute('INSERT INTO classes(id,teacher_id,subject_id,campus_id,grade,display_name,capacity,version,created_at,updated_at) VALUES(4,1,2,1,?,?,3,1,?,?)',('高一','保留班级',stamp,stamp))
        db.execute('INSERT INTO weekly_slots(id,class_id,weekday,slot_label) VALUES(7,4,3,?)',('三档',))
        db.execute('INSERT INTO enrollments(id,class_id,student_id,created_at) VALUES(9,4,8,?)',(stamp,))
        db.execute('INSERT INTO student_evaluations(id,enrollment_id,level,note,updated_by,updated_at) VALUES(10,9,?,?,1,?)',('A','保留评价',stamp))
        db.execute('INSERT INTO broadcasts(id,title,starts_at,deadline_at,created_by,created_at) VALUES(1,?,?,?,?,?)',('旧广播',stamp,stamp,1,stamp))
        raw=json.dumps({'students':[{'id':20}],'classes':[{'id':25}]})
        db.execute('INSERT INTO broadcast_snapshots(id,broadcast_id,captured_at,data) VALUES(1,1,?,?)',(stamp,raw))
        db.execute('CREATE INDEX student_name_lookup ON students(display_name)')
    migrate_stable_ids(legacy,tmp_path,Student.__table__,ClassRoom.__table__)
    with Session(legacy) as db:
        assert db.get(Student,8).display_name=='保留学生'
        assert db.get(Enrollment,9).student_id==8
        assert db.get(Evaluation,10).note=='保留评价'
        s=Student(display_name='新学生',grade='高一',campus_id=1);c=ClassRoom(teacher_id=1,subject_id=2,campus_id=1,grade='高一',display_name='新班级',capacity=3)
        db.add_all([s,c]);db.commit();assert s.id>20 and c.id>25
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('SELECT data FROM broadcast_snapshots').fetchone()[0]==raw
        assert db.execute("SELECT name FROM sqlite_master WHERE name='student_name_lookup'").fetchone()
        assert db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0]==2
    assert len(list((tmp_path/'backups').glob('migration-v1-*.sqlite3')))==1
    migrate_stable_ids(legacy,tmp_path,Student.__table__,ClassRoom.__table__)
    assert len(list((tmp_path/'backups').glob('migration-v1-*.sqlite3')))==1
    legacy.dispose()


def test_teacher_name_edit_does_not_create_false_class_conflicts():
    a,ts,campus,math,_=setup();u,t,_=ts[0]
    c=classroom(t,math,3,[])
    assert a.patch(f"/api/admin/teachers/{u['id']}",json={'display_name':'更正姓名','campus_id':campus,'enabled':True}).status_code==200
    assert t.get(f"/api/teacher/classes/{c['id']}").json()['version']==c['version']
    campus2=a.post('/api/admin/dictionaries',json={'kind':'campus','name':'另一校区'}).json()['id']
    assert a.patch(f"/api/admin/teachers/{u['id']}",json={'display_name':'更正姓名','campus_id':campus2,'enabled':True}).status_code==200
    fresh=t.get(f"/api/teacher/classes/{c['id']}").json()
    assert fresh['version']==c['version']+1 and fresh['campus_id']==campus2
