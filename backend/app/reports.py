from .db import User, ClassRoom, Student, Dictionary, now
from sqlalchemy import text

def consistent_read(db):
    # sqlite3's legacy mode does not BEGIN a transaction for SELECT statements.
    # Explicit BEGIN pins all report queries to one WAL revision.
    if not db.connection().connection.driver_connection.in_transaction:
        db.execute(text('BEGIN'))

def teacher_json(u):
    return {k:getattr(u,k) for k in ('id','username','display_name','campus_id','enabled','last_login_at','password_issued_at')} | {'has_password':bool(u.password_hash)}
def student_slot_json(s):
    return {'weekday':s.weekday,'slot_number':s.slot_number,'slot_label':s.slot_label,'start_time':s.start_time,'end_time':s.end_time}

def class_slots(c):
    if c.slots:
        from .migrations import legacy_slot_number
        return sorted([{'weekday':s.weekday,'slot_number':legacy_slot_number(s.slot_label),'slot_label':s.slot_label,'start_time':s.start_time,'end_time':s.end_time} for s in c.slots],key=lambda s:(s['weekday'],s['slot_number'] or 99,s['slot_label']))
    result={}
    for e in c.enrollments:
        for slot in e.slots:
            # Unknown legacy names have no period identity: preserve distinct times.
            identity=slot.slot_number if slot.slot_number is not None else (slot.slot_label,slot.start_time,slot.end_time)
            key=(slot.weekday,identity)
            if key not in result or (not result[key]['start_time'] and slot.start_time):result[key]=student_slot_json(slot)
    return sorted(result.values(),key=lambda s:(s['weekday'],s['slot_number'] or 99,s['slot_label']))

def class_json(c):
    slots=class_slots(c)
    return {k:getattr(c,k) for k in ('id','teacher_id','campus_id','subject_id','grade','display_name','capacity','version','updated_at')} | {
        'grade':' / '.join(dict.fromkeys(e.student.grade for e in c.enrollments)),
        'name_is_manual':c.name_is_manual,
        'weekly_slots':slots,
        'class_slot':{k:slots[0][k] for k in ('weekday','slot_number','start_time','end_time')} if len(slots)==1 and slots[0]['slot_number'] else None,
        'students':[{'enrollment_id':e.id,'student_id':e.student_id,'display_name':e.student.display_name,'grade':e.student.grade,'level':e.evaluation.level,'note':e.evaluation.note,'updated_at':e.evaluation.updated_at,'weekly_slots':[student_slot_json(s) for s in e.slots]} for e in c.enrollments]}
def report(db):
    consistent_read(db)
    dictionaries={d.id:d.name for d in db.query(Dictionary)}
    users=db.query(User).filter(User.role=='teacher',User.deleted_at.is_(None)).all()
    classes=db.query(ClassRoom).join(User,User.id==ClassRoom.teacher_id).filter(User.deleted_at.is_(None)).order_by(ClassRoom.id).all()
    teachers=[]
    for u in users:
        owned=[c for c in classes if c.teacher_id==u.id]
        groups={}
        for cap in (1,3,6):
            cs=[c for c in owned if c.capacity==cap]
            seats=sum(len(c.enrollments) for c in cs); capacity=len(cs)*cap
            groups[str(cap)]={'classes':len(cs),'seats':seats,'capacity':capacity,'vacancies':capacity-seats,'rate':seats/capacity if capacity else None,'weekly_lessons':sum(len(class_slots(c)) for c in cs)}
        small_capacity=groups['3']['capacity']+groups['6']['capacity']; small_seats=groups['3']['seats']+groups['6']['seats']
        teachers.append(teacher_json(u)|{'campus':dictionaries.get(u.campus_id,''),'groups':groups,'small_rate':small_seats/small_capacity if small_capacity else None,'small_seats':small_seats,'small_capacity':small_capacity,'weekly_lessons':sum(len(class_slots(c)) for c in owned),'class_count':len(owned),'classes':[class_json(c)|{'subject':dictionaries[c.subject_id]} for c in owned]})
    students=[]
    for s in db.query(Student).order_by(Student.id):
        details=[]
        for c in classes:
            for e in c.enrollments:
                if e.student_id==s.id:
                    u=next(u for u in users if u.id==c.teacher_id)
                    details.append({'subject_id':c.subject_id,'subject':dictionaries[c.subject_id],'teacher_id':u.id,'teacher':u.display_name,'class_id':c.id,'class_name':c.display_name,'campus_id':c.campus_id,'campus':dictionaries[c.campus_id],'level':e.evaluation.level,'note':e.evaluation.note,'updated_at':e.evaluation.updated_at,'weekly_slots':[student_slot_json(s) for s in e.slots]})
        students.append({'id':s.id,'display_name':s.display_name,'grade':s.grade,'campus_id':s.campus_id,'subject_count':len({d['subject_id'] for d in details}),'subjects':list(dict.fromkeys(d['subject'] for d in details)),'details':details})
    return {'generated_at':now(),'workload_basis':'student-slot-union','teachers':teachers,'students':students,'classes':[class_json(c)|{'subject':dictionaries[c.subject_id]} for c in classes]}

