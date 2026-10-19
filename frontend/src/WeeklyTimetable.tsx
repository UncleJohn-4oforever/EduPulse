import {useEffect,useState} from 'react';
import {Menu} from 'lucide-react';
import {api,weekdays} from './api';
import {Lesson,lessonsFor,standardTimes,withConflicts} from './weeklySchedule';
import './weeklyTimetable.css';
import {TimetableCourseEditor,CourseTarget} from './TimetableCourseEditor';
type Row=Record<string,any>;
function LessonCard({lesson:l,showHints,onEdit}:{lesson:Lesson;showHints:boolean;onEdit?:()=>void}){
 const actual=[...new Set(l.slots.filter(s=>s.start_time||s.end_time).map(s=>`${s.start_time||'未填'}–${s.end_time||'未填'}`))];
 const different=l.period!==null&&l.slots.some(s=>(s.start_time&&s.start_time!==standardTimes[l.period!-1][0])||(s.end_time&&s.end_time!==standardTimes[l.period!-1][1]));
 const missing=l.slots.some(s=>!s.start_time||!s.end_time);
 return <article className={'week-lesson'+(showHints&&l.conflicts.length?' has-conflict':'')} data-class-id={l.room.id}>
  <strong>{l.room.display_name}</strong><span>{l.room.subject} · 一对{l.room.capacity} · {l.members.length}/{l.room.capacity}人</span>
  <span>{[...new Set(l.members.map(m=>m.grade).filter(Boolean))].join(' / ')||l.room.grade||'年级未填写'}</span>
  <p className="week-students">{l.members.map(m=>m.display_name).join('、')||'暂无学生'}</p>
  {showHints&&different&&<span className="week-notice">实际时间：{actual.join('、')}（与标准档位不同）</span>}
  {showHints&&missing&&<span className="week-time-missing">具体时间未填写完整，按档位展示</span>}
  {showHints&&l.conflicts.length>0&&<details className="week-conflict"><summary>排课冲突 · {l.conflicts.length}项</summary>{l.conflicts.map(t=><p key={t}>{t}</p>)}</details>}
  {onEdit&&<button className="week-edit-course" onClick={onEdit}>编辑课程</button>}
 </article>;
}
export function WeeklyTimetable({teachers,warnings=[],historical=false,schoolOrder=false,allowHintToggle=false,editing}:{teachers:Row[];warnings?:Row[];historical?:boolean;schoolOrder?:boolean;allowHintToggle?:boolean;editing?:{role?:'admin'|'teacher';dict:any;notify:(text:string,error?:boolean)=>void;onDirty:(v:boolean)=>void;onSaving:(v:boolean)=>void;onSaved:()=>void}}){
 const [hintsEnabled,setHintsEnabled]=useState(false),[editMode,setEditMode]=useState(false),[target,setTarget]=useState<CourseTarget|null>(null);
 const canEdit=!!editing&&!historical&&editMode;
 const choose=(teacher:Row,subject:string,slot:Row,classId?:number)=>setTarget({teacher,slot,classId,subjectId:teacher.classes?.find((c:Row)=>c.subject===subject)?.subject_id||editing?.dict.subject[0]?.id});
 const showHints=allowHintToggle?hintsEnabled:true;
 const lessons=withConflicts(lessonsFor(teachers),warnings);
 const groups=new Map<string,{subject:string;teacher:Row;lessons:Lesson[]}>();
 for(const t of teachers){
  const subjects=[...new Set((t.classes||[]).map((c:Row)=>c.subject||'未分类'))] as string[];
  for(const subject of subjects.length?subjects:['暂无科目'])groups.set(`${subject}:${t.id}`,{subject,teacher:t,lessons:lessons.filter(l=>l.teacher.id===t.id&&(l.room.subject||'未分类')===subject)});
 }
 const preferred=['语文','数学','英语','物理','化学'];
 const priority=(name:string)=>{const index=preferred.indexOf(name);return schoolOrder&&index>=0?index:preferred.length};
 const subjects=[...new Set([...groups.keys()].map(key=>key.slice(0,key.lastIndexOf(':'))))].sort((a,b)=>priority(a)-priority(b)||a.localeCompare(b,'zh-CN'));
 const unplaced=lessons.filter(l=>l.period===null||l.day<1||l.day>7);
 const noSlots=teachers.flatMap(t=>(t.classes||[]).filter((c:Row)=>!lessons.some(l=>l.room.id===c.id)).map((c:Row)=>`${t.display_name} · ${c.display_name}`));
 return <section className="week-overview" aria-label="周课表总览">
  <div className="section-title"><div><h2>周课表总览</h2><p className="help">{historical?'所选历史快照':'已保存课程'} · 周一至周日，六档固定时间{showHints?'；偏离时间和排课冲突仅作提醒。':'。'}</p></div><div className="week-controls">{editing&&<label className="week-hint-toggle"><input type="checkbox" role="switch" checked={canEdit} disabled={historical||!!target} onChange={e=>setEditMode(e.target.checked)}/>编辑模式<span>{historical?'历史只读':canEdit?'已开启':'已关闭'}</span></label>}{allowHintToggle&&<label className="week-hint-toggle"><input type="checkbox" role="switch" checked={hintsEnabled} onChange={e=>setHintsEnabled(e.target.checked)}/>显示提示<span>{hintsEnabled?'已开启':'已关闭'}</span></label>}<span className="badge">{teachers.length}位教师 · {lessons.length}个课次</span></div></div>
  {canEdit&&<p className="notice">编辑模式已开启：点击档位中的“新增课程”或已有课程的“编辑课程”，保存后同步到服务器。</p>}
  {!teachers.length&&<p className="teacher-empty">暂无符合当前条件的教师。</p>}
  {subjects.map(subject=><section className="week-subject" key={subject}><h3>{subject}</h3>{[...groups.values()].filter(g=>g.subject===subject).map(g=><div className="week-teacher" key={g.teacher.id}>
   <div className="week-teacher-heading"><strong>{g.teacher.display_name}</strong>{g.teacher.campus&&<span>{g.teacher.campus}</span>}<span>{g.lessons.length}个课次</span></div>
   <div className="week-scroll" tabIndex={0} role="region" aria-label={`${g.teacher.display_name} ${subject}周课表，可横向滚动`}><table className="week-grid"><caption className="sr-only">{g.teacher.display_name} · {subject} · 周课表</caption><thead><tr><th scope="col">档位 / 时间</th>{weekdays.map(d=><th scope="col" key={d}>周{d}</th>)}</tr></thead><tbody>{standardTimes.map(([start,end],i)=><tr key={i}><th scope="row"><strong>第{'一二三四五六'[i]}档</strong><span>{start}–{end}</span></th>{weekdays.map((_,day)=><td key={day}>{g.lessons.filter(l=>l.period===i+1&&l.day===day+1).map(l=><LessonCard key={l.key} lesson={l} showHints={showHints} onEdit={canEdit?()=>choose(l.teacher,l.room.subject,l.slots[0],l.room.id):undefined}/> )}{canEdit&&<button className="week-add-course" aria-label={`新增${g.teacher.display_name}周${weekdays[day]}第${i+1}档课程`} onClick={()=>choose(g.teacher,subject,{weekday:day+1,slot_number:i+1,start_time:start,end_time:end})}>＋ 新增课程</button>}</td>)}</tr>)}</tbody></table></div>
  </div>)}</section>)}
  {unplaced.length>0&&<div className={showHints?'notice warning':'week-unassigned'}><div><strong>{showHints?'以下课程档位无法归入六档，请核对':'其他档位课程'}</strong>{unplaced.map(l=><div key={l.key}><span>{l.teacher.display_name} · 周{weekdays[l.day-1]||'?'} · {l.slots[0]?.slot_label||'档位未填'}</span><LessonCard lesson={l} showHints={showHints} onEdit={canEdit?()=>choose(l.teacher,l.room.subject,l.slots[0],l.room.id):undefined}/></div>)}</div></div>}
  {(showHints||canEdit)&&noSlots.length>0&&<details className="week-unassigned"><summary>尚未填写上课档位的班级 · {noSlots.length}个</summary>{teachers.flatMap(t=>(t.classes||[]).filter((c:Row)=>!lessons.some(l=>l.room.id===c.id)).map((c:Row)=><p key={c.id}>{t.display_name} · {c.display_name} {canEdit&&<button onClick={()=>choose(t,c.subject,{weekday:3,slot_number:3,start_time:null,end_time:null},c.id)}>编辑课程</button>}</p>))}</details>}
  {target&&editing&&!historical&&<TimetableCourseEditor role={editing.role} target={target} dict={editing.dict} notify={editing.notify} onDirty={editing.onDirty} onSaving={editing.onSaving} onClose={()=>setTarget(null)} onSaved={()=>{setTarget(null);editing.onSaved()}}/>}
 </section>;
}
export function TeacherTimetable({user,dict,revision,onClasses,onMenu,notify,onDirty,onSaving}:{user:Row;dict:Row;revision:number;onClasses:(c:Row[])=>void;onMenu:()=>void;notify:(text:string,error?:boolean)=>void;onDirty:(v:boolean)=>void;onSaving:(v:boolean)=>void}){
 const [classes,setClasses]=useState<Row[]|null>(null),[warnings,setWarnings]=useState<Row[]>([]),[error,setError]=useState(''),[warningError,setWarningError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{let active=true;setError('');setWarningError('');
  api('/teacher/classes').then(rows=>{if(active){setClasses(rows);onClasses(rows)}}).catch(e=>{if(active)setError(e.message)});
  api('/teacher/schedule-warnings').then(rows=>{if(active)setWarnings(rows)}).catch(e=>{if(active){setWarnings([]);setWarningError(e.message)}});
  return()=>{active=false};
 },[revision,retry,onClasses]);
 return <div className="teacher-workspace"><div className="teacher-toolbar"><div className="teacher-title"><button className="icon-button mobile-toggle" aria-label="打开课程导航" onClick={onMenu}><Menu/></button><h1>周课表总览</h1></div><span className="muted">仅展示您自己的课程</span></div>
 {error?<div className="error-box" role="alert">读取课表失败：{error}<button onClick={()=>setRetry(v=>v+1)}>重试</button></div>:classes===null?<p>正在读取课表…</p>:<>
 {warningError&&<div className="notice warning" role="alert">跨班冲突提醒暂不可用：{warningError}<button onClick={()=>setRetry(v=>v+1)}>重试</button></div>}
 <WeeklyTimetable editing={{role:'teacher',dict,notify,onDirty,onSaving,onSaved:()=>setRetry(v=>v+1)}} teachers={[{...user,classes:classes.map(c=>({...c,subject:dict.subject.find((s:Row)=>s.id===c.subject_id)?.name||dict.archived?.subject?.find((s:Row)=>s.id===c.subject_id)?.name||'未分类'}))}]} warnings={warnings}/></>}
 </div>;
}
