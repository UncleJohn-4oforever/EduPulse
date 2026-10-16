"""Student-owned schedules, deleted teachers/dictionaries and schema3 upgrade."""
import json, sqlite3, subprocess, sys
from io import BytesIO
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from openpyxl import load_workbook
from test_acceptance import reset,setup,student,classroom,body_of,broadcast,client
from app.db import *
from app.migrations import migrate_student_schedules


def test_student_slots_are_independent_and_class_load_is_union():
    a,ts,campus,math,_=setup();t=ts[0][1]
    c=classroom(t,math,6,[student(t,campus) for _ in range(3)])
    body=body_of(c)
    for m in body['students']:m['weekly_slots']=[{'weekday':3,'slot_number':3}]
    body['students'][1]['weekly_slots'].append({'weekday':4,'slot_number':6,'start_time':'17:00','end_time':'18:00'})
    r=t.patch(f"/api/teacher/classes/{c['id']}",json=body);assert r.status_code==200,r.text
    updated=r.json();assert len(updated['weekly_slots'])==2
    assert [len(m['weekly_slots']) for m in updated['students']]==[1,2,1]
    assert updated['weekly_slots'][1]['start_time']=='17:00'
    assert a.get('/api/admin/reports/workload').json()[0]['weekly_lessons']==2
    fresh=t.get(f"/api/teacher/classes/{c['id']}").json();assert fresh==updated
    body=body_of(fresh);body['students'].pop(1)
    r=t.patch(f"/api/teacher/classes/{c['id']}",json=body);assert r.status_code==200
    assert a.get('/api/admin/reports/workload').json()[0]['weekly_lessons']==1
    body=body_of(r.json());body['students']=[]
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code==200
    assert a.get('/api/admin/reports/workload').json()[0]['weekly_lessons']==0


def test_shared_student_has_separate_subject_schedules_and_no_teacher_leak():
    a,ts,campus,math,english=setup();t=ts[0][1];other=ts[1][1];sid=student(t,campus)
    m=classroom(t,math,3,[sid]);e=classroom(other,english,3,[sid])
    body=body_of(e);body['students'][0]['weekly_slots']=[{'weekday':6,'slot_number':6}]
    assert other.patch(f"/api/teacher/classes/{e['id']}",json=body).status_code==200
    assert t.get(f"/api/teacher/classes/{m['id']}").json()['students'][0]['weekly_slots'][0]['slot_number']==3
    assert t.get(f"/api/teacher/classes/{e['id']}").status_code==404
    result=t.get('/api/students/search',params={'q':str(sid)}).json()[0]
    assert set(result)=={'id','display_name','grade'}
    s=a.get('/api/admin/reports/students').json()[0];assert s['subject_count']==2
    assert s['details'][1]['weekly_slots'][0]['weekday']==6
    workbook=load_workbook(BytesIO(a.get('/api/admin/reports/export.xlsx').content))
    sheet=workbook['学生科目教师评价明细'];assert sheet['L1'].value=='该生上课档位';assert '第6档' in sheet['L3'].value


@pytest.mark.parametrize('slots',[[{'weekday':3,'slot_number':7}],[{'weekday':8,'slot_number':1}],[{'weekday':3,'slot_number':1},{'weekday':3,'slot_number':1}],[],[{'weekday':3,'slot_number':1,'start_time':'09:00'}]])
def test_server_rejects_invalid_student_slots(slots):
    _,ts,campus,math,_=setup();t=ts[0][1];c=classroom(t,math,3,[student(t,campus)])
    body=body_of(c);body['students'][0]['weekly_slots']=slots
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code==422


def test_same_group_slot_cannot_have_conflicting_explicit_times():
    _,ts,campus,math,_=setup();t=ts[0][1];c=classroom(t,math,3,[student(t,campus),student(t,campus)])
    body=body_of(c)
    body['students'][0]['weekly_slots']=[{'weekday':3,'slot_number':2,'start_time':'09:00','end_time':'10:00'}]
    body['students'][1]['weekly_slots']=[{'weekday':3,'slot_number':2,'start_time':'10:00','end_time':'11:00'}]
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code==422
    body['students'][1]['weekly_slots']=[{'weekday':3,'slot_number':2}]
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code==200


