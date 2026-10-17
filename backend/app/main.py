import os, json, secrets, asyncio, time, logging, hashlib
from pathlib import Path
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from collections import defaultdict, deque
from fastapi import FastAPI, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError, OperationalError
from argon2.exceptions import VerificationError, InvalidHashError
from .db import *
from .security import *
from .schemas import *
from .reports import report, filtered, teacher_json, class_json, consistent_read
from .schedules import schedule_warnings
from . import exports
from .freeze_compare import metrics as freeze_metrics, compare as compare_freezes

# All writes are serialized in SQLite; version checks prevent stale edits.
def write(db):
    db.execute(text('BEGIN IMMEDIATE'))
    # Recheck authenticated sessions after acquiring the write lock.
    sessions=[x for x in db.identity_map.values() if isinstance(x,LoginSession)]
    db.expire_all()
    for session in sessions:
        user=db.get(User,session.user_id)
        if session.expires_at<=now() or not user or not user.enabled or user.session_version!=session.version:
            raise HTTPException(401,'会话已失效，请重新登录')
    # Freeze expired rounds before accepting any new data mutation.
    return finalize_due(db)
def dictionary(db,id,kind,allow_deleted=False):
    d=db.get(Dictionary,id)
    if not d or d.kind!=kind or (d.deleted_at and not allow_deleted): raise HTTPException(422,'该'+{'campus':'校区','subject':'科目','grade':'年级'}.get(kind,kind)+'不存在或已删除，请选择有效类别')
    return d
def grade_check(db,grade,previous=None):
    d=db.query(Dictionary).filter_by(kind='grade',name=grade).first()
    if not d or (d.deleted_at and grade!=previous):raise HTTPException(422,'请选择有效年级；该年级不存在或已删除')
def own(db,id,user):
    c=db.get(ClassRoom,id)
    if not c or c.teacher_id!=user.id: raise HTTPException(404,'班级不存在或无权限')
    return c

def progress(db,b):
    return {'id':b.id,'title':b.title,'starts_at':b.starts_at,'deadline_at':b.deadline_at,'closed_at':b.closed_at,'status':'已结束' if b.closed_at else '已截止' if b.deadline_at<=now() else '未开始' if b.starts_at>now() else '进行中','targets':[{'teacher_id':t.teacher_id,'display_name':db.get(User,t.teacher_id).display_name,'username':db.get(User,t.teacher_id).username,'confirmed_at':t.confirmed_at,'deleted':bool(db.get(User,t.teacher_id).deleted_at)} for t in b.targets],'has_snapshot':bool(db.query(Snapshot).filter_by(broadcast_id=b.id).first())}
def annotate(data,b):
    data['broadcast']=b
    targets={t['teacher_id']:t for t in b['targets']}
    for t in data['teachers']:
        target=targets.get(t['id'])
        t['confirmation']='已确认' if target and target['confirmed_at'] else '未经本轮确认' if target else '非本轮目标'
    return data
def freeze(db,b,actor=None):
    if db.query(Snapshot).filter_by(broadcast_id=b.id).first(): return
    b.closed_at=now()
    data=report(db)
    data=annotate(data,progress(db,b)|{'has_snapshot':True})
    db.add(Snapshot(broadcast_id=b.id,data=json.dumps(data,ensure_ascii=False)))
    audit(db,actor,'snapshot.freeze','broadcast',b.id)
def finalize_due(db):
    changed=False
    for b in db.query(Broadcast).filter(Broadcast.closed_at.is_(None),Broadcast.deadline_at<=now()).all():
        freeze(db,b); changed=True
    return changed

connections={}
async def notify(event,teacher_ids=None):
    for ws,uid in list(connections.items()):
        try:
            with SessionLocal() as db:
                user=db.get(User,uid)
                session=db.get(LoginSession,digest(ws.cookies.get(COOKIE,'')))
                valid=user and user.enabled and session and session.version==user.session_version and session.expires_at>now()
                if not valid:
                    await ws.close(code=4401); connections.pop(ws,None); continue
                if user.role=='admin' or teacher_ids is None or uid in teacher_ids: await ws.send_json({'event':event})
        except Exception: connections.pop(ws,None)
def tick_database():
    with SessionLocal() as db:
        changed=write(db); db.commit()
    return changed

