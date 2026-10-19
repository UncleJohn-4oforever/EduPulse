"""Student conflicts across teachers are advisory and scoped to participants."""
import json
import pytest
from test_acceptance import reset, setup, student, classroom, body_of
from test_report_schedule_review import schedule


@pytest.mark.parametrize('day,number,start,end,kind', [
    (6, 1, '09:00', '11:00', 'time_overlap'),
    (6, 4, '09:00', '11:00', 'time_overlap'),
    (6, 1, None, None, 'possible_overlap'),
    (6, 1, '10:00', '12:00', None),
    (7, 1, '08:00', '10:00', None),
    (6, 2, None, None, None),
])
def test_shared_student_conflicts_across_teachers(day, number, start, end, kind):
    admin, teachers, campus, subject, english = setup(3)
    t1, t2, outsider = [t[1] for t in teachers]
    sid = student(t1, campus, '共享学生')
    # Same names are distinct identities and must not create extra warnings.
    other_sid = student(t2, campus, '共享学生')
    a = schedule(t1, classroom(t1, subject, 3, [sid]), 6, 1, '08:00', '10:00')
    b = schedule(t2, classroom(t2, english, 3, [sid, other_sid]), day, number, start, end)
    before = admin.get('/api/admin/reports').json()
    warnings = admin.get('/api/admin/schedule-warnings').json()
    assert len(warnings) == (1 if kind else 0)
    assert t1.get('/api/teacher/schedule-warnings').json() == warnings
    assert t2.get('/api/teacher/schedule-warnings').json() == warnings
    assert outsider.get('/api/teacher/schedule-warnings').json() == []
    if kind:
        w = warnings[0]
        assert w['scope'] == 'student' and w['kind'] == kind
        assert w['student_id'] == sid
        assert w['teacher_ids'] == [teachers[0][0]['id'], teachers[1][0]['id']]
        assert {c['id'] for c in w['classes']} == {a['id'], b['id']}
        assert '仅测试评价' not in json.dumps(w)
        assert 'students' not in w and 'note' not in json.dumps(w)
    after = admin.get('/api/admin/reports').json()
    assert before['teachers'] == after['teachers']
    assert before['students'] == after['students']
    schedule(t2, b, 7, number, start, end)
    assert admin.get('/api/admin/schedule-warnings').json() == []


def test_legacy_student_conflict_uses_enrollment_slots_not_class_union():
    admin, teachers, campus, subject, english = setup()
    t1, t2 = [t[1] for t in teachers]
    shared, other = student(t1, campus), student(t1, campus)
    a = schedule(t1, classroom(t1, subject, 3, [shared, other]), 6, 1, '08:00', '10:00')
    body = body_of(a)
    body['students'][0]['weekly_slots'] = [{'weekday': 7, 'slot_number': 1}]
    assert t1.patch(f"/api/teacher/classes/{a['id']}", json=body).status_code == 422
    # Historical records remain readable, though new mixed-period writes are blocked.
    from app.db import SessionLocal,ClassRoom,Enrollment,StudentWeeklySlot
    with SessionLocal.begin() as db:
        db.get(ClassRoom,a['id']).slots=[]
        enrollment=db.query(Enrollment).filter_by(class_id=a['id'],student_id=shared).one()
        enrollment.slots=[StudentWeeklySlot(weekday=7,slot_number=1,slot_label='第1档')]
    schedule(t2, classroom(t2, english, 3, [shared]), 6, 1, '08:00', '10:00')
    assert admin.get('/api/admin/schedule-warnings').json() == []
