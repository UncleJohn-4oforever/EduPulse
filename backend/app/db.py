import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.types import String, Text

DATA = Path(os.environ.get('EDUPULSE_DATA_DIR', str(Path.home() / 'EduPulseData'))).expanduser()
DATA.mkdir(parents=True, exist_ok=True)
engine = create_engine('sqlite:///' + str(DATA / 'edupulse.sqlite3'), connect_args={'check_same_thread': False, 'timeout':30})
@event.listens_for(engine, 'connect')
def pragmas(conn, _):
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
SessionLocal = sessionmaker(engine, expire_on_commit=False)
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass
class WorkspaceSettings(Base):
    __tablename__='workspace_settings'
    id: Mapped[int] = mapped_column(primary_key=True)
    campus_name: Mapped[str] = mapped_column(String(40))
    __table_args__=(CheckConstraint('id = 1'),)
class Dictionary(Base):
    __tablename__='dictionaries'
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    deleted_at: Mapped[str|None]
    __table_args__=(UniqueConstraint('kind','name'),)
class User(Base):
    __tablename__='users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(10))
    campus_id: Mapped[int|None] = mapped_column(ForeignKey('dictionaries.id'))
    password_hash: Mapped[str|None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    session_version: Mapped[int] = mapped_column(default=0)
    password_issued_at: Mapped[str|None]
    password_changed_at: Mapped[str|None]
    last_login_at: Mapped[str|None]
    created_at: Mapped[str] = mapped_column(default=now)
    deleted_at: Mapped[str|None]
class LoginSession(Base):
    __tablename__='sessions'
    token_hash: Mapped[str] = mapped_column(String(64),primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int]
    csrf: Mapped[str]
    expires_at: Mapped[str]
class Student(Base):
    __tablename__='students'
    __table_args__={'sqlite_autoincrement':True}
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(40))
    campus_id: Mapped[int] = mapped_column(ForeignKey('dictionaries.id'))
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)
class ClassRoom(Base):
    __tablename__='classes'
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    subject_id: Mapped[int] = mapped_column(ForeignKey('dictionaries.id'))
    campus_id: Mapped[int] = mapped_column(ForeignKey('dictionaries.id'))
    grade: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(100))
    name_is_manual: Mapped[bool] = mapped_column(default=True, server_default='1')
    capacity: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)
    slots: Mapped[list['WeeklySlot']] = relationship(cascade='all, delete-orphan',order_by='WeeklySlot.id')
    enrollments: Mapped[list['Enrollment']] = relationship(cascade='all, delete-orphan',order_by='Enrollment.id')
    __table_args__=(CheckConstraint('capacity IN (1,3,6)'),{'sqlite_autoincrement':True})
class WeeklySlot(Base):
    __tablename__='weekly_slots'
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id'))
    weekday: Mapped[int]
    slot_label: Mapped[str] = mapped_column(String(80))
    start_time: Mapped[str|None]
    end_time: Mapped[str|None]
    __table_args__=(CheckConstraint('weekday BETWEEN 1 AND 7'),)
class Enrollment(Base):
    __tablename__='enrollments'
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    created_at: Mapped[str] = mapped_column(default=now)
    student: Mapped['Student'] = relationship()
    evaluation: Mapped['Evaluation'] = relationship(cascade='all, delete-orphan',uselist=False)
    slots: Mapped[list['StudentWeeklySlot']] = relationship(cascade='all, delete-orphan',order_by='StudentWeeklySlot.id')
    __table_args__=(UniqueConstraint('student_id','class_id'),)
class StudentWeeklySlot(Base):
    __tablename__='student_weekly_slots'
    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey('enrollments.id'))
    weekday: Mapped[int]
    slot_number: Mapped[int|None]
    slot_label: Mapped[str] = mapped_column(String(80))
    start_time: Mapped[str|None]
    end_time: Mapped[str|None]
    __table_args__=(CheckConstraint('weekday BETWEEN 1 AND 7'),CheckConstraint('slot_number IS NULL OR slot_number BETWEEN 1 AND 6'))
class Evaluation(Base):
    __tablename__='student_evaluations'
    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey('enrollments.id'),unique=True)
    level: Mapped[str] = mapped_column(String(1))
    note: Mapped[str] = mapped_column(Text,default='')
    updated_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[str] = mapped_column(default=now)
    __table_args__=(CheckConstraint("level IN ('A','B','C')"),)
class Broadcast(Base):
    __tablename__='broadcasts'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    starts_at: Mapped[str]
    deadline_at: Mapped[str]
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[str] = mapped_column(default=now)
    closed_at: Mapped[str|None]
    targets: Mapped[list['Target']] = relationship(cascade='all, delete-orphan')
class Target(Base):
    __tablename__='broadcast_targets'
    broadcast_id: Mapped[int] = mapped_column(ForeignKey('broadcasts.id'),primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'),primary_key=True)
    confirmed_at: Mapped[str|None]
class Snapshot(Base):
    __tablename__='broadcast_snapshots'
    id: Mapped[int] = mapped_column(primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(ForeignKey('broadcasts.id'),unique=True)
    captured_at: Mapped[str] = mapped_column(default=now)
    data: Mapped[str] = mapped_column(Text)
class Audit(Base):
    __tablename__='audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int|None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    timestamp: Mapped[str] = mapped_column(default=now)
    metadata_json: Mapped[str] = mapped_column(Text,default='{}')
class FrozenRecord(Base):
    __tablename__='frozen_records'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(Text,default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_by_name: Mapped[str] = mapped_column(String(80))
    captured_at: Mapped[str] = mapped_column(default=now)
    data: Mapped[str] = mapped_column(Text)
    __table_args__={'sqlite_autoincrement':True}
class SchemaVersion(Base):
    __tablename__='schema_versions'
    version: Mapped[int] = mapped_column(primary_key=True)
    applied_at: Mapped[str] = mapped_column(default=now)

def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if not db.get(SchemaVersion,1): db.add(SchemaVersion(version=1))
    from .migrations import migrate_stable_ids, migrate_student_schedules, migrate_class_names, migrate_frozen_records
    migrate_stable_ids(engine,DATA,Student.__table__,ClassRoom.__table__)
    migrate_student_schedules(engine,DATA)
    migrate_class_names(engine,DATA)
    migrate_frozen_records(engine)
    with SessionLocal.begin() as db:
        if not db.query(Dictionary).first():
            for kind,names in {'campus':['主校区'],'subject':['数学','英语','语文','物理','化学','生物','道法','历史'],'grade':['初一','初二','初三','高一','高二','高三','一年级','二年级','三年级','四年级','五年级','六年级']}.items():
                db.add_all([Dictionary(kind=kind,name=n) for n in names])
