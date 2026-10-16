import hashlib, secrets, os
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request, Depends
from argon2 import PasswordHasher
from .db import SessionLocal, LoginSession, User, now, Audit
ph=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
COOKIE='edupulse_session'
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def random_password():
    alphabet='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    while True:
        value=''.join(secrets.choice(alphabet) for _ in range(18))
        if any(c.isupper() for c in value) and any(c.islower() for c in value) and any(c.isdigit() for c in value): return value

def get_db():
    with SessionLocal() as db:
        try: yield db
        finally: db.rollback()
def current_user(request:Request,db=Depends(get_db)):
    token=request.cookies.get(COOKIE,'')
    session=db.get(LoginSession,digest(token)) if token else None
    user=db.get(User,session.user_id) if session else None
    if not session or session.expires_at<=now() or not user or not user.enabled or not user.password_hash or user.session_version!=session.version:
        raise HTTPException(401,'请登录，或会话已失效')
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            raise HTTPException(403,'请求来源不受信任')
        if not secrets.compare_digest(request.headers.get('x-csrf-token',''),session.csrf): raise HTTPException(403,'请求校验失败，请刷新页面')
    request.state.session=session
    return user
def admin(user=Depends(current_user)):
    if user.role!='admin': raise HTTPException(403,'仅教学主管可执行此操作')
    return user
def teacher(user=Depends(current_user)):
    if user.role!='teacher': raise HTTPException(403,'请使用教师账号')
    return user
def audit(db,user,action,kind,entity,metadata=None):
    import json
    db.add(Audit(actor_id=user.id if user else None,action=action,entity_type=kind,entity_id=str(entity),metadata_json=json.dumps(metadata or {},ensure_ascii=False)))
def new_session(db,user):
    token=secrets.token_urlsafe(40)
    row=LoginSession(token_hash=digest(token),user_id=user.id,version=user.session_version,csrf=secrets.token_urlsafe(32),expires_at=(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat())
    db.add(row)
    return token,row
