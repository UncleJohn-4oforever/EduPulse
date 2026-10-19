from test_acceptance import reset
from app.db import SessionLocal,Dictionary,init_db


def test_new_install_has_complete_subjects_and_grades():
    with SessionLocal() as db:
        assert [d.name for d in db.query(Dictionary).filter_by(kind='subject').order_by(Dictionary.id)]==['数学','英语','语文','物理','化学','生物','道法','历史']
        assert [d.name for d in db.query(Dictionary).filter_by(kind='grade').order_by(Dictionary.id)]==['初一','初二','初三','高一','高二','高三','一年级','二年级','三年级','四年级','五年级','六年级']
        assert [d.name for d in db.query(Dictionary).filter_by(kind='campus')]==['主校区']


def test_restart_preserves_customized_and_deleted_dictionary_entries():
    with SessionLocal.begin() as db:
        row=db.query(Dictionary).filter_by(kind='subject',name='历史').one()
        row.deleted_at='2026-10-19T00:00:00+00:00'
        db.add(Dictionary(kind='subject',name='校区自选科目'))
        db.query(Dictionary).filter_by(kind='grade',name='一年级').one().name='小学一年级'
        before=[(d.id,d.kind,d.name,d.deleted_at) for d in db.query(Dictionary).order_by(Dictionary.id)]
    init_db()
    with SessionLocal() as db:
        assert [(d.id,d.kind,d.name,d.deleted_at) for d in db.query(Dictionary).order_by(Dictionary.id)]==before
