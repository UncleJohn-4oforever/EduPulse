from test_acceptance import reset,setup,student,classroom,body_of,broadcast
from app.db import SessionLocal,Enrollment,Evaluation,StudentWeeklySlot,Student


def preview(admin,identity):
    r=admin.get(f'/api/admin/students/{identity}/deletion-preview')
    assert r.status_code==200,r.text
    return r.json()


def remove(admin,identity,token):
    return admin.delete(f'/api/admin/students/{identity}',params={'confirmed':True,'token':token})


def test_admin_deletion_removes_links_but_preserves_classes_and_all_history():
    a,ts,campus,math,eng=setup();t=ts[0][1];other=ts[1][1]
    sid=student(t,campus,'误录学生');keep=student(t,campus,'保留学生')
    c1=classroom(t,math,3,[sid,keep]);c2=classroom(other,eng,6,[sid])
    freeze=a.post('/api/admin/freezes',json={'title':'删除前'}).json();frozen=a.get(f"/api/admin/freezes/{freeze['id']}").json()
    bid=broadcast(a,campus);a.post(f'/api/admin/broadcasts/{bid}/close');historic=a.get(f'/api/admin/broadcasts/{bid}/snapshot').json()
    impact=preview(a,sid);assert {c['id'] for c in impact['classes']}=={c1['id'],c2['id']}
    assert remove(a,sid,impact['token']).status_code==200
    fresh1=t.get('/api/teacher/classes').json()[0];fresh2=other.get('/api/teacher/classes').json()[0]
    assert fresh1['id']==c1['id'] and fresh1['version']==c1['version']+1
    assert [s['student_id'] for s in fresh1['students']]==[keep]
    assert fresh2['id']==c2['id'] and fresh2['students']==[] and fresh2['version']==c2['version']+1
    assert a.get(f"/api/admin/freezes/{freeze['id']}").json()==frozen
    assert a.get(f'/api/admin/broadcasts/{bid}/snapshot').json()==historic
    assert sid not in [s['id'] for s in a.get('/api/admin/reports?search_type=student').json()['students']]
    with SessionLocal() as db:
        assert db.get(Student,sid) is None
        assert db.query(Enrollment).count()==1 and db.query(Evaluation).count()==1 and db.query(StudentWeeklySlot).count()==1
    assert student(t,campus,'新学生')>keep
    assert any(row['action']=='student.delete' for row in a.get('/api/admin/audit').json())


def test_student_deletion_requires_admin_confirmation_and_current_preview():
    a,ts,campus,math,_=setup();t=ts[0][1];sid=student(t,campus)
    c=classroom(t,math,3,[sid]);impact=preview(a,sid)
    assert t.get(f'/api/admin/students/{sid}/deletion-preview').status_code==403
    assert remove(t,sid,impact['token']).status_code==403
    assert a.delete(f'/api/admin/students/{sid}',params={'token':impact['token']}).status_code==422
    assert a.delete(f'/api/admin/students/{sid}?confirmed=true').status_code==422
    assert remove(a,sid,'0'*64).status_code==409
    body=body_of(c);body['students'][0]['note']='核对后发生修改'
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code==200
    assert remove(a,sid,impact['token']).status_code==409
    impact2=preview(a,sid);assert impact['token']!=impact2['token']
    assert remove(a,sid,impact2['token']).status_code==200
    assert remove(a,sid,impact2['token']).status_code==404
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code in (409,422)
    assert t.get('/api/teacher/classes').json()[0]['students']==[]


def test_unassigned_profile_deletion_updates_subject_ratio_and_comparison():
    a,ts,campus,math,_=setup();t=ts[0][1]
    assigned=student(t,campus);unassigned=student(t,campus,'不存在的学生')
    classroom(t,math,6,[assigned]);old=a.post('/api/admin/freezes',json={'title':'B'}).json()
    impact=preview(a,unassigned);assert impact['classes']==[]
    assert remove(a,unassigned,impact['token']).status_code==200
    new=a.post('/api/admin/freezes',json={'title':'A'}).json()
    result=a.get(f"/api/admin/freezes/compare?old_id={old['id']}&new_id={new['id']}").json()['metrics']['subjects']
    assert result['before']['value']==.5 and result['after']['value']==1
    assert result['events'][0]['entity_id']==unassigned and result['events'][0]['direction']=='up'


def test_campus_filter_retains_unassigned_profiles_without_loosening_other_filters():
    a,ts,campus,math,eng=setup();t=ts[0][1]
    assigned=student(t,campus);unassigned=student(t,campus,'未关联学生');classroom(t,math,6,[assigned])
    branch=a.post('/api/admin/dictionaries',json={'kind':'campus','name':'其他校区'}).json()['id']
    other=student(a,branch,'其他校区未关联学生')
    data=a.get(f'/api/admin/reports?campus_id={campus}').json()
    assert {s['id'] for s in data['students']}=={assigned,unassigned}
    assert sum(s['subject_count'] for s in data['students'])/len(data['students'])==.5
    assert [s['id'] for s in a.get(f'/api/admin/reports?campus_id={branch}').json()['students']]==[other]
    assert [s['id'] for s in a.get(f'/api/admin/reports?campus_id={campus}&subject_id={math}').json()['students']]==[assigned]
    assert a.get(f'/api/admin/reports?campus_id={campus}&subject_id={eng}').json()['students']==[]
    assert a.get(f"/api/admin/reports?campus_id={campus}&teacher_id={ts[0][0]['id']}").json()['students'][0]['id']==assigned
    assert len(a.get(f'/api/admin/reports?campus_id={campus}&q=未关联&search_type=student').json()['students'])==1
