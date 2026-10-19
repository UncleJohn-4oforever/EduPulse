from test_acceptance import reset,setup,student,body_of


def test_teacher_shared_class_slot_is_the_single_source_for_every_student():
    admin,teachers,campus,subject,_=setup()
    teacher=teachers[0][1]
    first=student(teacher,campus,'甲');second=student(teacher,campus,'乙')
    shared={'weekday':5,'slot_number':1,'start_time':'08:00','end_time':'10:00'}
    body={'display_name':'自动班名','name_is_manual':False,'subject_id':subject,'capacity':6,'class_slot':shared,
          'students':[{'student_id':first,'level':'A','note':'保留评价'},
                      {'student_id':second,'level':'B','note':'','weekly_slots':[{'weekday':7,'slot_number':3}]}]}
    response=teacher.post('/api/teacher/classes',json=body)
    assert response.status_code==200,response.text
    saved=response.json()
    assert saved['display_name']=='周五一档'
    assert all([(s['weekday'],s['slot_number'],s['start_time'],s['end_time']) for s in m['weekly_slots']]==[(5,1,'08:00','10:00')] for m in saved['students'])
    third=student(teacher,campus,'丙')
    body=body_of(saved)|{'name_is_manual':False,'class_slot':{**shared,'weekday':6,'slot_number':2,'start_time':'10:00','end_time':'12:00'}}
    body['students'].append({'student_id':third,'level':'C','note':'新学生不必再填档位'})
    response=teacher.patch(f"/api/teacher/classes/{saved['id']}",json=body)
    assert response.status_code==200,response.text
    updated=response.json()
    assert updated['display_name']=='周六二档'
    assert len(updated['weekly_slots'])==1
    assert all(len(m['weekly_slots'])==1 and m['weekly_slots'][0]['weekday']==6 and m['weekly_slots'][0]['slot_number']==2 for m in updated['students'])
    assert updated['students'][0]['note']=='保留评价'
    assert len(admin.get('/api/admin/reports').json()['classes'][0]['weekly_slots'])==1
    assert teacher.patch(f"/api/teacher/classes/{saved['id']}",json=body).status_code==409
    invalid=body_of(updated)|{'class_slot':{**shared,'end_time':'07:00'}}
    assert teacher.patch(f"/api/teacher/classes/{saved['id']}",json=invalid).status_code==422
    assert teacher.get(f"/api/teacher/classes/{saved['id']}").json()==updated


def test_supervisor_shared_slot_covers_current_and_new_members():
    admin,teachers,campus,subject,_=setup()
    owner,teacher,_=teachers[0]
    first=student(teacher,campus)
    body={'teacher_id':owner['id'],'display_name':'主管统一排课','subject_id':subject,'capacity':3,
          'class_slot':{'weekday':5,'slot_number':1,'start_time':None,'end_time':None},'students':[{'student_id':first}]}
    response=admin.post('/api/admin/classes',json=body)
    assert response.status_code==200,response.text
    saved=response.json()
    assert saved['students'][0]['weekly_slots'][0]['slot_number']==1
    assert saved['students'][0]['weekly_slots'][0]['start_time'] is None
    assert teacher.get(f"/api/teacher/classes/{saved['id']}").json()==saved