async def ticker():
    while True:
        await asyncio.sleep(15)
        try:
            # SQLite's busy timeout must not block all HTTP/WebSocket requests.
            changed=await asyncio.to_thread(tick_database)
        except OperationalError:
            logging.getLogger(__name__).exception('广播截止处理失败，将在下一轮重试')
            continue
        if changed: await notify('broadcast.updated')
@asynccontextmanager
async def lifespan(app):
    init_db(); task=asyncio.create_task(ticker())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):await task
app=FastAPI(title='EduPulse 1.2.2',lifespan=lifespan)
@app.middleware('http')
async def headers(request,call_next):
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response
@app.exception_handler(IntegrityError)
async def integrity(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409,content={'detail':'数据关联冲突或名称重复，请刷新后重试'})

def user_json(u): return {'id':u.id,'username':u.username,'display_name':u.display_name,'role':u.role,'campus_id':u.campus_id}
failures=defaultdict(deque)
_dummy=ph.hash(secrets.token_urlsafe(32))
@app.post('/api/auth/login')
def login(body:Login,request:Request,response:Response,db=Depends(get_db)):
    origin=request.headers.get('origin')
    if origin and origin!=str(request.base_url).rstrip('/'): raise HTTPException(403,'请求来源不受信任')
    ip=request.client.host if request.client else 'local'
    # Key by remote IP to also rate-limit guessing many usernames.
    write(db)
    bucket=failures[ip]; current=time.monotonic()
    while bucket and bucket[0]<current-300: bucket.popleft()
    if len(bucket)>=10: raise HTTPException(429,'登录尝试过多，请五分钟后重试')
    user=db.query(User).filter_by(username=body.username).first()
    valid=False
    try: valid=ph.verify(user.password_hash if user and user.password_hash else _dummy,body.password)
    except (VerificationError,InvalidHashError): pass
    if not valid or not user or not user.enabled:
        bucket.append(current); audit(db,None,'login.failed','auth','',{'ip':ip}); db.commit()
        raise HTTPException(401,'账号或密码错误，或账号不可用')
    user.last_login_at=now(); token,session=new_session(db,user)
    audit(db,user,'login.success','user',user.id); db.commit()
    response.set_cookie(COOKIE,token,httponly=True,secure=os.getenv('EDUPULSE_SECURE_COOKIE','false').lower()=='true',samesite='strict',max_age=8*3600)
    return {'user':user_json(user),'csrf_token':session.csrf}
@app.get('/api/auth/me')
def me(request:Request,user=Depends(current_user)): return {'user':user_json(user),'csrf_token':request.state.session.csrf}
@app.post('/api/auth/logout')
def logout(request:Request,response:Response,user=Depends(current_user),db=Depends(get_db)):
    write(db); db.delete(request.state.session); audit(db,user,'logout','user',user.id); db.commit(); response.delete_cookie(COOKIE)
    return {'ok':True}
@app.get('/api/dictionaries')
def dictionaries(user=Depends(current_user),db=Depends(get_db)):
    settings=db.get(WorkspaceSettings,1)
    return {'campus_name':settings.campus_name if settings else ''} | {k:[{'id':d.id,'name':d.name} for d in db.query(Dictionary).filter_by(kind=k).filter(Dictionary.deleted_at.is_(None)).order_by(Dictionary.id)] for k in ('campus','subject','grade')} | {'archived':{k:[{'id':d.id,'name':d.name} for d in db.query(Dictionary).filter_by(kind=k).filter(Dictionary.deleted_at.is_not(None)).order_by(Dictionary.id)] for k in ('campus','subject','grade')}}
@app.patch('/api/admin/settings/campus-name')
async def update_campus_name(body:CampusNameIn,user=Depends(admin),db=Depends(get_db)):
    write(db)
    settings=db.get(WorkspaceSettings,1)
    if settings:settings.campus_name=body.campus_name
    else:db.add(WorkspaceSettings(id=1,campus_name=body.campus_name))
    audit(db,user,'settings.campus_name.update','workspace_settings',1)
    db.commit()
    await notify('settings.updated')
    return {'campus_name':body.campus_name}
