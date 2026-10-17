from fastapi.testclient import TestClient
from test_acceptance import reset, setup, client
from app.main import app
from app.db import SessionLocal, WorkspaceSettings, Audit, init_db


def test_campus_name_persists_and_keeps_existing_data():
    admin, teachers, campus, _, _ = setup(1)
    before = admin.get('/api/dictionaries').json()
    assert before['campus_name'] == ''
    response = admin.patch('/api/admin/settings/campus-name', json={'campus_name': '  滨江校区  '})
    assert response.status_code == 200, response.text
    assert response.json() == {'campus_name': '滨江校区'}
    # Startup initialization and a fresh login must keep the saved setting.
    init_db()
    saved = client().get('/api/dictionaries').json()
    assert saved == before | {'campus_name': '滨江校区'}
    assert teachers[0][1].get('/api/dictionaries').json()['campus_name'] == '滨江校区'
    assert admin.get('/api/admin/teachers').json()[0]['campus_id'] == campus
    assert admin.patch('/api/admin/settings/campus-name', json={'campus_name': '城西校区'}).status_code == 200
    with SessionLocal() as db:
        assert db.query(WorkspaceSettings).count() == 1
        assert db.get(WorkspaceSettings, 1).campus_name == '城西校区'
        assert db.query(Audit).filter_by(action='settings.campus_name.update').count() == 2


def test_campus_name_requires_admin_csrf_and_valid_name():
    admin, teachers, _, _, _ = setup(1)
    path = '/api/admin/settings/campus-name'
    payload = {'campus_name': '测试校区'}
    assert TestClient(app).patch(path, json=payload).status_code == 401
    assert teachers[0][1].patch(path, json=payload).status_code == 403
    csrf = admin.headers.pop('x-csrf-token')
    assert admin.patch(path, json=payload).status_code == 403
    admin.headers['x-csrf-token'] = csrf
    for body in ({'campus_name': ''}, {'campus_name': '  '}, {'campus_name': '校' * 41}, payload | {'id': 2}):
        assert admin.patch(path, json=body).status_code == 422
    assert admin.get('/api/dictionaries').json()['campus_name'] == ''
    assert admin.patch(path, json={'campus_name': '校' * 40}).status_code == 200


def test_restore_accepts_older_backup_and_restores_saved_name(tmp_path):
    import sqlite3
    import subprocess
    import sys
    from app.db import engine

    admin, _, _, _, _ = setup(0)
    path = '/api/admin/settings/campus-name'
    admin.patch(path, json={'campus_name': '备份校区'})
    backup = tmp_path / 'with-name.sqlite3'
    subprocess.run([sys.executable, '-m', 'app.cli', 'backup', '--output', str(backup)], check=True, capture_output=True)
    admin.patch(path, json={'campus_name': '之后的名称'})
    engine.dispose()
    subprocess.run([sys.executable, '-m', 'app.cli', 'restore', str(backup), '--confirm'], check=True, capture_output=True)
    init_db()
    assert client().get('/api/dictionaries').json()['campus_name'] == '备份校区'
    # Simulate an existing installation's backup from before this feature.
    with sqlite3.connect(backup) as db:
        db.execute('DROP TABLE workspace_settings')
    engine.dispose()
    subprocess.run([sys.executable, '-m', 'app.cli', 'restore', str(backup), '--confirm'], check=True, capture_output=True)
    init_db()
    assert client().get('/api/dictionaries').json()['campus_name'] == ''
