import pytest
from test_acceptance import reset,setup,student,classroom,body_of
from app.freeze_compare import metrics,compare
from app.db import SessionLocal,FrozenRecord,engine,init_db


def freeze(admin,title):
    r=admin.post('/api/admin/freezes',json={'title':title,'note':'仅测试冻结备注'})
    assert r.status_code==200,r.text
    return r.json()


def test_manual_freeze_is_immutable_and_comparison_explains_new_small_class():
    a,ts,campus,math,eng=setup();t=ts[0][1]
    s1=student(t,campus,'双科学员');s2=student(t,campus,'单科学员')
    classroom(t,math,6,[s1,s2]);classroom(t,eng,3,[s1])
    old=freeze(a,'旧B');old_data=a.get(f"/api/admin/freezes/{old['id']}").json()
    assert old['metrics']['subjects']['value']==1.5
    assert old['metrics']['six']['value']==pytest.approx(2/6)
    # Broadcasts are not required and freezing does not stop normal teacher writes.
    assert a.get('/api/admin/broadcasts').json()==[]
    s3=student(t,campus,'新增学员');c=classroom(t,math,6,[s3])
    new=freeze(a,'新A')
    result=a.get(f"/api/admin/freezes/compare?old_id={old['id']}&new_id={new['id']}").json()['metrics']
    assert result['six']['after']['value']==.25
    change=result['six']['events'][0]
    assert change['entity_id']==c['id'] and change['direction']=='down'
    assert '新增一对六班，1人' in change['title']
    assert result['subjects']['after']['value']==pytest.approx(4/3)
    assert result['subjects']['events'][0]['direction']=='down'
    assert '新增学员' in result['subjects']['events'][0]['title']
    assert result['three']['events']==[]
    assert a.get(f"/api/admin/freezes/{old['id']}").json()==old_data
    rows=a.get('/api/admin/freezes').json();assert [r['id'] for r in rows]==[new['id'],old['id']]
    assert 'data' not in rows[0] and rows[0]['created_by_name']=='测试主管'
    assert any(row['action']=='freeze.create' for row in a.get('/api/admin/audit').json())


def test_freeze_permissions_validation_and_no_edit_endpoints():
    a,ts,_,_,_=setup();t=ts[0][1]
    assert t.post('/api/admin/freezes',json={'title':'越权'}).status_code==403
    assert t.get('/api/admin/freezes').status_code==403
    assert t.get('/api/admin/freezes/compare?old_id=1&new_id=2').status_code==403
    assert a.post('/api/admin/freezes',json={'title':'   '}).status_code==422
    r=freeze(a,'空记录');assert all(m['value'] is None for m in r['metrics'].values())
    assert a.get(f"/api/admin/freezes/compare?old_id={r['id']}&new_id={r['id']}").status_code==422
    assert a.get('/api/admin/freezes/compare?old_id=999&new_id=1000').status_code==404
    assert a.get('/api/admin/freezes/999').status_code==404
    assert t.get(f"/api/admin/freezes/{r['id']}").status_code==403
    assert a.patch(f"/api/admin/freezes/{r['id']}",json={'title':'篡改'}).status_code in (404,405)
    assert a.delete(f"/api/admin/freezes/{r['id']}").status_code in (404,405)


def test_rename_and_evaluation_changes_do_not_generate_metric_factors():
    a,ts,campus,math,_=setup();t=ts[0][1]
    c=classroom(t,math,3,[student(t,campus)])
    old=freeze(a,'B');body=body_of(c);body['display_name']='改名';body['students'][0]['note']='新评价'
    assert t.patch(f"/api/teacher/classes/{c['id']}",json=body).status_code==200
    new=freeze(a,'A')
    data=a.get(f"/api/admin/freezes/compare?old_id={old['id']}&new_id={new['id']}").json()
    assert all(m['events']==[] for m in data['metrics'].values())
    assert a.get(f"/api/admin/freezes/{new['id']}").json()['data']['classes'][0]['students'][0]['note']=='新评价'


