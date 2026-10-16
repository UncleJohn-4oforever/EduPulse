import {useCallback,useEffect,useRef,useState} from 'react';
import {Plus,Save,Trash2,ChevronDown,Check,Menu} from 'lucide-react';
import {api,date,weekdays} from './api';
import {automaticClassName,inheritedSlots,rememberedSubject,rememberSubject} from './classDefaults';

type Row=Record<string,any>;
type Dict={subject:Row[];grade:Row[];archived?:{subject:Row[]}};
type Notify=(text:string,error?:boolean)=>void;
const slotText=(s:Row)=>`周${weekdays[s.weekday-1]} ${s.slot_number?`第${s.slot_number}档`:s.slot_label}${s.start_time&&s.end_time?` ${s.start_time}–${s.end_time}`:''}`;
export function teacherDayCounts(classes:Row[]){
 return weekdays.map((_,i)=>({day:i+1,count:classes.reduce((n,c)=>n+(c.weekly_slots||[]).filter((s:Row)=>s.weekday===i+1).length,0)})).filter(d=>d.count);
}

export function TeacherPage({user,dict,revision,onDirty,onSaving,onClasses,day,notify,Warnings,onMenu}:{user:Row;dict:Dict;revision:number;onDirty:(v:boolean)=>void;onSaving:(v:boolean)=>void;onClasses:(rows:Row[])=>void;day:number|null;notify:Notify;Warnings:React.ComponentType<{rows:Row[]}>;onMenu:()=>void}){
 const [classes,setClasses]=useState<Row[]>([]),[tasks,setTasks]=useState<Row[]>([]),[newClass,setNewClass]=useState(false),[warnings,setWarnings]=useState<Row[]>([]),[loaded,setLoaded]=useState(false),[busy,setBusy]=useState(false),[dirtyMap,setDirtyMap]=useState<Record<string,boolean>>({});
 const [loadErrors,setLoadErrors]=useState<Record<string,string>>({});
 const savingRef=useRef<Record<string,boolean>>({});
 const saving=useCallback((id:string,value:boolean)=>{savingRef.current={...savingRef.current,[id]:value};onSaving(Object.values(savingRef.current).some(Boolean))},[onSaving]);
 const dirtyRef=useRef<Record<string,boolean>>({}),loadVersion=useRef(0);
 const load=useCallback(async()=>{
  const v=++loadVersion.current;
  const run=async(key:string,path:string,apply:(data:Row[])=>void)=>{try{const data=await api(path);if(v!==loadVersion.current)return;apply(data);setLoadErrors(e=>{const next={...e};delete next[key];return next})}catch(error){if(v===loadVersion.current)setLoadErrors(e=>({...e,[key]:(error as Error).message}))}};
  await Promise.allSettled([
   run('classes','/teacher/classes',next=>{setClasses(current=>[...next,...current.filter(c=>dirtyRef.current[String(c.id)]&&!next.some(n=>n.id===c.id))]);onClasses(next);setLoaded(true)}),
   run('warnings','/teacher/schedule-warnings',setWarnings),
   run('tasks','/broadcasts/current',setTasks)
  ]);
 },[onClasses]);
 useEffect(()=>{load()},[load,revision]);
 useEffect(()=>()=>{loadVersion.current++;onSaving(false)},[onSaving]);
 const mark=useCallback((id:string,value:boolean)=>{dirtyRef.current={...dirtyRef.current,[id]:value};setDirtyMap(m=>m[id]===value?m:{...m,[id]:value})},[]);
 const dirty=Object.values(dirtyMap).some(Boolean);useEffect(()=>onDirty(dirty),[dirty,onDirty]);
 const confirmTask=async(task:Row)=>{if(dirty){notify('请先保存或取消班级修改，再确认本轮数据。',true);return}if(!confirm(`确认「${task.title}」：所有班级数据已核对？`))return;setBusy(true);try{await api(`/broadcasts/${task.id}/confirm`,'POST');await load();notify('本轮数据已确认')}catch(e){notify((e as Error).message,true)}finally{setBusy(false)}};
 const visible=classes.filter(c=>!day||c.weekly_slots.some((s:Row)=>s.weekday===day));
 const relevantWarnings=warnings.filter(w=>!day||w.weekday===day);
 return <div className="teacher-workspace">
  <div className="teacher-toolbar"><div className="teacher-title"><button className="icon-button mobile-toggle" aria-label="打开课程导航" onClick={onMenu}><Menu/></button><h1>{day?`周${weekdays[day-1]}课程`:'班级总览'}</h1><span className="badge">{visible.length} 个班级</span>{dirty&&<span className="badge warning">有未保存修改</span>}</div><button className="primary" disabled={newClass||!dict.subject.length} onClick={()=>setNewClass(true)}><Plus size={18}/>新增班级</button></div>
  {tasks.map(task=><div className="teacher-task" key={task.id}><div><strong>{task.title}</strong><small>截止 {date(task.deadline_at)}{task.confirmed_at?` · 已确认 ${date(task.confirmed_at)}`:''}</small></div><button className="primary" disabled={busy} onClick={()=>confirmTask(task)}><Check size={17}/>{task.confirmed_at?'再次确认':'确认本轮数据'}</button></div>)}
  {Object.entries(loadErrors).map(([key,error])=><div role="alert" className="notice warning" key={key}><span>{key==='classes'?'班级加载失败':key==='warnings'?'冲突提醒暂不可用，当前不能确认是否有冲突':'核对任务暂不可用'}：{error}</span><button onClick={()=>load()}>重试</button></div>)}
  {!loaded&&!loadErrors.classes&&<p className="muted">正在加载班级…</p>}
  <Warnings rows={relevantWarnings}/>
  {newClass&&<ClassEditor key="new" user={user} dict={dict} initial={null} day={day} notify={notify} mark={mark} onSaving={saving} onSaved={()=>{mark('new',false);setNewClass(false);load()}} onDelete={()=>{mark('new',false);setNewClass(false)}}/>}
  {classes.map(c=><div key={c.id} hidden={!visible.includes(c)}><ClassEditor user={user} dict={dict} initial={c} day={day} notify={notify} mark={mark} onSaving={saving} onSaved={()=>{mark(String(c.id),false);load()}} onDelete={()=>{mark(String(c.id),false);load()}}/></div>)}
  {loaded&&!loadErrors.classes&&!visible.length&&!newClass&&<div className="teacher-empty">{day?'当天还没有班级。':'还没有班级。'}点击“新增班级”开始录入。</div>}
 </div>;
}

