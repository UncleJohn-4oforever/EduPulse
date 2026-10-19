from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Literal, Annotated
from datetime import datetime, timezone
ObjectId = Annotated[int, Field(gt=0, le=2**63-1)]
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid', str_strip_whitespace=True)
class Login(Strict):
    # Passwords are exact secrets, including leading/trailing whitespace.
    model_config=ConfigDict(extra='forbid', str_strip_whitespace=False)
    username: str=Field(min_length=1,max_length=80)
    password: str=Field(min_length=1,max_length=256)
    @field_validator('username', mode='before')
    @classmethod
    def trim_username(cls,value):
        return value.strip() if isinstance(value,str) else value
class TeacherIn(Strict):
    display_name: str=Field(min_length=1,max_length=80)
    campus_id: ObjectId
class TeacherPatch(Strict):
    display_name: str=Field(min_length=1,max_length=80)
    campus_id: ObjectId
    enabled: bool
class IDs(Strict):
    ids: list[ObjectId]=Field(min_length=1,max_length=300)
class TeacherImport(Strict):
    teachers: list[TeacherIn]=Field(min_length=1,max_length=300)
class DictIn(Strict):
    kind: Literal['campus','subject','grade']
    name: str=Field(min_length=1,max_length=40)
class CampusNameIn(Strict):
    campus_name: str=Field(min_length=1,max_length=40)
class StudentIn(Strict):
    display_name: str=Field(min_length=1,max_length=80)
    grade: str=Field(min_length=1,max_length=40)
    campus_id: ObjectId
class Slot(Strict):
    weekday: int=Field(ge=1,le=7)
    slot_number: int=Field(ge=1,le=6)
    start_time: str|None=None
    end_time: str|None=None
    @field_validator('start_time','end_time')
    @classmethod
    def empty_time(cls,v):return v or None
    @model_validator(mode='after')
    def times(self):
        import re
        for value in (self.start_time,self.end_time):
            if value and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value):raise ValueError('时间格式为 HH:mm')
        if bool(self.start_time)!=bool(self.end_time):raise ValueError('请同时填写开始和结束时间，或都留空')
        if self.start_time and self.end_time<=self.start_time:raise ValueError('结束时间须晚于开始时间')
        return self
class NewClassStudent(Strict):
    display_name: str=Field(min_length=1,max_length=80)
    grade: str=Field(min_length=1,max_length=40)
class Member(Strict):
    student_id: ObjectId|None=None
    new_student: NewClassStudent|None=None
    level: Literal['A','B','C']='B'
    note: str=Field(default='',max_length=1000)
    weekly_slots: list[Slot]=Field(min_length=1,max_length=42)
    @model_validator(mode='after')
    def unique_slots(self):
        if (self.student_id is None)==(self.new_student is None):raise ValueError('请选择已有学生或填写新学生，不能同时提交')
        keys=[(s.weekday,s.slot_number) for s in self.weekly_slots]
        if len(keys)!=len(set(keys)):raise ValueError('同一学生不能重复选择同一星期、同一档位')
        return self
class ClassIn(Strict):
    # New editors submit one class schedule. Legacy clients remain readable.
    class_slot: Slot|None=None
    @model_validator(mode='before')
    @classmethod
    def shared_class_slot(cls,value):
        if isinstance(value,dict) and value.get('class_slot') is not None and isinstance(value.get('students',[]),list):
            return {**value,'students':[{**m,'weekly_slots':[value['class_slot']]} if isinstance(m,dict) else m for m in value.get('students',[])]}
        return value
    display_name: str=Field(min_length=1,max_length=100)
    name_is_manual: bool=True
    subject_id: ObjectId
    # Accepted for older clients; the server derives class grades from students.
    grade: str|None=Field(default=None,max_length=40)
    capacity: Literal[1,3,6]
    students: list[Member]=Field(default_factory=list,max_length=6)
    version: int|None=None
    @model_validator(mode='after')
    def members(self):
        if len(self.students)>self.capacity:raise ValueError('学生人数超过班型容量')
        ids=[m.student_id for m in self.students if m.student_id is not None]
        if len(set(ids))!=len(ids):raise ValueError('同一学生不能重复加入班级')
        slots=[s for m in self.students for s in m.weekly_slots]
        if any(len(m.weekly_slots)!=1 for m in self.students) or len({(s.weekday,s.slot_number) for s in slots})>1:
            raise ValueError('一个班级只能有一个档位，所有学生须使用相同星期和档位')
        times={}
        for member in self.students:
            for slot in member.weekly_slots:
                if slot.start_time:
                    key=(slot.weekday,slot.slot_number);value=(slot.start_time,slot.end_time)
                    if key in times and times[key]!=value:raise ValueError('同班同一星期同档位的具体时间须一致；也可以留空')
                    times[key]=value
        if slots:
            self.class_slot=self.class_slot or next((s for s in slots if s.start_time),slots[0])
            for member in self.students:member.weekly_slots=[self.class_slot]
        return self
class AdminClassIn(ClassIn):
    teacher_id: ObjectId

class BroadcastIn(Strict):
    title: str=Field(min_length=1,max_length=120)
    starts_at: datetime
    deadline_at: datetime
    campus_id: ObjectId|None=None
    teacher_ids: list[ObjectId]=Field(default_factory=list,max_length=300)
    @field_validator('starts_at','deadline_at')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None: raise ValueError('时间必须含时区')
        return v.astimezone(timezone.utc)
    @model_validator(mode='after')
    def dates(self):
        if self.deadline_at<=self.starts_at: raise ValueError('截止时间须晚于开始时间')
        return self
class MergeIn(Strict):
    source_id: ObjectId
    target_id: ObjectId

class FreezeIn(Strict):
    title: str=Field(min_length=1,max_length=120)
    note: str=Field(default='',max_length=1000)
