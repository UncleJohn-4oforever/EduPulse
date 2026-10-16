"""Read-only schedule advisories, separate from reports and historical snapshots."""
from collections import defaultdict
from itertools import combinations
from .db import ClassRoom, User
from .reports import class_slots, consistent_read


def overlap_kind(a, b):
    if a['weekday'] != b['weekday']:
        return None
    if all(s.get('start_time') and s.get('end_time') for s in (a, b)):
        return 'time_overlap' if max(a['start_time'], b['start_time']) < min(a['end_time'], b['end_time']) else None
    if a['slot_number'] is not None and a['slot_number'] == b['slot_number']:
        return 'possible_overlap'
    return None


def schedule_warnings(db, teacher_id=None):
    consistent_read(db)
    query = db.query(ClassRoom).join(User, User.id == ClassRoom.teacher_id).filter(User.deleted_at.is_(None))
    grouped = defaultdict(list)
    students = defaultdict(list)
    rooms = query.order_by(ClassRoom.id).all()
    # Cross-teacher student conflicts need all current enrollments, but only
    # return conflicts involving the requesting teacher's own classes.
    for room in rooms:
        if teacher_id is None or room.teacher_id == teacher_id:
            grouped[room.teacher_id].append((room, class_slots(room)))
        for enrollment in room.enrollments:
            students[enrollment.student_id].append((room, enrollment))
    warnings = []
    for uid, rooms in grouped.items():
        for (a, slots_a), (b, slots_b) in combinations(rooms, 2):
            for sa in slots_a:
                for sb in slots_b:
                    kind = overlap_kind(sa, sb)
                    if not kind:
                        continue
                    warnings.append({'teacher_id': uid, 'teacher_name': db.get(User, uid).display_name,
                        'weekday': sa['weekday'], 'kind': kind,
                        'classes': [{'id': room.id, 'display_name': room.display_name, **slot}
                                    for room, slot in ((a, sa), (b, sb))]})
    from .reports import student_slot_json
    for student_id, enrollments in students.items():
        for (a, ea), (b, eb) in combinations(enrollments, 2):
            if teacher_id is not None and teacher_id not in (a.teacher_id, b.teacher_id):
                continue
            for sa in map(student_slot_json, ea.slots):
                for sb in map(student_slot_json, eb.slots):
                    kind = overlap_kind(sa, sb)
                    if not kind:
                        continue
                    warnings.append({'scope': 'student', 'kind': kind,
                        'student_id': student_id, 'student_name': ea.student.display_name,
                        'teacher_ids': sorted({a.teacher_id, b.teacher_id}),
                        'weekday': sa['weekday'],
                        'classes': [{'id': room.id, 'display_name': room.display_name,
                                     'teacher_name': db.get(User, room.teacher_id).display_name, **slot}
                                    for room, slot in ((a, sa), (b, sb))]})
    return warnings