function ClassEditor({user,dict,initial,day,notify,mark,onSaving,onSaved,onDelete}:{user:Row;dict:Dict;initial:Row|null;day:number|null;notify:Notify;mark:(id:string,v:boolean)=>void;onSaving:(id:string,v:boolean)=>void;onSaved:()=>void;onDelete:()=>void}){
 const id=String(initial?.id||'new');
 const blank=()=>({display_name:'',name_is_manual:false,subject_id:rememberedSubject({id:user.id,username:user.username},dict.subject as {id:number}[]),capacity:6,students:[]});
 const [form,setForm]=useState<Row>(()=>structuredClone(initial||blank())),[saved,setSaved]=useState<Row>(()=>structuredClone(initial||blank())),[open,setOpen]=useState(!initial),[busy,setBusy]=useState(false);
 const busyRef=useRef(false);
 const changed=!initial||JSON.stringify(form)!==JSON.stringify(saved);
 useEffect(()=>mark(id,changed),[id,changed,mark]);
 useEffect(()=>{if(initial&&!changed&&initial.version>saved.version){setForm(structuredClone(initial));setSaved(structuredClone(initial))}},[initial,changed,saved.version]);
 const effectiveName=form.name_is_manual?form.display_name.trim():automaticClassName(form.students)||form.display_name.trim();
 const update=(key:string,value:any)=>{if(key==='subject_id')rememberSubject({id:user.id,username:user.username},Number(value));setForm(f=>({...f,[key]:value,...(key==='display_name'?{name_is_manual:!!value.trim()}:{})}))};
 const member=(index:number,value:Row)=>setForm(f=>({...f,students:f.students.map((s:Row,i:number)=>i===index?{...s,...value}:s)}));
 const subjectRows:Row[]=[...dict.subject,...(dict.archived?.subject||[]).filter(s=>s.id===form.subject_id).map(s=>({...s,name:s.name+'（已删除）'}))];
 const subject=subjectRows.find(s=>s.id===Number(form.subject_id))?.name||'—';
 const add=()=>setForm(f=>{const slots=inheritedSlots(f.students);if(!f.students.length&&day)slots[0].weekday=day;return {...f,students:[...f.students,{draft_key:crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`,student_id:null,display_name:'',grade:f.students[0]?.grade||dict.grade.find(g=>g.name==='高一')?.name||dict.grade[0]?.name||'',weekly_slots:slots,level:'B',note:''}]}});
 const save=async()=>{
  if(busyRef.current)return;
  if(!effectiveName){notify('请填写学生档位以自动命名，或手动填写班级名称。',true);return}
  if(form.students.some((s:Row)=>!s.display_name.trim()||!s.grade||!s.weekly_slots.length||s.weekly_slots.some((slot:Row)=>!slot.slot_number||!!slot.start_time!==!!slot.end_time||(slot.start_time&&slot.end_time<=slot.start_time)))){notify('请补全学生姓名、年级和档位；时间需同时填写且结束晚于开始。',true);return}
  if(form.students.some((s:Row)=>new Set(s.weekly_slots.map((slot:Row)=>`${slot.weekday}-${slot.slot_number}`)).size!==s.weekly_slots.length)){notify('同一学生不能重复选择同星期、同档位。',true);return}
  const known=form.students.filter((s:Row)=>s.student_id).map((s:Row)=>s.student_id);if(new Set(known).size!==known.length){notify('同一学生不能重复加入本班。',true);return}
  const times=new Map();for(const s of form.students)for(const slot of s.weekly_slots){if(!slot.start_time)continue;const key=`${slot.weekday}-${slot.slot_number}`,value=`${slot.start_time}-${slot.end_time}`;if(times.has(key)&&times.get(key)!==value){notify('同班同星期同档位的具体时间须一致。',true);return}times.set(key,value)}
  busyRef.current=true;setBusy(true);onSaving(id,true);
  try{
   const resolved:Row[]=structuredClone(form.students);
   for(let i=0;i<resolved.length;i++)if(!resolved[i].student_id){
    const s=resolved[i],matches:Row[]=await api('/students/search?q='+encodeURIComponent(s.display_name.trim()));
    if(matches.some(m=>m.display_name===s.display_name.trim())&&!confirm(`已有名为「${s.display_name}」的学生。确定是不同的学生，需要新建档案？取消后可从姓名下的搜索结果选择已有档案。`))return;
    const created=await api('/students','POST',{display_name:s.display_name,grade:s.grade,campus_id:user.campus_id});
    resolved[i]={...s,student_id:created.id,display_name:created.display_name,grade:created.grade};
    const index=i;setForm(f=>({...f,students:f.students.map((m:Row,j:number)=>j===index?resolved[index]:m)}));
   }
   const body={display_name:effectiveName,name_is_manual:form.name_is_manual??true,subject_id:Number(form.subject_id),capacity:Number(form.capacity),students:resolved.map(s=>({student_id:s.student_id,level:s.level,note:s.note,weekly_slots:s.weekly_slots.map((slot:Row)=>({weekday:slot.weekday,slot_number:slot.slot_number,start_time:slot.start_time||null,end_time:slot.end_time||null}))})),...(initial?{version:form.version}:{})};
   const result=await api('/teacher/classes'+(initial?'/'+initial.id:''),initial?'PATCH':'POST',body);rememberSubject({id:user.id,username:user.username},Number(result.subject_id));setForm(result);setSaved(result);setOpen(false);notify('班级已保存');onSaved();
  }catch(e){notify((e as Error).message,true)}finally{busyRef.current=false;setBusy(false);onSaving(id,false)}
 };
 const remove=async()=>{if(!confirm(`确定删除「${effectiveName||'新班级'}」及其学生关联、档位和评价？学生档案和历史快照保留。`))return;if(!initial){onDelete();return}if(busyRef.current)return;busyRef.current=true;setBusy(true);onSaving(id,true);try{await api(`/teacher/classes/${initial.id}?confirmed=true&version=${form.version}`,'DELETE');notify('班级已删除');onDelete()}catch(e){notify((e as Error).message,true)}finally{busyRef.current=false;setBusy(false);onSaving(id,false)}};
 return <section className={'class-editor panel compact-class '+(open?'editing':'collapsed')}>
  <div className="class-heading"><button className="class-toggle" aria-expanded={open} onClick={()=>setOpen(!open)}><span><strong>{effectiveName||'新建班级'}</strong><small>{user.display_name} · {subject} · 一对{form.capacity} · {form.students.length}/{form.capacity} 人</small></span><ChevronDown size={18} className={open?'rotated':''}/></button><span className={'badge '+(changed?'warning':'success')}>{changed?'待保存':'已保存'}</span><button className="icon-button danger-text" disabled={busy} onClick={remove} title="删除班级"><Trash2 size={18}/></button></div>
  {!open&&<div className="class-summary">{form.students.length?form.students.map((s:Row,i:number)=><div className="summary-student" key={s.student_id||s.draft_key||i}><strong>{s.display_name||'未填写姓名'}</strong><span>{s.grade}</span><span>{s.weekly_slots.map(slotText).join('；')}</span></div>):<span className="muted">暂无学生</span>}<button className="summary-edit" onClick={()=>setOpen(true)}>展开编辑</button></div>}
  {open&&<div className="class-body"><fieldset className="editor-fields" disabled={busy}>
   <div className="class-basics"><label>任课老师<input value={user.display_name} disabled/></label><label>科目<select aria-label="科目" value={form.subject_id||''} onChange={e=>update('subject_id',Number(e.target.value))}>{subjectRows.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>班型 / 容量<select aria-label="班型 / 容量" value={form.capacity} onChange={e=>{const capacity=Number(e.target.value);if(capacity<form.students.length){notify('请先移除多余学生。',true);return}update('capacity',capacity)}}>{[1,3,6].map(n=><option key={n} value={n}>一对{n} · {n}席位</option>)}</select></label></div>
   <div className="student-lines">{form.students.map((s:Row,i:number)=><StudentLine key={s.draft_key||s.student_id} student={s} dict={dict} existing={form.students.filter((_:Row,j:number)=>j!==i).map((m:Row)=>m.student_id)} onChange={value=>member(i,value)} onRemove={()=>{if((!s.display_name&&!s.student_id)||confirm(`从本班移除「${s.display_name}」及其档位和评价？`))update('students',form.students.filter((_:Row,j:number)=>j!==i))}} notify={notify}/>)}</div>
   <button className="add-student" disabled={form.students.length>=form.capacity} onClick={add}><Plus size={18}/>{form.students.length>=form.capacity?'已达到班型容量':'添加学生'}</button>
   <label className="class-name-field">班级名称<input aria-label="班级名称" maxLength={100} placeholder="按档位自动命名，也可手动输入" value={effectiveName} onChange={e=>update('display_name',e.target.value)}/>{form.name_is_manual&&form.students.length>0&&<button className="text-button" onClick={()=>update('display_name','')}>恢复自动命名</button>}</label>
   <div className="class-bottom"><span>{form.students.length} / {form.capacity} 人</span><div className="actions"><button onClick={()=>{if(!changed||confirm('取消未保存修改？')){if(initial){setForm(structuredClone(saved));setOpen(false)}else onDelete()}}}>取消</button><button className="primary" disabled={busy||!changed} onClick={save}><Save size={17}/>{busy?'保存中…':'保存班级'}</button></div></div>
  </fieldset></div>}
 </section>;
}

function StudentLine({student:s,dict,existing,onChange,onRemove,notify}:{student:Row;dict:Dict;existing:number[];onChange:(v:Row)=>void;onRemove:()=>void;notify:Notify}){
 const [matches,setMatches]=useState<Row[]>([]),[searching,setSearching]=useState(false);
 useEffect(()=>{let active=true;if(s.student_id||!s.display_name.trim()){setMatches([]);setSearching(false);return}setSearching(true);const timer=setTimeout(()=>api('/students/search?q='+encodeURIComponent(s.display_name)).then(rows=>{if(active)setMatches(rows)}).catch(e=>{if(active)notify(e.message,true)}).finally(()=>{if(active)setSearching(false)}),250);return()=>{active=false;clearTimeout(timer)}},[s.display_name,s.student_id,notify]);
 const patchSlot=(index:number,key:string,value:any)=>onChange({weekly_slots:s.weekly_slots.map((slot:Row,i:number)=>i===index?{...slot,[key]:value}:slot)});
 return <div className="student-line">
  <div className="student-inline"><label>学生姓名<input aria-label="学生姓名" maxLength={80} autoFocus={!s.student_id&&!s.display_name} placeholder="输入姓名，或搜索已有学生" value={s.display_name} readOnly={!!s.student_id} onChange={e=>onChange({display_name:e.target.value})}/></label><label>年级<select aria-label="学生年级" disabled={!!s.student_id} value={s.grade} onChange={e=>onChange({grade:e.target.value})}>{s.grade&&!dict.grade.some(g=>g.name===s.grade)&&<option>{s.grade}</option>}{dict.grade.map(g=><option key={g.id}>{g.name}</option>)}</select></label><div className="inline-slots">{s.weekly_slots.map((slot:Row,i:number)=><div className="inline-slot" key={i}><label>星期<select aria-label="星期" value={slot.weekday} onChange={e=>patchSlot(i,'weekday',Number(e.target.value))}>{weekdays.map((w,j)=><option value={j+1} key={w}>周{w}</option>)}</select></label><label>档位<select aria-label="档位" value={slot.slot_number||''} onChange={e=>patchSlot(i,'slot_number',Number(e.target.value))}>{!slot.slot_number&&<option value="">请选择（原 {slot.slot_label}）</option>}{[1,2,3,4,5,6].map(n=><option key={n} value={n}>第{n}档</option>)}</select></label><label>开始时间<input type="time" aria-label="开始时间" value={slot.start_time||''} onChange={e=>patchSlot(i,'start_time',e.target.value||null)}/></label><label>结束时间<input type="time" aria-label="结束时间" value={slot.end_time||''} onChange={e=>patchSlot(i,'end_time',e.target.value||null)}/></label>{i>0&&<button className="icon-button danger-text" title="移除额外档位" onClick={()=>onChange({weekly_slots:s.weekly_slots.filter((_:Row,j:number)=>j!==i)})}><XIcon/></button>}</div>)}</div><button className="icon-button danger-text remove-student" title="移除学生" onClick={onRemove}><Trash2 size={17}/></button></div>
  {!s.student_id&&s.display_name.trim()&&<div className="inline-search">{searching?<span className="muted">正在查找已有学生…</span>:matches.length?<><span>已有档案，请核对身份后选择：</span>{matches.map(m=><button key={m.id} disabled={existing.includes(m.id)} onClick={()=>{if(confirm(`选择 ${m.display_name} · ${m.grade} · #${m.id}，确定是同一位学生？`))onChange({student_id:m.id,display_name:m.display_name,grade:m.grade})}}>{m.display_name} · {m.grade} · #{m.id}{existing.includes(m.id)?'（已在本班）':' · 使用此档案'}</button>)}<small>若不是同一人，保存时可确认新建独立档案。</small></>:<span className="muted">保存班级时将新建学生档案。</span>}</div>}
  <div className="student-row-extras">{s.student_id&&<span className="muted">学生 #{s.student_id}<button className="text-button" onClick={()=>{if(confirm('重新选择学生？本行的排课和评价将用于新选择的学生。'))onChange({student_id:null,display_name:''})}}>重新选择</button></span>}<details className="student-evaluation"><summary>程度与文字评价 · {s.level}{s.note?' · 已填写评价':''}</summary><div><label>程度<select aria-label="程度" value={s.level} onChange={e=>onChange({level:e.target.value})}>{['A','B','C'].map(v=><option key={v}>{v}</option>)}</select></label><label>文字评价<textarea aria-label="文字评价" maxLength={1000} rows={2} value={s.note} onChange={e=>onChange({note:e.target.value})}/></label></div></details></div>
 </div>;
}
function XIcon(){return <span aria-hidden="true">×</span>}