@app.post('/api/admin/dictionaries')
def create_dictionary(body:DictIn,user=Depends(admin),db=Depends(get_db)):
    write(db); d=db.query(Dictionary).filter_by(kind=body.kind,name=body.name).first()
    if d and not d.deleted_at:raise HTTPException(409,'该类别名称已存在')
    if d:d.deleted_at=None
    else:d=Dictionary(**body.model_dump());db.add(d)
    db.flush();audit(db,user,'dictionary.create_or_restore',body.kind,d.id);db.commit();return {'id':d.id,'name':d.name}
@app.get('/api/admin/teachers')
def teachers(user=Depends(admin),db=Depends(get_db)): return [teacher_json(u)|{'class_count':db.query(ClassRoom).filter_by(teacher_id=u.id).count()} for u in db.query(User).filter_by(role='teacher').filter(User.deleted_at.is_(None)).order_by(User.id)]
@app.delete('/api/admin/teachers/{id}')
async def delete_teacher(id:ObjectId,confirmed:bool=False,user=Depends(admin),db=Depends(get_db)):
    write(db);u=db.get(User,id)
    if not u or u.role!='teacher' or u.deleted_at:raise HTTPException(404,'教师不存在或已删除')
    if not confirmed:raise HTTPException(422,'请确认删除教师及其当前班级关联、评价；学生档案和历史快照会保留')
    classes=db.query(ClassRoom).filter_by(teacher_id=id).all()
    audit(db,user,'teacher.delete','user',id,{'class_ids':[c.id for c in classes]})
    for c in classes:
        audit(db,user,'class.delete_with_teacher','class',c.id,{'student_ids':[e.student_id for e in c.enrollments]})
        db.delete(c)
    u.deleted_at=now();u.enabled=False;u.password_hash=None;u.session_version+=1
    db.commit();await notify('account.updated',[id]);return {'ok':True,'deleted_classes':len(classes)}
@app.delete('/api/admin/dictionaries/{id}')
async def delete_dictionary(id:ObjectId,confirmed:bool=False,user=Depends(admin),db=Depends(get_db)):
    write(db);d=db.get(Dictionary,id)
    if not d or d.deleted_at:raise HTTPException(404,'类别不存在或已删除')
    if not confirmed:raise HTTPException(422,'请明确确认删除；已关联记录和历史名称会保留')
    d.deleted_at=now();audit(db,user,'dictionary.delete',d.kind,id)
    db.commit();await notify('dictionary.updated');return {'ok':True}
def add_teacher(db,body,user):
    dictionary(db,body.campus_id,'campus')
    u=User(username='t_'+secrets.token_hex(5),display_name=body.display_name,role='teacher',campus_id=body.campus_id)
    db.add(u); db.flush(); audit(db,user,'teacher.create','user',u.id)
    return u
@app.post('/api/admin/teachers')
def create_teacher(body:TeacherIn,user=Depends(admin),db=Depends(get_db)):
    write(db); u=add_teacher(db,body,user); db.commit(); return teacher_json(u)
@app.post('/api/admin/teachers/import')
def import_teachers(body:TeacherImport,user=Depends(admin),db=Depends(get_db)):
    write(db); result=[teacher_json(add_teacher(db,b,user)) for b in body.teachers]; db.commit(); return result
@app.patch('/api/admin/teachers/{id}')
async def update_teacher(id:ObjectId,body:TeacherPatch,user=Depends(admin),db=Depends(get_db)):
    write(db); u=db.get(User,id)
    if not u or u.role!='teacher' or u.deleted_at: raise HTTPException(404,'教师不存在')
    dictionary(db,body.campus_id,'campus',allow_deleted=body.campus_id==u.campus_id)
    # Keep existing class campus consistent with teacher campus.
    if u.campus_id!=body.campus_id:
        for c in db.query(ClassRoom).filter_by(teacher_id=id): c.campus_id=body.campus_id; c.version+=1; c.updated_at=now()
    if u.enabled!=body.enabled: u.session_version+=1
    u.display_name=body.display_name; u.campus_id=body.campus_id; u.enabled=body.enabled
    audit(db,user,'teacher.update','user',u.id,{'enabled':u.enabled}); db.commit(); await notify('account.updated',[id]); return teacher_json(u)
