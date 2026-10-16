import {useCallback,useEffect,useState} from 'react';
import {api} from './api';

type Student={id:number;display_name:string;grade:string;campus_id:number;details:{class_id:number;class_name:string;teacher:string;subject:string;campus:string}[]};
export function duplicateGroups(students:Student[]){
 const groups=new Map<string,Student[]>();
 for(const s of students){const name=s.display_name.trim();if(name)groups.set(name,[...(groups.get(name)||[]),s])}
 return [...groups.entries()].filter(([,rows])=>rows.length>1);
}
export function DuplicateStudents({revision,onMerged,campusName}:{revision:number;onMerged:()=>void;campusName:(id:number)=>string}){
 const [students,setStudents]=useState<Student[]>([]),[error,setError]=useState(''),[loading,setLoading]=useState(true),[pair,setPair]=useState<Student[]|null>(null),[source,setSource]=useState(''),[target,setTarget]=useState(''),[busy,setBusy]=useState(false);
 const load=useCallback(()=>{setLoading(true);return api('/admin/reports?search_type=student').then(data=>{setStudents(data.students);setError('')}).catch(e=>setError(e.message)).finally(()=>setLoading(false))},[]);
 useEffect(()=>{load()},[load,revision]);
 const groups=duplicateGroups(students),from=pair?.find(s=>String(s.id)===source),to=pair?.find(s=>String(s.id)===target);
 const shared=from&&to?from.details.filter(d=>to.details.some(t=>t.class_id===d.class_id)):[];
 const merge=async()=>{
  if(!from||!to||source===target||shared.length)return;
  if(!confirm(`确认是同一位学生，将 ${from.display_name} #${source} 合并到 #${target}？保留 #${target} 的姓名、年级和校区，转移班级、档位和评价。此操作不可直接撤销，历史快照保持原样。`))return;
  setBusy(true);setError('');
  try{await api('/admin/students/merge','POST',{source_id:from.id,target_id:to.id});setPair(null);await load();onMerged()}catch(e){setError((e as Error).message)}finally{setBusy(false)}
 };
 const profile=(s:Student)=><div className="merge-profile"><strong>{s.display_name} · #{s.id}</strong><p>{s.grade} · {campusName(s.campus_id)}</p>{s.details.length?s.details.map((d,i)=><p key={i}>{d.teacher} · {d.subject} · {d.class_name}（班级 #{d.class_id}）</p>):<p>尚未关联班级</p>}</div>;
 return <section className="panel duplicate-students"><h2>重名学生核对 <span className="count">{groups.length} 组</span></h2><p className="help">检查全部当前学生档案，不受下方筛选和分页影响。同名可能是不同学生，请核对编号、年级、校区和任课教师后再合并。</p>{loading&&<p role="status">正在核对重名档案…</p>}{error&&<div className="error-box" role="alert">{error}<button disabled={busy} onClick={load}>重新读取</button></div>}{!loading&&!error&&!groups.length&&<p>暂无重名学生。</p>}{groups.length>0&&<details><summary>查看 {groups.length} 组重名学生</summary>{groups.map(([name,rows])=><div className="duplicate-group" key={name}><div><strong>{name}</strong><p>{rows.map(s=>`#${s.id} · ${s.grade} · ${campusName(s.campus_id)}`).join('；')}</p></div><button onClick={()=>{setPair(rows);setTarget(String(rows[0].id));setSource(String(rows[1].id));setError('')}}>核对并合并</button></div>)}</details>}{pair&&<div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-label="核对并合并重名学生"><div className="section-title"><h2>核对并合并重名学生</h2><button disabled={busy} onClick={()=>setPair(null)}>关闭</button></div><div className="form-grid"><label>待合并编号<select value={source} disabled={busy} onChange={e=>setSource(e.target.value)}>{pair.map(s=><option key={s.id} value={s.id}>{s.display_name} #{s.id}</option>)}</select>{from&&profile(from)}</label><label>保留编号<select value={target} disabled={busy} onChange={e=>setTarget(e.target.value)}>{pair.map(s=><option key={s.id} value={s.id}>{s.display_name} #{s.id}</option>)}</select>{to&&profile(to)}</label></div><p>保留编号的姓名、年级、校区不变；待合并档案的班级、档位和评价转入保留编号。历史快照保持原样。</p>{source===target&&<p className="error-box">请选择两个不同编号。</p>}{shared.length>0&&<p className="error-box">两个档案同时在以下班级，需先在班级中人工处理重复关联后再合并：{shared.map(d=>`${d.class_name} #${d.class_id}`).join('、')}。</p>}{error&&<div className="error-box" role="alert">{error}</div>}<button className="primary full" disabled={busy||source===target||shared.length>0} onClick={merge}>{busy?'正在合并…':'确认身份一致并合并'}</button></section></div>}</section>;
}
