"""Independent regression cases for legacy schedules and concurrent upgrades."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import asyncio
import sqlite3

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from test_acceptance import reset, setup, student, classroom, broadcast
from app import main
from app.db import Base, SessionLocal, StudentWeeklySlot, Enrollment, now, Student, ClassRoom, Broadcast, Snapshot
from app import migrations
from app.migrations import migrate_stable_ids, migrate_student_schedules


def seed_legacy_v2(db):
    for table in ('users', 'dictionaries'):
        db.exec_driver_sql(f'ALTER TABLE {table} DROP COLUMN deleted_at')
    stamp = now()
    db.exec_driver_sql("INSERT INTO dictionaries(id,kind,name) VALUES(1,'campus','旧校区'),(2,'subject','旧科目')")
    db.exec_driver_sql("INSERT INTO users(id,username,display_name,role,campus_id,enabled,session_version,created_at) VALUES(1,'old','虚构教师','teacher',1,1,0,?)", (stamp,))
    db.exec_driver_sql("INSERT INTO students(id,display_name,grade,campus_id,created_at,updated_at) VALUES(1,'虚构学生','高一',1,?,?)", (stamp, stamp))
    db.exec_driver_sql("INSERT INTO classes(id,teacher_id,subject_id,campus_id,grade,display_name,capacity,version,created_at,updated_at) VALUES(1,1,2,1,'高一','旧班',3,1,?,?)", (stamp, stamp))
    db.exec_driver_sql('INSERT INTO enrollments(id,class_id,student_id,created_at) VALUES(1,1,1,?)', (stamp,))
    db.exec_driver_sql("INSERT INTO weekly_slots(id,class_id,weekday,slot_label) VALUES(1,1,3,'三档'),(2,1,4,'四档')")


def test_unmapped_legacy_slots_keep_distinct_times_in_class_workload():
    admin, teachers, campus, subject, _ = setup()
    teacher = teachers[0][1]
    room = classroom(teacher, subject, 3, [student(teacher, campus), student(teacher, campus)])
    with SessionLocal.begin() as db:
        for enrollment in db.query(Enrollment).filter_by(class_id=room['id']):
            enrollment.slots = [StudentWeeklySlot(weekday=3, slot_number=None,
                slot_label='旧特殊时段', start_time=start, end_time=end)
                for start, end in [('09:00', '10:00'), ('14:00', '15:00')]]
    data = admin.get('/api/admin/reports').json()
    assert data['teachers'][0]['weekly_lessons'] == 2
    assert len(data['classes'][0]['weekly_slots']) == 2
    assert len(teacher.get(f"/api/teacher/classes/{room['id']}").json()['weekly_slots']) == 2


@pytest.mark.parametrize('version', [1, 2])
def test_simultaneous_upgrade_rechecks_version_after_acquiring_lock(tmp_path, version):
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.sqlite3'),
        connect_args={'check_same_thread': False, 'timeout': 10})
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        db.exec_driver_sql('INSERT INTO schema_versions VALUES (?, ?)', (version, now()))
        if version == 2:
            seed_legacy_v2(db)
    barrier = Barrier(2)
    @event.listens_for(engine, 'checkout')
    def trace(connection, record, proxy):
        connection.set_trace_callback(lambda sql: barrier.wait(timeout=5) if sql == 'BEGIN IMMEDIATE' else None)
    def upgrade():
        if version == 1:
            migrate_stable_ids(engine, tmp_path, Student.__table__, ClassRoom.__table__)
        else:
            migrate_student_schedules(engine, tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(upgrade) for _ in range(2)]
            for future in futures:
                future.result(timeout=15)
        with engine.connect() as db:
            assert db.exec_driver_sql('SELECT MAX(version) FROM schema_versions').scalar() == version + 1
            if version == 2:
                assert db.exec_driver_sql('SELECT COUNT(*) FROM student_weekly_slots').scalar() == 2
    finally:
        engine.dispose()


def test_broadcast_ticker_recovers_after_transient_database_failure(monkeypatch):
    admin, _, campus, _, _ = setup()
    bid = broadcast(admin, campus)
    with SessionLocal.begin() as db:
        b = db.get(Broadcast, bid)
        b.starts_at = '2000-01-01T00:00:00+00:00'
        b.deadline_at = '2000-01-02T00:00:00+00:00'
    calls = []
    sleeps = []
    original = main.write
    def write(db):
        calls.append(True)
        if len(calls) == 1:
            raise OperationalError('BEGIN IMMEDIATE', {}, sqlite3.OperationalError('database is locked'))
        return original(db)
    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise asyncio.CancelledError
    monkeypatch.setattr(main, 'write', write)
    monkeypatch.setattr(main.asyncio, 'sleep', sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main.ticker())
    assert len(calls) == 2
    with SessionLocal() as db:
        assert db.query(Snapshot).filter_by(broadcast_id=bid).count() == 1
        assert db.get(Broadcast, bid).closed_at


def test_failed_schedule_migration_rolls_back_and_can_retry(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path / 'interrupted.sqlite3'))
    Base.metadata.create_all(engine)
    with engine.begin() as db:
        db.exec_driver_sql('INSERT INTO schema_versions VALUES(2, ?)', (now(),))
        seed_legacy_v2(db)
    original = migrations.legacy_slot_number
    def interrupted(label):
        if label == '四档':
            raise RuntimeError('injected upgrade interruption')
        return original(label)
    monkeypatch.setattr(migrations, 'legacy_slot_number', interrupted)
    try:
        with pytest.raises(RuntimeError, match='injected'):
            migrate_student_schedules(engine, tmp_path)
        with engine.connect() as db:
            assert db.exec_driver_sql('SELECT MAX(version) FROM schema_versions').scalar() == 2
            assert db.exec_driver_sql('SELECT COUNT(*) FROM student_weekly_slots').scalar() == 0
            assert 'deleted_at' not in {row[1] for row in db.exec_driver_sql('PRAGMA table_info(users)')}
        monkeypatch.setattr(migrations, 'legacy_slot_number', original)
        migrate_student_schedules(engine, tmp_path)
        with engine.connect() as db:
            assert db.exec_driver_sql('SELECT MAX(version) FROM schema_versions').scalar() == 3
            assert db.exec_driver_sql('SELECT COUNT(*) FROM student_weekly_slots').scalar() == 2
            assert db.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
    finally:
        engine.dispose()