def issue(db,id,user):
    u=db.get(User,id)
    if not u or u.role!='teacher' or not u.enabled or u.deleted_at: raise HTTPException(422,'请选择启用的教师账号')
    password=random_password(); u.password_hash=ph.hash(password); u.password_issued_at=now(); u.password_changed_at=now(); u.session_version+=1
    audit(db,user,'password.reset','user',u.id)
    return {'id':u.id,'display_name':u.display_name,'username':u.username,'password':password}
@app.post('/api/admin/teachers/issue-passwords')
async def issue_many(body:IDs,user=Depends(admin),db=Depends(get_db)):
    write(db); result=[issue(db,id,user) for id in dict.fromkeys(body.ids)]; db.commit(); await notify('account.updated',body.ids); return result
@app.post('/api/admin/teachers/{id}/issue-password')
async def issue_one(id:ObjectId,user=Depends(admin),db=Depends(get_db)):
    write(db); result=issue(db,id,user); db.commit(); await notify('account.updated',[id]); return result
@app.get('/api/students/search')
def search_students(q:str=Query(default='',max_length=80),user=Depends(current_user),db=Depends(get_db)):
    # Only identity fields, no enrollments, subject counts, or other teachers' evaluations.
    query=db.query(Student)
    if q:
        numeric_id=int(q) if q.isascii() and q.isdecimal() else None
        if numeric_id is not None and not 0<numeric_id<=2**63-1: numeric_id=None
        query=query.filter(Student.display_name.contains(q,autoescape=True) | (Student.id==numeric_id if numeric_id is not None else False))
    else: return []
    return [{'id':s.id,'display_name':s.display_name,'grade':s.grade} for s in query.order_by(Student.id).limit(30)]
@app.post('/api/students')
def create_student(body:StudentIn,user=Depends(current_user),db=Depends(get_db)):
    write(db); dictionary(db,body.campus_id,'campus'); grade_check(db,body.grade)
    if user.role=='teacher' and body.campus_id!=user.campus_id: raise HTTPException(403,'新建学生须使用所属校区')
    s=Student(**body.model_dump()); db.add(s); db.flush(); audit(db,user,'student.create','student',s.id); db.commit(); return {'id':s.id,'display_name':s.display_name,'grade':s.grade}
@app.get('/api/teacher/classes')
def my_classes(user=Depends(teacher),db=Depends(get_db)): return [class_json(c) for c in db.query(ClassRoom).filter_by(teacher_id=user.id).order_by(ClassRoom.id)]
@app.get('/api/teacher/schedule-warnings')
def teacher_schedule_warnings(user=Depends(teacher),db=Depends(get_db)):
    return schedule_warnings(db,user.id)
@app.get('/api/admin/schedule-warnings')
def admin_schedule_warnings(user=Depends(admin),db=Depends(get_db)):
    return schedule_warnings(db)
@app.get('/api/teacher/classes/{id}')
def get_class(id:ObjectId,user=Depends(teacher),db=Depends(get_db)): return class_json(own(db,id,user))
def save_class(db,c,body,user,new=False):
    dictionary(db,body.subject_id,'subject',allow_deleted=not new and c.subject_id==body.subject_id)
    if not new and (body.version is None or body.version!=c.version): raise HTTPException(409,'班级已被其他页面修改，请刷新后重试（未保存内容请先复制）')
    grades=[]
    for member in body.students:
        student=db.get(Student,member.student_id)
        if not student: raise HTTPException(422,'学生档案不存在')
        if student.grade not in grades: grades.append(student.grade)
    c.display_name=body.display_name; c.grade=' / '.join(grades); c.capacity=body.capacity; c.subject_id=body.subject_id; c.updated_at=now()
    c.name_is_manual=body.name_is_manual
    if not c.name_is_manual and body.students:
        slot=body.students[0].weekly_slots[0]
        c.display_name=f"周{'一二三四五六日'[slot.weekday-1]}{'一二三四五六'[slot.slot_number-1]}档"
    if not new: c.version+=1
    # Schedules now belong to each student's enrollment. Old class slots are retired.
    c.slots=[]
    existing={e.student_id:e for e in c.enrollments}; keep={m.student_id for m in body.students}
    for e in list(c.enrollments):
        if e.student_id not in keep:
            c.enrollments.remove(e); audit(db,user,'enrollment.remove','class',c.id,{'student_id':e.student_id})
    for m in body.students:
        e=existing.get(m.student_id)
        if not e:
            e=Enrollment(student_id=m.student_id); c.enrollments.append(e)
            e.evaluation=Evaluation(level=m.level,note=m.note,updated_by=user.id)
        elif e.evaluation.level!=m.level or e.evaluation.note!=m.note:
            e.evaluation.level=m.level; e.evaluation.note=m.note; e.evaluation.updated_at=now(); e.evaluation.updated_by=user.id
        e.slots=[StudentWeeklySlot(weekday=s.weekday,slot_number=s.slot_number,slot_label=f'第{s.slot_number}档',start_time=s.start_time,end_time=s.end_time) for s in m.weekly_slots]
    db.flush(); audit(db,user,'class.create' if new else 'class.update','class',c.id)