def test_delete_teacher_revokes_sessions_preserves_students_and_history():
    a,ts,campus,math,_=setup();u,t,p=ts[0]
    classroom(t,math,3,[student(t,campus)]);b=broadcast(a,campus)
    a.post(f'/api/admin/broadcasts/{b}/close');before=a.get(f'/api/admin/broadcasts/{b}/snapshot').json()
    assert t.delete(f"/api/admin/teachers/{u['id']}?confirmed=true").status_code==403
    assert a.delete(f"/api/admin/teachers/{u['id']}").status_code==422
    r=a.delete(f"/api/admin/teachers/{u['id']}?confirmed=true");assert r.status_code==200 and r.json()['deleted_classes']==1
    assert t.get('/api/teacher/classes').status_code==401
    assert a.patch(f"/api/admin/teachers/{u['id']}",json={'display_name':'恢复','campus_id':campus,'enabled':True}).status_code==404
    assert all(row['id']!=u['id'] for row in a.get('/api/admin/teachers').json())
    assert a.get(f'/api/admin/broadcasts/{b}/snapshot').json()==before
    current=a.get('/api/admin/reports').json();assert len(current['students'])==1 and current['students'][0]['subject_count']==0
    assert current['classes']==[] and len(current['teachers'])==1
    with SessionLocal() as db:
        assert db.get(User,u['id']).deleted_at and db.get(User,u['id']).password_hash is None
        assert db.query(StudentWeeklySlot).count()==0
        assert db.query(Audit).filter_by(action='teacher.delete').count()==1


def test_dictionary_delete_hides_choices_preserves_existing_and_can_restore():
    a,ts,campus,math,_=setup();t=ts[0][1];c=classroom(t,math,3,[student(t,campus)])
    dictionaries=a.get('/api/dictionaries').json();grade=next(g for g in dictionaries['grade'] if g['name']=='高一')
    for id in (math,grade['id']):
        assert t.delete(f'/api/admin/dictionaries/{id}?confirmed=true').status_code==403
        assert a.delete(f'/api/admin/dictionaries/{id}').status_code==422
        assert a.delete(f'/api/admin/dictionaries/{id}?confirmed=true').status_code==200
    d=t.get('/api/dictionaries').json();assert not any(s['id']==math for s in d['subject']);assert d['archived']['subject'][0]['name']=='数学'
    body=body_of(c);body['display_name']='保持原类别的旧班级'
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code==200
    body.pop('version');assert t.post('/api/teacher/classes',json=body).status_code==422
    assert t.post('/api/students',json={'display_name':'新生','grade':'高一','campus_id':campus}).status_code==422
    r=a.post('/api/admin/dictionaries',json={'kind':'subject','name':'数学'});assert r.status_code==200 and r.json()['id']==math
    assert a.post('/api/admin/dictionaries',json={'kind':'grade','name':'高一'}).status_code==200


def test_teacher_deleted_after_broadcast_does_not_change_denominator():
    a,ts,campus,_,_=setup();b=broadcast(a,campus);u=ts[0][0]
    assert a.delete(f"/api/admin/teachers/{u['id']}?confirmed=true").status_code==200
    progress=a.get(f'/api/admin/broadcasts/{b}/progress').json()
    assert len(progress['targets'])==2 and next(t for t in progress['targets'] if t['teacher_id']==u['id'])['deleted']


