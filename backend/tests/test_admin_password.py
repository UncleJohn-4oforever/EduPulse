import json
import sys
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from test_acceptance import reset,setup,client,student,classroom
from app.main import app
from app.db import SessionLocal,User,Audit,LoginSession
from app import cli
from app.security import ph

OLD='TestOnlyPassword2026'
NEW='ChangedAdminPassword2026'

def test_password_change_revokes_all_own_sessions_preserves_other_users_and_data():
    admin,teachers,campus,subject,_=setup();other=client();teacher=teachers[0][1]
    classroom(teacher,subject,3,[student(teacher,campus)])
    before=admin.get('/api/admin/reports').json()
    with SessionLocal.begin() as db:
        db.add(User(username='second-admin',display_name='第二主管',role='admin',password_hash=ph.hash(OLD)))
    second=client('second-admin')
    result=admin.post('/api/admin/change-password',json={'current_password':OLD,'new_password':NEW})
    assert result.status_code==200,result.text
    assert admin.get('/api/auth/me').status_code==401 and other.get('/api/auth/me').status_code==401
    assert second.get('/api/auth/me').status_code==200 and teacher.get('/api/auth/me').status_code==200
    assert TestClient(app).post('/api/auth/login',json={'username':'test-admin','password':OLD}).status_code==401
    fresh=client(password=NEW);after=fresh.get('/api/admin/reports').json()
    assert before['classes']==after['classes'] and before['students']==after['students']
    with SessionLocal() as db:
        user=db.query(User).filter_by(username='test-admin').one();assert ph.verify(user.password_hash,NEW)
        logs=db.query(Audit).filter_by(action='admin.password.change').all();assert len(logs)==1
        assert OLD not in str(vars(logs[0])) and NEW not in str(vars(logs[0]))

def test_password_change_permissions_validation_and_attempt_limit():
    admin,teachers,_,_,_=setup();endpoint='/api/admin/change-password'
    payload={'current_password':OLD,'new_password':NEW}
    assert TestClient(app).post(endpoint,json=payload).status_code==401
    assert teachers[0][1].post(endpoint,json=payload).status_code==403
    csrf=admin.headers.pop('x-csrf-token');assert admin.post(endpoint,json=payload).status_code==403;admin.headers['x-csrf-token']=csrf
    for value in ['short1','OnlyLettersWithoutDigits','1234567890123456','x1'*129]:
        assert admin.post(endpoint,json={**payload,'new_password':value}).status_code==422
    assert admin.post(endpoint,json={**payload,'new_password':OLD}).status_code==400
    for _ in range(5):assert admin.post(endpoint,json={**payload,'current_password':'incorrect'}).status_code==400
    assert admin.get('/api/auth/me').status_code==200
    assert admin.post(endpoint,json=payload).status_code==429
    with SessionLocal() as db:assert ph.verify(db.query(User).filter_by(username='test-admin').one().password_hash,OLD)

def test_password_spaces_are_preserved():
    admin=client();password='  KeepSpacesPassword2026  '
    assert admin.post('/api/admin/change-password',json={'current_password':OLD,'new_password':password}).status_code==200
    assert TestClient(app).post('/api/auth/login',json={'username':'test-admin','password':password.strip()}).status_code==401
    assert client(password=password).get('/api/auth/me').status_code==200

def test_local_recovery_is_interactive_and_preserves_data(capsys):
    admin,teachers,campus,subject,_=setup();teacher=teachers[0][1]
    classroom(teacher,subject,3,[student(teacher,campus)])
    before=admin.get('/api/admin/reports').json()
    with patch.object(sys,'argv',['run.py','reset-admin-password']),patch('builtins.input',side_effect=['test-admin','test-admin']),patch.object(cli.getpass,'getpass',side_effect=[NEW,NEW]):cli.main()
    output=capsys.readouterr().out;assert NEW not in output and OLD not in output
    assert admin.get('/api/auth/me').status_code==401 and teacher.get('/api/auth/me').status_code==200
    after=client(password=NEW).get('/api/admin/reports').json()
    assert before['classes']==after['classes'] and before['students']==after['students']
    with SessionLocal() as db:assert db.query(Audit).filter_by(action='admin.password.reset.local').count()==1

@pytest.mark.parametrize('account,confirm,passwords',[('not-an-admin','',[]),('test-admin','wrong',[]),('test-admin','test-admin',['InvalidShort1']),('test-admin','test-admin',[NEW,NEW+'mismatch'])])
def test_local_recovery_rejects_invalid_input_without_changing_password(account,confirm,passwords):
    with patch.object(sys,'argv',['run.py','reset-admin-password']),patch('builtins.input',side_effect=[account,confirm]),patch.object(cli.getpass,'getpass',side_effect=passwords),pytest.raises(SystemExit):cli.main()
    with SessionLocal() as db:
        assert ph.verify(db.query(User).filter_by(username='test-admin').one().password_hash,OLD)
        assert db.query(Audit).filter_by(action='admin.password.reset.local').count()==0