@app.post('/api/teacher/classes')
async def create_class(body:ClassIn,user=Depends(teacher),db=Depends(get_db)):
    write(db);dictionary(db,user.campus_id,'campus'); c=ClassRoom(teacher_id=user.id,campus_id=user.campus_id); db.add(c)
    # Avoid flushing incomplete required fields before validation.
    with db.no_autoflush: save_class(db,c,body,user,new=True)
    db.commit(); await notify('data.updated', [user.id]); return class_json(c)
@app.patch('/api/teacher/classes/{id}')
async def update_class(id:ObjectId,body:ClassIn,user=Depends(teacher),db=Depends(get_db)):
    write(db); c=own(db,id,user); save_class(db,c,body,user); db.commit(); await notify('data.updated',[user.id]); return class_json(c)
@app.delete('/api/teacher/classes/{id}')
async def delete_class(id:ObjectId,confirmed:bool=False,version:int|None=None,user=Depends(teacher),db=Depends(get_db)):
    write(db); c=own(db,id,user)
    if not confirmed: raise HTTPException(422,'请明确确认删除')
    if version!=c.version: raise HTTPException(409,'班级已更新，请刷新后再删除')
    audit(db,user,'class.delete','class',id,{'student_ids':[e.student_id for e in c.enrollments]}); db.delete(c); db.commit(); await notify('data.updated',[user.id]); return {'ok':True}
@app.get('/api/broadcasts/current')
def current_broadcasts(user=Depends(current_user),db=Depends(get_db)):
    rows=db.query(Broadcast).filter(Broadcast.deadline_at>now(),Broadcast.starts_at<=now(),Broadcast.closed_at.is_(None)).order_by(Broadcast.id.desc()).all()
    return [{'id':b.id,'title':b.title,'starts_at':b.starts_at,'deadline_at':b.deadline_at,'confirmed_at':next((t.confirmed_at for t in b.targets if t.teacher_id==user.id),None)} for b in rows if user.role=='admin' or any(t.teacher_id==user.id for t in b.targets)]
@app.post('/api/admin/broadcasts')
async def create_broadcast(body:BroadcastIn,user=Depends(admin),db=Depends(get_db)):
    if body.deadline_at<=datetime.now(timezone.utc): raise HTTPException(422,'截止时间必须晚于当前时间')
    write(db); query=db.query(User).filter_by(role='teacher',enabled=True)
    if body.campus_id: dictionary(db,body.campus_id,'campus'); query=query.filter_by(campus_id=body.campus_id)
    if body.teacher_ids: query=query.filter(User.id.in_(body.teacher_ids))
    users=query.all()
    if not users or (body.teacher_ids and set(body.teacher_ids)!={u.id for u in users}): raise HTTPException(422,'目标教师为空或含不属于此范围的账号')
    b=Broadcast(title=body.title,starts_at=body.starts_at.isoformat(),deadline_at=body.deadline_at.isoformat(),created_by=user.id,targets=[Target(teacher_id=u.id) for u in users]); db.add(b); db.flush(); audit(db,user,'broadcast.create','broadcast',b.id); db.commit(); await notify('broadcast.created',[u.id for u in users]); return progress(db,b)
@app.get('/api/admin/broadcasts')
def list_broadcasts(user=Depends(admin),db=Depends(get_db)):
    return [progress(db,b) for b in db.query(Broadcast).order_by(Broadcast.id.desc())]
