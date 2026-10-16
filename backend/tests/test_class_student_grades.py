from test_acceptance import reset, setup, student, classroom, body_of
from app.db import SessionLocal, ClassRoom


def test_class_grade_follows_students_without_grade_input():
    admin, teachers, campus, subject, _ = setup()
    teacher = teachers[0][1]
    sid = student(teacher, campus)
    payload = {'display_name': '周六一档', 'subject_id': subject, 'capacity': 3,
               'students': [{'student_id': sid, 'weekly_slots': [{'weekday': 6, 'slot_number': 1}]}]}
    response = teacher.post('/api/teacher/classes', json=payload)
    assert response.status_code == 200, response.text
    room = response.json()
    assert room['grade'] == '高一'
    assert room['display_name'] == '周六一档'
    # Obsolete client input cannot override student identity information.
    payload['grade'] = '初一'
    payload['version'] = room['version']
    response = teacher.patch(f"/api/teacher/classes/{room['id']}", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['grade'] == '高一'
    # Old class metadata is ignored even before that class is edited.
    with SessionLocal.begin() as db:
        db.get(ClassRoom, room['id']).grade = '旧班级年级'
    assert teacher.get('/api/teacher/classes').json()[0]['grade'] == '高一'
    assert admin.get('/api/admin/reports').json()['classes'][0]['grade'] == '高一'


def test_mixed_grade_and_empty_classes_remain_supported():
    admin, teachers, campus, subject, _ = setup()
    teacher = teachers[0][1]
    a = student(teacher, campus)
    b = teacher.post('/api/students', json={'display_name': '另一年级学生', 'grade': '初一', 'campus_id': campus}).json()['id']
    room = classroom(teacher, subject, 3, [a, b])
    assert room['grade'] == '高一 / 初一'
    payload = body_of(room)
    payload.pop('grade')
    payload['students'] = payload['students'][1:]
    response = teacher.patch(f"/api/teacher/classes/{room['id']}", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['grade'] == '初一'
    payload['version'] = response.json()['version']
    payload['students'] = []
    response = teacher.patch(f"/api/teacher/classes/{room['id']}", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()['grade'] == ''
