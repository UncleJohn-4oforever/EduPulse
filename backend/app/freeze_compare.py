"""Deterministic snapshot differences; no guesses about business motivations."""
from collections import defaultdict


def metrics(data):
    result={}
    for key,cap in [('three',3),('six',6)]:
        classes=[c for c in data['classes'] if c['capacity']==cap]
        seats=sum(len(c['students']) for c in classes);capacity=len(classes)*cap
        result[key]={'numerator':seats,'denominator':capacity,'classes':len(classes),'value':seats/capacity if capacity else None}
    total=sum(s['subject_count'] for s in data['students']);count=len(data['students'])
    result['subjects']={'numerator':total,'denominator':count,'value':total/count if count else None}
    return result


def compare(old,new):
    before=old.get('frozen_metrics') or metrics(old);after=new.get('frozen_metrics') or metrics(new);result={}
    teachers={t['id']:t['display_name'] for t in [*old['teachers'],*new['teachers']]}
    old_classes={c['id']:c for c in old['classes']};new_classes={c['id']:c for c in new['classes']}

    def event(key,title,details,dn,dd,kind,identity):
        base=before[key]['value']
        score=dn-base*dd if base is not None and after[key]['value'] is not None else 0
        direction='up' if score>1e-10 else 'down' if score< -1e-10 else 'neutral'
        return {'title':title,'details':details,'delta_numerator':dn,'delta_denominator':dd,'direction':direction,'kind':kind,'entity_id':identity}

    for key,cap in [('three',3),('six',6)]:
        events=[]
        for identity in sorted(old_classes.keys()|new_classes.keys()):
            a=old_classes.get(identity);b=new_classes.get(identity)
            was=a is not None and a['capacity']==cap;is_now=b is not None and b['capacity']==cap
            if not was and not is_now:continue
            old_seats=len(a['students']) if was else 0;new_seats=len(b['students']) if is_now else 0
            dn=new_seats-old_seats;dd=(int(is_now)-int(was))*cap
            if dn==0 and dd==0:continue
            c=b or a;owner=teachers.get(c['teacher_id'],'教师')
            cap_name=lambda n:{1:'一',3:'三',6:'六'}[n]
            if not a:action=f"新增一对{cap_name(cap)}班，{new_seats}人"
            elif not b:action=f"移除一对{cap_name(cap)}班，原{old_seats}人"
            elif a['capacity']!=b['capacity']:action=f"班型由一对{cap_name(a['capacity'])}调整为一对{cap_name(b['capacity'])}"
            else:action=f"人数由{old_seats}人变为{new_seats}人"
            details=[f'本指标席位：{old_seats} → {new_seats}；容量：{cap if was else 0} → {cap if is_now else 0}']
            old_members={s['student_id']:s['display_name'] for s in a['students']} if a else {}
            new_members={s['student_id']:s['display_name'] for s in b['students']} if b else {}
            for label,ids,members in [('新增学生',new_members.keys()-old_members.keys(),new_members),('移除关联',old_members.keys()-new_members.keys(),old_members)]:
                if ids:details.append(label+'：'+'、'.join(f'{members[i]} #{i}' for i in sorted(ids)))
            slots=c.get('weekly_slots',[])
            if slots:details.append('上课档位：'+'；'.join(f"周{'一二三四五六日'[s['weekday']-1]}{s['slot_label']}" for s in slots))
            events.append(event(key,f"{owner} · {c['display_name']}（班级 #{identity}）：{action}",details,dn,dd,'class',identity))
        result[key]={'before':before[key],'after':after[key],'events':events}

    # Canonicalize old identities through captured merge chains. Keep old counts
    # separately, so archival merges are explained rather than mistaken for churn.
    merges={int(k):int(v) for k,v in new.get('student_merges',{}).items()}
    def canonical(identity):
        seen=set()
        while identity in merges and identity not in seen:seen.add(identity);identity=merges[identity]
        return identity
    def grouped(data):
        groups=defaultdict(list)
        for s in data['students']:groups[canonical(s['id'])].append(s)
        return groups
    old_students=grouped(old);new_students=grouped(new);events=[]
    for identity in sorted(old_students.keys()|new_students.keys()):
        a=old_students[identity];b=new_students[identity]
        dn=sum(s['subject_count'] for s in b)-sum(s['subject_count'] for s in a);dd=len(b)-len(a)
        merged=bool(a and b and {s['id'] for s in a}!={s['id'] for s in b} and any(s['id'] in merges for s in a))
        if dn==0 and dd==0 and not merged:continue
        name=(b or a)[0]['display_name']
        if merged:action='档案合并：'+'、'.join('#'+str(s['id']) for s in a)+' → '+ '、'.join('#'+str(s['id']) for s in b)
        elif not a:action='新增学生'
        elif not b:action='移除学生档案'
        else:action='科目调整'
        subjects=lambda rows:'、'.join(dict.fromkeys(name for s in rows for name in s['subjects'])) or '无关联科目'
        details=[f'原科目：{subjects(a)}',f'现科目：{subjects(b)}',f"学生科目合计：{sum(s['subject_count'] for s in a)} → {sum(s['subject_count'] for s in b)}；学生数：{len(a)} → {len(b)}"]
        events.append(event('subjects',f'{name} #{identity}：{action}',details,dn,dd,'merge' if merged else 'student',identity))
    result['subjects']={'before':before['subjects'],'after':after['subjects'],'events':events}
    return result