@app.get('/api/admin/broadcasts/{id}/progress')
def get_progress(id:ObjectId,user=Depends(admin),db=Depends(get_db)):
    b=db.get(Broadcast,id)
    if not b: raise HTTPException(404,'广播不存在')
    return progress(db,b)
@app.post('/api/broadcasts/{id}/confirm')
async def confirm_broadcast(id:ObjectId,user=Depends(teacher),db=Depends(get_db)):
    write(db); b=db.get(Broadcast,id); target=db.get(Target,(id,user.id))
    if not b or not target: raise HTTPException(404,'任务不存在或不属于您')
    if b.closed_at or b.deadline_at<=now() or b.starts_at>now(): raise HTTPException(409,'任务未开始、已截止或已结束')
    target.confirmed_at=now(); db.flush(); audit(db,user,'broadcast.confirm','broadcast',id)
    if all(t.confirmed_at for t in b.targets): freeze(db,b,user)
    db.commit(); await notify('broadcast.updated',[t.teacher_id for t in b.targets]); return {'ok':True,'confirmed_at':target.confirmed_at}
@app.post('/api/admin/broadcasts/{id}/close')
async def close_broadcast(id:ObjectId,user=Depends(admin),db=Depends(get_db)):
    write(db); b=db.get(Broadcast,id)
    if not b: raise HTTPException(404,'广播不存在')
    freeze(db,b,user); db.commit(); await notify('broadcast.updated',[t.teacher_id for t in b.targets]); return progress(db,b)

def source(db,broadcast_id):
    if not broadcast_id:
        data=report(db)
        stamp=now()
        b=db.query(Broadcast).filter(Broadcast.starts_at<=stamp,Broadcast.deadline_at>stamp,Broadcast.closed_at.is_(None)).order_by(Broadcast.id.desc()).first()
        if b: annotate(data,progress(db,b))
        return data
    b=db.get(Broadcast,broadcast_id)
    if not b: raise HTTPException(404,'广播不存在')
    if not b.closed_at and b.deadline_at<=now():
        write(db); freeze(db,b); db.commit()
    s=db.query(Snapshot).filter_by(broadcast_id=broadcast_id).first()
    if not s: raise HTTPException(409,'本轮尚未结束，快照尚未冻结；可先结束本轮或导出实时数据')
    return json.loads(s.data)
@app.get('/api/admin/broadcasts/{id}/snapshot')
def get_snapshot(id:ObjectId,user=Depends(admin),db=Depends(get_db)): return source(db,id)
@app.get('/api/admin/reports')
def all_reports(broadcast_id:ObjectId|None=None,campus_id:ObjectId|None=None,subject_id:ObjectId|None=None,teacher_id:ObjectId|None=None,q:str='',grade:str='',search_type:Literal['teacher','student']='teacher',user=Depends(admin),db=Depends(get_db)):
    return filtered(source(db,broadcast_id),campus_id,subject_id,teacher_id,q,grade,search_type)

def frozen_json(row,include_data=False):
    data=json.loads(row.data)
    result={k:getattr(row,k) for k in ('id','title','note','created_by_name','captured_at')}
    result['metrics']=data.get('frozen_metrics') or freeze_metrics(data)
    result['teacher_count']=len(data['teachers']);result['class_count']=len(data['classes']);result['student_count']=len(data['students'])
    if include_data:result['data']=data
    return result

@app.get('/api/admin/freezes')
def list_freezes(user=Depends(admin),db=Depends(get_db)):
    return [frozen_json(row) for row in db.query(FrozenRecord).order_by(FrozenRecord.id.desc())]

@app.post('/api/admin/freezes')
async def create_freeze(body:FreezeIn,user=Depends(admin),db=Depends(get_db)):
    write(db)
    data=report(db)
    data['freeze_basis']='global-v1'
    data['frozen_metrics']=freeze_metrics(data)
    data['student_merges']={}
    for entry in db.query(Audit).filter_by(action='student.merge').order_by(Audit.id):
        metadata=json.loads(entry.metadata_json)
        data['student_merges'][str(metadata['source_id'])]=int(entry.entity_id)
    row=FrozenRecord(title=body.title,note=body.note,created_by=user.id,created_by_name=user.display_name,captured_at=data['generated_at'],data=json.dumps(data,ensure_ascii=False))
    db.add(row);db.flush();audit(db,user,'freeze.create','frozen_record',row.id);db.commit()
    await notify('freeze.created',[])
    return frozen_json(row)

