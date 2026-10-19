import {useCallback,useEffect,useRef,useState} from 'react';
import {api} from './api';
import {ClassEditor} from './TeacherWorkspace';
type Row=Record<string,any>;
export type CourseTarget={teacher:Row;subjectId:number;slot:Row;classId?:number};
export function TimetableCourseEditor({target,dict,notify,onDirty,onSaving,onClose,onSaved,role='admin'}:{target:CourseTarget;dict:any;notify:(text:string,error?:boolean)=>void;onDirty:(v:boolean)=>void;onSaving:(v:boolean)=>void;onClose:()=>void;onSaved:()=>void;role?:'admin'|'teacher'}){
 const [loaded,setLoaded]=useState<Row|null>(null),[error,setError]=useState(''),[retry,setRetry]=useState(0),[busy,setBusy]=useState(false);
 const dirtyRef=useRef(false),busyRef=useRef(false);
 const mark=useCallback((_:string,value:boolean)=>{dirtyRef.current=value;onDirty(value)},[onDirty]);
 const saving=useCallback((_:string,value:boolean)=>{busyRef.current=value;setBusy(value);onSaving(value)},[onSaving]);
 useEffect(()=>()=>{onDirty(false);onSaving(false)},[onDirty,onSaving]);
 useEffect(()=>{let active=true;setError('');setLoaded(null);if(target.classId)api(`/${role}/classes/${target.classId}`).then(row=>{if(active)setLoaded(row)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[target.classId,retry,role]);
 const close=()=>{if(busyRef.current)return;if(dirtyRef.current&&!confirm('放弃本次未保存的课程修改？'))return;onClose()};
 useEffect(()=>{const escape=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.stopPropagation();close()}};document.addEventListener('keydown',escape);return()=>document.removeEventListener('keydown',escape)});
 const owner=loaded?.teacher||target.teacher;
 return <div className="modal-backdrop"><section className={"modal admin-course-modal"+(role==='teacher'?' teacher-course-modal':'')} role="dialog" aria-modal="true" aria-label={target.classId?'编辑课程':'新增课程'}><div className="section-title"><h2>{target.classId?'编辑课程':'新增课程'} · {owner.display_name}</h2><button disabled={busy} onClick={close}>关闭</button></div>{role==='teacher'?<details className="course-editor-help"><summary>保存后同步到主管端 · 操作说明</summary><p>这里编辑整个班级。可添加或移除学生、调整档位与评价；删除班级会移除本班全部档位及学生关联，学生档案与历史记录保留。</p></details>:<p className="help">保存后同步到教师端及主管统计。这里编辑整个班级；删除会移除本班全部档位及学生关联，学生档案与历史记录保留。</p>}
 {error?<div className="error-box" role="alert">读取最新班级失败：{error}<button onClick={()=>setRetry(v=>v+1)}>重试</button></div>:target.classId&&!loaded?<p>正在读取最新班级…</p>:<ClassEditor key={target.classId||'new'} user={owner} dict={dict} initial={loaded} day={target.slot.weekday} adminMode={role==='admin'} timetableMode defaults={{subject_id:target.subjectId}} defaultSlot={target.slot} notify={notify} mark={mark} onSaving={saving} onSaved={onSaved} onDelete={onSaved}/>}
 </section></div>;
}