def test_v2_upgrade_copies_class_slots_per_student_and_keeps_snapshot(tmp_path):
    # Build a real v2 fixture from current schema, removing only the v3 additions.
    path=tmp_path/'legacy-v2.sqlite3';stamp=now();legacy=create_engine('sqlite:///'+str(path))
    from sqlalchemy.schema import CreateTable
    with sqlite3.connect(path) as db:
        for table in Base.metadata.sorted_tables:
            if table.name=='student_weekly_slots':continue
            ddl=str(CreateTable(table).compile(dialect=legacy.dialect))
            ddl=ddl.replace('\n\tdeleted_at VARCHAR,','').replace(', \n\tdeleted_at VARCHAR','')
            db.execute(ddl)
        db.execute('INSERT INTO schema_versions VALUES(2,?)',(stamp,))
        db.execute("INSERT INTO dictionaries(id,kind,name) VALUES(1,'campus','主校区'),(2,'subject','数学')")
        db.execute("INSERT INTO users(id,username,display_name,role,campus_id,enabled,session_version,created_at) VALUES(1,'old','旧教师','teacher',1,1,0,?)",(stamp,))
        for id in (1,2):db.execute("INSERT INTO students(id,display_name,grade,campus_id,created_at,updated_at) VALUES(?,?,'高一',1,?,?)",(id,'虚构'+str(id),stamp,stamp))
        db.execute("INSERT INTO classes(id,teacher_id,subject_id,campus_id,grade,display_name,capacity,version,created_at,updated_at) VALUES(1,1,2,1,'高一','旧班',3,1,?,?)",(stamp,stamp))
        for id in (1,2):
            db.execute('INSERT INTO enrollments(id,class_id,student_id,created_at) VALUES(?,1,?,?)',(id,id,stamp))
            db.execute("INSERT INTO student_evaluations(id,enrollment_id,level,note,updated_by,updated_at) VALUES(?,?,'A','旧评价',1,?)",(id,id,stamp))
        db.execute("INSERT INTO weekly_slots(id,class_id,weekday,slot_label,start_time,end_time) VALUES(1,1,3,'三档','09:00','10:00'),(2,1,4,'特殊旧名称',NULL,NULL)")
        db.execute("INSERT INTO broadcasts(id,title,starts_at,deadline_at,created_by,created_at) VALUES(1,'旧轮',?,?,1,?)",(stamp,stamp,stamp))
        raw=json.dumps({'students':[],'classes':[],'teachers':[],'historic':True})
        db.execute('INSERT INTO broadcast_snapshots(id,broadcast_id,captured_at,data) VALUES(1,1,?,?)',(stamp,raw))
    migrate_student_schedules(legacy,tmp_path)
    with Session(legacy) as db:
        for id in (1,2):
            e=db.get(Enrollment,id);assert len(e.slots)==2
            assert e.slots[0].slot_number==3 and e.slots[0].start_time=='09:00'
            assert e.slots[1].slot_number is None and e.slots[1].slot_label=='特殊旧名称'
        assert db.get(Snapshot,1).data==raw and db.get(User,1).deleted_at is None
    migrate_student_schedules(legacy,tmp_path)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM student_weekly_slots').fetchone()[0]==4
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0]==3
    assert len(list((tmp_path/'backups').glob('migration-v2-*.sqlite3')))==1
    legacy.dispose()
    backup=next((tmp_path/'backups').glob('migration-v2-*.sqlite3'))
    # Old v2 backups must remain restorable by the new CLI before startup upgrade.
    subprocess.run([sys.executable,'-m','app.cli','restore',str(backup),'--confirm'],check=True,capture_output=True,timeout=10)
    subprocess.run([sys.executable,'-m','app.cli','init-db'],check=True,capture_output=True,timeout=10)
    with SessionLocal() as db:
        assert db.get(SchemaVersion,3)
        assert db.query(StudentWeeklySlot).count()==4
        assert db.get(Snapshot,1).data==raw


def test_teacher_deletion_keeps_other_teachers_shared_student_relationships():
    a,ts,campus,math,english=setup();u,t,_=ts[0];other=ts[1][1]
    sid=student(t,campus);classroom(t,math,3,[sid]);e=classroom(other,english,3,[sid])
    assert a.delete(f"/api/admin/teachers/{u['id']}?confirmed=true").status_code==200
    fresh=other.get(f"/api/teacher/classes/{e['id']}").json()
    assert fresh['students'][0]['student_id']==sid and fresh['students'][0]['level']=='A'
    assert len(fresh['students'][0]['weekly_slots'])==1
    assert a.get('/api/admin/reports/students').json()[0]['subject_count']==1
