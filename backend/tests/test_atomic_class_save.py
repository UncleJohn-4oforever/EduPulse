import pytest
from test_acceptance import reset,setup,classroom,student,body_of
from app.db import SessionLocal,Student,Audit


def test_empty_class_retains_master_slot_and_auto_name():
    admin,teachers,campus,subject,_=setup();teacher=teachers[0][1]
    slot={'weekday':5,'slot_number':1,'start_time':'08:00','end_time':'10:00'}
    body={'display_name':'自动','name_is_manual':False,'subject_id':subject,'capacity':3,'students':[],'class_slot':slot}
    response=teacher.post('/api/teacher/classes',json=body);assert response.status_code==200,response.text
    saved=response.json();assert saved['display_name']=='周五一档' and saved['class_slot']==slot
    fresh=teacher.get(f"/api/teacher/classes/{saved['id']}").json();assert fresh==saved
    body=body_of(saved);body['students']=[{'new_student':{'display_name':'事务新生','grade':'高一'},'weekly_slots':[slot]}]
    response=teacher.patch(f"/api/teacher/classes/{saved['id']}",json=body);assert response.status_code==200,response.text
    body=body_of(response.json());body['students']=[]
    response=teacher.patch(f"/api/teacher/classes/{saved['id']}",json=body);assert response.status_code==200,response.text
    assert response.json()['class_slot']==slot and len(response.json()['weekly_slots'])==1
    assert admin.get('/api/admin/reports/workload').json()[0]['weekly_lessons']==1


@pytest.mark.parametrize('admin_mode',[False,True])
def test_class_and_new_student_commit_or_rollback_together(admin_mode):
    admin,teachers,campus,subject,_=setup();owner,teacher,_=teachers[0]
    saved=classroom(teacher,subject,3,[student(teacher,campus)])
    endpoint=f"/api/{'admin' if admin_mode else 'teacher'}/classes/{saved['id']}";client=admin if admin_mode else teacher
    body=body_of(saved)
    if admin_mode:body['teacher_id']=owner['id']
    body['students'].append({'new_student':{'display_name':'原子新生','grade':'高一'},'weekly_slots':body['students'][0]['weekly_slots']})
    with SessionLocal() as db:before=db.query(Student).count();audits=db.query(Audit).count()
    stale={**body,'version':saved['version']+1}
    assert client.patch(endpoint,json=stale).status_code==409
    invalid={**body,'students':[body['students'][1],{'student_id':999999,'weekly_slots':body['students'][0]['weekly_slots']}]}
    assert client.patch(endpoint,json=invalid).status_code==422
    with SessionLocal() as db:assert db.query(Student).count()==before and db.query(Audit).count()==audits
    response=client.patch(endpoint,json=body);assert response.status_code==200,response.text
    assert len(response.json()['students'])==2
    with SessionLocal() as db:assert db.query(Student).count()==before+1


def test_release_allowlist_excludes_business_files(tmp_path):
    import importlib.util
    from pathlib import Path
    script=Path(__file__).resolve().parents[2]/'scripts'/'release_files.py'
    spec=importlib.util.spec_from_file_location('release_files',script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    included=['run.py','首次运行.bat','.env.example','frontend/dist/index.html','frontend/dist/assets/index.js','backend/app/main.py','backend/wheels-win-py312/example.whl','scripts/package.py','docs/licenses/react-LICENSE.txt']
    excluded=['学员名单核对结果.xlsx','student.csv','notes.json','.env','backend/app/private.xlsx','exports/report.xlsx','browser-test-data/db.sqlite3','frontend/node_modules/a.js','docs/screenshots/private.png']
    for name in included+excluded:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture',encoding='utf-8')
    assert {p.relative_to(tmp_path).as_posix() for p in module.release_files(tmp_path)}==set(included)