def test_student_merge_chain_is_explained_without_false_churn():
    a,ts,campus,math,eng=setup();t=ts[0][1]
    s1=student(t,campus,'重复1');s2=student(t,campus,'重复2');s3=student(t,campus,'保留')
    classroom(t,math,6,[s1]);classroom(t,eng,6,[s2]);classroom(t,math,3,[s3])
    old=freeze(a,'合并前')
    assert a.post('/api/admin/students/merge',json={'source_id':s1,'target_id':s2}).status_code==200
    assert a.post('/api/admin/students/merge',json={'source_id':s2,'target_id':s3}).status_code==200
    new=freeze(a,'合并后')
    result=a.get(f"/api/admin/freezes/compare?old_id={old['id']}&new_id={new['id']}").json()['metrics']
    events=result['subjects']['events'];assert len(events)==1
    assert events[0]['kind']=='merge' and events[0]['direction']=='up'
    assert events[0]['delta_numerator']==-1 and events[0]['delta_denominator']==-2
    assert '档案合并' in events[0]['title'] and '移除学生档案' not in events[0]['title']
    assert result['six']['events']==[] and result['three']['events']==[]


def test_capacity_change_deletion_and_all_factors_reconcile_exactly():
    a,ts,campus,math,eng=setup();t=ts[0][1]
    c1=classroom(t,math,3,[student(t,campus)]);c2=classroom(t,eng,6,[student(t,campus)])
    old=freeze(a,'B');before=a.get(f"/api/admin/freezes/{old['id']}").json()['data']
    body=body_of(c1);body['capacity']=6
    assert t.patch(f"/api/teacher/classes/{c1['id']}",json=body).status_code==200
    assert t.delete(f"/api/teacher/classes/{c2['id']}?confirmed=true&version={c2['version']}").status_code==200
    classroom(t,math,3,[student(t,campus)])
    new=freeze(a,'A');after=a.get(f"/api/admin/freezes/{new['id']}").json()['data']
    results=compare(before,after)
    for m in results.values():
        assert sum(e['delta_numerator'] for e in m['events'])==m['after']['numerator']-m['before']['numerator']
        assert sum(e['delta_denominator'] for e in m['events'])==m['after']['denominator']-m['before']['denominator']
    assert any('班型' in e['title'] for e in results['six']['events'])


def test_direction_is_relative_to_old_ratio_including_counteracting_changes():
    a,ts,campus,math,eng=setup();t=ts[0][1]
    s1=student(t,campus,'原双科');s2=student(t,campus,'原单科')
    classroom(t,math,6,[s1,s2]);classroom(t,eng,3,[s1]);old=freeze(a,'B')
    one=student(t,campus,'新增单科');two=student(t,campus,'新增双科')
    classroom(t,math,6,[one,two]);classroom(t,eng,3,[two]);new=freeze(a,'A')
    result=a.get(f"/api/admin/freezes/compare?old_id={old['id']}&new_id={new['id']}").json()['metrics']['subjects']
    assert result['before']['value']==result['after']['value']==1.5
    assert {e['direction'] for e in result['events']}=={'up','down'}


def test_empty_denominators_are_not_mislabelled_and_survive_reopen():
    a,ts,campus,math,_=setup();t=ts[0][1];old=freeze(a,'空B')
    classroom(t,math,6,[student(t,campus)]);new=freeze(a,'有A')
    result=a.get(f"/api/admin/freezes/compare?old_id={old['id']}&new_id={new['id']}").json()['metrics']
    assert result['six']['before']['value'] is None
    assert result['six']['events'][0]['direction']=='neutral'
    with SessionLocal() as db:
        assert db.get(FrozenRecord,new['id']).title=='有A'


def test_v4_additive_upgrade_keeps_existing_classes_and_broadcast_history():
    from test_acceptance import broadcast
    a,ts,campus,math,_=setup();t=ts[0][1]
    c=classroom(t,math,6,[student(t,campus)])
    bid=broadcast(a,campus);a.post(f'/api/admin/broadcasts/{bid}/close')
    historic=a.get(f'/api/admin/broadcasts/{bid}/snapshot').json()
    with engine.begin() as db:
        db.exec_driver_sql('DROP TABLE frozen_records')
        db.exec_driver_sql('DELETE FROM schema_versions WHERE version=5')
    init_db();init_db()
    with engine.connect() as db:assert db.exec_driver_sql('SELECT MAX(version) FROM schema_versions').scalar()==5
    assert a.get(f'/api/admin/broadcasts/{bid}/snapshot').json()==historic
    assert t.get('/api/teacher/classes').json()[0]['id']==c['id']
    assert freeze(a,'升级后首份记录')['class_count']==1
