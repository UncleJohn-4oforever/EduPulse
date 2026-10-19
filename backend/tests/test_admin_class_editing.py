import json
from test_acceptance import reset,setup,student,classroom,body_of,broadcast
from app.db import SessionLocal,Audit,User,Snapshot


def test_admin_class_writes_sync_with_teacher_and_preserve_history():
    admin,teachers,campus,subject,_=setup()
    owner,teacher,_=teachers[0]
    sid=student(teacher,campus)
    existing=classroom(teacher,subject,3,[sid])
    bid=broadcast(admin,campus);admin.post(f'/api/admin/broadcasts/{bid}/close')
    with SessionLocal() as db:
        raw=db.query(Snapshot).filter_by(broadcast_id=bid).one().data
    loaded=admin.get(f"/api/admin/classes/{existing['id']}").json()
    assert loaded['teacher']['id']==owner['id']
    body=body_of(loaded)|{'teacher_id':owner['id'],'display_name':'主管修改','name_is_manual':True}
    body['students'][0]['weekly_slots']=[{'weekday':6,'slot_number':2,'start_time':'10:00','end_time':'12:00'}]
    changed=admin.patch(f"/api/admin/classes/{existing['id']}",json=body)
    assert changed.status_code==200,changed.text
    current=teacher.get(f"/api/teacher/classes/{existing['id']}").json()
    assert current['display_name']=='主管修改' and current['students'][0]['weekly_slots'][0]['weekday']==6
    assert current['version']==existing['version']+1
    assert admin.patch(f"/api/admin/classes/{existing['id']}",json=body).status_code==409
    assert teacher.patch(f"/api/teacher/classes/{existing['id']}",json=body_of(existing)).status_code==409
    assert admin.delete(f"/api/admin/classes/{existing['id']}?confirmed=true&version={existing['version']}").status_code==409
    assert admin.delete(f"/api/admin/classes/{existing['id']}?version={current['version']}").status_code==422
    assert admin.delete(f"/api/admin/classes/{existing['id']}?confirmed=true&version={current['version']}").status_code==200
    assert teacher.get(f"/api/teacher/classes/{existing['id']}").status_code==404
    created=admin.post('/api/admin/classes',json={**body,'version':None})
    assert created.status_code==200,created.text
    assert created.json()['teacher_id']==owner['id'] and created.json()['campus_id']==campus
    assert len(teacher.get('/api/teacher/classes').json())==1
    assert admin.get('/api/admin/reports').json()['classes'][0]['display_name']=='主管修改'
    with SessionLocal() as db:
        assert db.query(Snapshot).filter_by(broadcast_id=bid).one().data==raw
        assert json.loads(raw)['classes'][0]['display_name']==existing['display_name']
        actor=db.query(User).filter_by(role='admin').one()
        assert db.query(Audit).filter_by(actor_id=actor.id,action='class.update').count()==1
        assert db.query(Audit).filter_by(actor_id=actor.id,action='class.delete').count()==1


def test_admin_class_permissions_validation_and_deleted_teachers():
    admin,teachers,campus,subject,_=setup()
    owner,teacher,_=teachers[0];other,outsider,_=teachers[1]
    c=classroom(teacher,subject,3,[student(teacher,campus)])
    body=body_of(c)|{'teacher_id':owner['id']}
    for client in (teacher,outsider):
        assert client.get(f"/api/admin/classes/{c['id']}").status_code==403
        assert client.post('/api/admin/classes',json=body).status_code==403
        assert client.patch(f"/api/admin/classes/{c['id']}",json=body).status_code==403
        assert client.delete(f"/api/admin/classes/{c['id']}?confirmed=true&version=1").status_code==403
    assert admin.patch(f"/api/admin/classes/{c['id']}",json=body|{'teacher_id':other['id']}).status_code==422
    invalid=body|{'students':[body['students'][0],body['students'][0]]}
    assert admin.post('/api/admin/classes',json=invalid).status_code==422
    invalid=body|{'students':[body['students'][0]|{'student_id':999999}]}
    assert admin.post('/api/admin/classes',json=invalid).status_code==422
    assert admin.get('/api/admin/classes/999999').status_code==404
    assert admin.post('/api/admin/classes',json=body|{'teacher_id':999999}).status_code==422
    from app.db import now
    with SessionLocal.begin() as db: db.get(User,owner['id']).deleted_at=now()
    assert admin.get(f"/api/admin/classes/{c['id']}").status_code==404
    assert admin.patch(f"/api/admin/classes/{c['id']}",json=body).status_code==404
    assert admin.post('/api/admin/classes',json=body).status_code==422