@app.get('/api/admin/freezes/compare')
def compare_frozen_records(old_id:ObjectId,new_id:ObjectId,user=Depends(admin),db=Depends(get_db)):
    if old_id>=new_id:raise HTTPException(422,'请选择较早的记录B和较新的记录A，且不能是同一份记录')
    old=db.get(FrozenRecord,old_id);new=db.get(FrozenRecord,new_id)
    if not old or not new:raise HTTPException(404,'冻结记录不存在')
    return {'old':frozen_json(old),'new':frozen_json(new),'metrics':compare_freezes(json.loads(old.data),json.loads(new.data))}

@app.get('/api/admin/freezes/{id}')
def read_freeze(id:ObjectId,user=Depends(admin),db=Depends(get_db)):
    row=db.get(FrozenRecord,id)
    if not row:raise HTTPException(404,'冻结记录不存在')
    return frozen_json(row,True)

@app.get('/api/admin/reports/{kind}')
def report_kind(kind:str,broadcast_id:ObjectId|None=None,campus_id:ObjectId|None=None,subject_id:ObjectId|None=None,teacher_id:ObjectId|None=None,q:str='',grade:str='',search_type:Literal['teacher','student']='teacher',view:Literal['all','occupancy','workload','students']='all',ordered_ids:str=Query(default='',max_length=100000),user=Depends(admin),db=Depends(get_db)):
    data=filtered(source(db,broadcast_id),campus_id,subject_id,teacher_id,q,grade,'student' if kind=='students' or view=='students' else search_type)
    data['scope']['campus_label']=db.get(Dictionary,campus_id).name if campus_id and db.get(Dictionary,campus_id) else '全部校区'
    data['scope']['subject_label']=db.get(Dictionary,subject_id).name if subject_id and db.get(Dictionary,subject_id) else '全部科目'
    if kind in ('occupancy','workload'): return data['teachers']
    if kind=='students': return data['students']
    if kind in ('export.xlsx','export.png'):
        if ordered_ids:
            try: order={int(value):i for i,value in enumerate(ordered_ids.split(','))}
            except ValueError: raise HTTPException(422,'排序编号格式无效')
            key='students' if view=='students' else 'teachers'
            data[key].sort(key=lambda row:order.get(row['id'],len(order)))
        # Release the read snapshot before acquiring a write lock for audit.
        db.rollback()
        write(db)
        audit(db,user,'report.export','broadcast' if broadcast_id else 'report',broadcast_id or 'current',{'format':kind,'view':view}); db.commit()
        try: content=exports.xlsx(data,view) if kind.endswith('xlsx') else exports.png(data,view)
        except RuntimeError as exc: raise HTTPException(503,str(exc))
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if kind.endswith('xlsx') else 'image/png',headers={'Content-Disposition':f'attachment; filename="EduPulse-{broadcast_id or "current"}.{kind.split(".")[-1]}"'})
    raise HTTPException(404,'报表不存在')
@app.post('/api/admin/students/merge')
def merge_students(body:MergeIn,user=Depends(admin),db=Depends(get_db)):
    write(db); a=db.get(Student,body.source_id); b=db.get(Student,body.target_id)
    if not a or not b or a.id==b.id: raise HTTPException(422,'请指定不同且存在的学生编号')
    source_enrollments=db.query(Enrollment).filter_by(student_id=a.id).all()
    target_classes={e.class_id for e in db.query(Enrollment).filter_by(student_id=b.id)}
    if any(e.class_id in target_classes for e in source_enrollments): raise HTTPException(409,'两个档案在同一班都有评价，请先人工移除重复关联后再合并')
    for e in source_enrollments:
        e.student_id=b.id; c=db.get(ClassRoom,e.class_id); c.version+=1; c.updated_at=now()
    audit(db,user,'student.merge','student',b.id,{'source_id':a.id}); db.flush(); db.delete(a); db.commit(); return {'ok':True}