def filtered(data,campus_id=None,subject_id=None,teacher_id=None,q='',grade='',search_type='teacher'):
    # Recompute from class-level truth when scope changes; never average percentages.
    import copy
    result=copy.deepcopy(data)
    teachers=[]
    for t in result['teachers']:
        if campus_id and t['campus_id']!=campus_id: continue
        if teacher_id and t['id']!=teacher_id: continue
        if search_type=='teacher' and q and q.casefold() not in (t['display_name']+' '+t['username']).casefold(): continue
        cs=[c for c in t['classes'] if not subject_id or c['subject_id']==subject_id]
        if subject_id and not cs: continue
        t['classes']=cs
        for cap in (1,3,6):
            matching=[c for c in cs if c['capacity']==cap]
            seats=sum(len(c['students']) for c in matching); capacity=cap*len(matching)
            t['groups'][str(cap)]={'classes':len(matching),'seats':seats,'capacity':capacity,'vacancies':capacity-seats,'rate':seats/capacity if capacity else None,'weekly_lessons':sum(len(c['weekly_slots']) for c in matching)}
        t['small_seats']=sum(t['groups'][str(c)]['seats'] for c in (3,6)); t['small_capacity']=sum(t['groups'][str(c)]['capacity'] for c in (3,6))
        t['small_rate']=t['small_seats']/t['small_capacity'] if t['small_capacity'] else None
        t['class_count']=len(cs); t['weekly_lessons']=sum(len(c['weekly_slots']) for c in cs)
        teachers.append(t)
    result['teachers']=teachers
    students=[]
    for s in result['students']:
        if grade and s['grade']!=grade: continue
        if search_type=='student' and q and q.casefold() not in (s['display_name']+' '+str(s['id'])).casefold(): continue
        ds=[d for d in s['details'] if (not campus_id or d['campus_id']==campus_id) and (not subject_id or d['subject_id']==subject_id) and (not teacher_id or d['teacher_id']==teacher_id) and (not q or search_type=='student' or d['teacher_id'] in {t['id'] for t in teachers})]
        if not ds:
            if subject_id or teacher_id or (q and search_type=='teacher'):continue
            # An unassigned student still belongs to their profile's campus.
            # Students attending other campuses keep the class-based scope.
            if campus_id and (s['details'] or s['campus_id']!=campus_id):continue
        s['details']=ds; s['subjects']=list(dict.fromkeys(d['subject'] for d in ds)); s['subject_count']=len(s['subjects'])
        students.append(s)
    result['students']=students
    result['classes']=[c for t in teachers for c in t['classes']]
    result['scope']={'campus_id':campus_id,'subject_id':subject_id,'teacher_id':teacher_id,'q':q,'grade':grade,'search_type':search_type}
    return result
