"""Disabled teachers leave live schedules, while retained data can be restored."""
from io import BytesIO

from openpyxl import load_workbook

from test_acceptance import reset, setup, student, classroom, body_of
from app.db import SessionLocal, ClassRoom, Student


def set_enabled(admin, user, campus, enabled):
    response = admin.patch(f"/api/admin/teachers/{user['id']}", json={
        'display_name': '停用测试教师', 'campus_id': campus, 'enabled': enabled})
    assert response.status_code == 200, response.text


def test_disable_removes_live_courses_metrics_conflicts_and_exports_but_preserves_history():
    admin, teachers, campus, math, english = setup()
    owner, teacher, _ = teachers[0]
    other, active_teacher, _ = teachers[1]
    shared = student(teacher, campus)
    three = classroom(teacher, math, 3, [shared])
    six = classroom(teacher, math, 6, [shared])
    active = classroom(active_teacher, english, 6, [shared])
    set_enabled(admin, owner, campus, True)
    before = admin.get('/api/admin/reports').json()
    assert admin.get('/api/admin/schedule-warnings').json()
    frozen = admin.post('/api/admin/freezes', json={'title': '停用前'}).json()
    historical = admin.get(f"/api/admin/freezes/{frozen['id']}").json()

    set_enabled(admin, owner, campus, False)
    current = admin.get('/api/admin/reports').json()
    assert [t['id'] for t in current['teachers']] == [other['id']]
    assert [c['id'] for c in current['classes']] == [active['id']]
    assert current['teachers'][0]['small_rate'] == 1 / 6
    assert current['students'][0]['subject_count'] == 1
    assert current['students'][0]['subjects'] == ['英语']
    assert all(d['teacher_id'] == other['id'] for d in current['students'][0]['details'])
    assert admin.get('/api/admin/schedule-warnings').json() == []
    assert active_teacher.get('/api/teacher/schedule-warnings').json() == []
    assert teacher.get('/api/teacher/classes').status_code == 401
    assert next(t for t in admin.get('/api/admin/teachers').json() if t['id'] == owner['id'])['class_count'] == 2
    assert admin.get(f"/api/admin/classes/{three['id']}").status_code == 404
    body = body_of(three) | {'teacher_id': owner['id']}
    assert admin.patch(f"/api/admin/classes/{three['id']}", json=body).status_code == 404
    assert admin.post('/api/admin/classes', json=body).status_code == 422
    workbook = load_workbook(BytesIO(admin.get('/api/admin/reports/export.xlsx').content))
    assert all('停用测试教师' not in row for row in workbook['教师满班率'].iter_rows(values_only=True))
    after_freeze = admin.post('/api/admin/freezes', json={'title': '停用后'}).json()
    assert after_freeze['metrics']['three']['value'] is None
    assert after_freeze['metrics']['six']['value'] == 1 / 6
    assert admin.get(f"/api/admin/freezes/{frozen['id']}").json() == historical
    assert admin.get(f"/api/admin/freezes/compare?old_id={frozen['id']}&new_id={after_freeze['id']}").status_code == 200
    with SessionLocal() as db:
        assert db.get(ClassRoom, three['id']) is not None
        assert db.get(ClassRoom, six['id']) is not None
        assert db.get(Student, shared) is not None

    set_enabled(admin, owner, campus, True)
    restored = admin.get('/api/admin/reports').json()
    assert restored['classes'] == before['classes']
    assert restored['students'] == before['students']
    assert admin.get('/api/admin/schedule-warnings').json()


def test_delete_disabled_teacher_removes_retained_classes_but_not_students_or_freezes():
    admin, teachers, campus, math, _ = setup()
    owner, teacher, _ = teachers[0]
    shared = student(teacher, campus)
    room = classroom(teacher, math, 3, [shared])
    freeze = admin.post('/api/admin/freezes', json={'title': '删除前'}).json()
    historical = admin.get(f"/api/admin/freezes/{freeze['id']}").json()
    set_enabled(admin, owner, campus, False)
    deleted = admin.delete(f"/api/admin/teachers/{owner['id']}?confirmed=true")
    assert deleted.status_code == 200
    assert deleted.json()['deleted_classes'] == 1
    assert not admin.get('/api/admin/reports').json()['classes']
    assert admin.get('/api/admin/schedule-warnings').json() == []
    assert admin.get(f"/api/admin/freezes/{freeze['id']}").json() == historical
    with SessionLocal() as db:
        assert db.get(ClassRoom, room['id']) is None
        assert db.get(Student, shared) is not None