@app.get('/api/admin/audit')
def audit_list(user=Depends(admin),db=Depends(get_db)):
    return [{'id':a.id,'actor_id':a.actor_id,'action':a.action,'entity_type':a.entity_type,'entity_id':a.entity_id,'timestamp':a.timestamp,'metadata':json.loads(a.metadata_json)} for a in db.query(Audit).order_by(Audit.id.desc()).limit(200)]

def student_deletion_preview(db,s):
    classes=[]
    for enrollment in db.query(Enrollment).filter_by(student_id=s.id).order_by(Enrollment.class_id):
        c=db.get(ClassRoom,enrollment.class_id)
        classes.append({'id':c.id,'display_name':c.display_name,'teacher':db.get(User,c.teacher_id).display_name,'teacher_id':c.teacher_id,'subject':db.get(Dictionary,c.subject_id).name,'capacity':c.capacity,'version':c.version})
    result={'student':{'id':s.id,'display_name':s.display_name,'grade':s.grade,'campus_id':s.campus_id},'classes':classes}
    result['token']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return result

@app.get('/api/admin/students/{id}/deletion-preview')
def preview_student_deletion(id:ObjectId,user=Depends(admin),db=Depends(get_db)):
    consistent_read(db)
    s=db.get(Student,id)
    if not s:raise HTTPException(404,'学生档案不存在，可能已经合并或删除')
    return student_deletion_preview(db,s)

@app.delete('/api/admin/students/{id}')
async def delete_student(id:ObjectId,token:str=Query(pattern='^[0-9a-f]{64}$'),confirmed:bool=False,user=Depends(admin),db=Depends(get_db)):
    if not confirmed:raise HTTPException(422,'请先核对删除影响并确认删除')
    write(db);s=db.get(Student,id)
    if not s:raise HTTPException(404,'学生档案不存在，可能已经合并或删除')
    preview=student_deletion_preview(db,s)
    if not secrets.compare_digest(preview['token'],token):raise HTTPException(409,'学生或关联班级已发生变化，请重新核对删除影响')
    for enrollment in db.query(Enrollment).filter_by(student_id=s.id).all():
        c=db.get(ClassRoom,enrollment.class_id);c.version+=1;c.updated_at=now()
        db.delete(enrollment)
    audit(db,user,'student.delete','student',s.id,{'student_name':s.display_name,'class_ids':[c['id'] for c in preview['classes']]})
    db.flush();db.delete(s);db.commit()
    await notify('student.deleted',list({c['teacher_id'] for c in preview['classes']}))
    return {'ok':True}
@app.get('/api/health')
def health(): return {'status':'ok','version':'1.2.2'}
@app.websocket('/ws/events')
async def events(ws:WebSocket):
    origin=ws.headers.get('origin')
    expected=('https' if ws.url.scheme=='wss' else 'http')+'://'+ws.headers.get('host','')
    if origin!=expected: await ws.close(code=4403); return
    token=ws.cookies.get(COOKIE,'')
    with SessionLocal() as db:
        s=db.get(LoginSession,digest(token)) if token else None
        u=db.get(User,s.user_id) if s else None
        if not s or not u or not u.enabled or s.expires_at<=now() or s.version!=u.session_version: await ws.close(code=4401); return
        uid=u.id
    await ws.accept(); connections[ws]=uid
    try:
        while True:
            try: await asyncio.wait_for(ws.receive_text(),timeout=20)
            except asyncio.TimeoutError: pass
            # Revalidate on every heartbeat, also handles invalidation across processes.
            with SessionLocal() as db:
                s=db.get(LoginSession,digest(token)); u=db.get(User,uid)
                if not s or not u.enabled or s.version!=u.session_version or s.expires_at<=now():
                    await ws.close(code=4401); break
            await ws.send_json({'event':'heartbeat'})
    except (WebSocketDisconnect,RuntimeError): pass
    finally: connections.pop(ws,None)

DIST=Path(__file__).parents[2]/'frontend/dist'
if (DIST/'assets').exists(): app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
@app.get('/{path:path}')
def spa(path:str):
    if path.startswith(('api/','ws/')): raise HTTPException(404,'接口不存在')
    if (DIST/'index.html').exists(): return FileResponse(DIST/'index.html')
    raise HTTPException(503,'请先构建前端：cd frontend && npm ci && npm run build')
