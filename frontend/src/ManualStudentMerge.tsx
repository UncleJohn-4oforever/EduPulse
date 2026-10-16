import {useEffect,useState} from 'react';
import {api} from './api';

type Profile={student:{id:number;display_name:string;grade:string;campus_id:number};classes:{id:number;display_name:string;teacher:string;subject:string}[]};
function useStudentIdentity(value:string,retry:number){
 const valid=/^\d+$/.test(value)&&Number.isSafeInteger(Number(value))&&Number(value)>0;
 const key=valid?String(Number(value)):'';
 const [state,setState]=useState<{key:string;profile:Profile|null;error:string}>({key:'',profile:null,error:''});
 useEffect(()=>{
  let active=true;
  setState({key,profile:null,error:''});
  if(!key)return;
  // Reuse the read-only exact-ID identity/association preview; this never deletes.
  const timer=setTimeout(()=>api(`/admin/students/${key}/deletion-preview`).then(profile=>{if(active)setState({key,profile,error:''})}).catch(e=>{if(active)setState({key,profile:null,error:e.message})}),250);
  return()=>{active=false;clearTimeout(timer)};
 },[key,retry]);
 const current=state.key===key;
 return {profile:valid&&current?state.profile:null,error:value&&!valid?'请输入有效的学生编号':current?state.error:'',loading:valid&&(!current||(!state.profile&&!state.error))};
}

export function ManualStudentMerge({onMerged,notify,campusName}:{onMerged:()=>void;notify:(text:string,error?:boolean)=>void;campusName:(id:number)=>string}){
 const [source,setSource]=useState(''),[target,setTarget]=useState(''),[retry,setRetry]=useState(0),[busy,setBusy]=useState(false);
 const from=useStudentIdentity(source,retry),to=useStudentIdentity(target,retry);
 const same=!!from.profile&&!!to.profile&&from.profile.student.id===to.profile.student.id;
 const shared=from.profile?.classes.filter(c=>to.profile?.classes.some(t=>t.id===c.id))||[];
 const ready=!!from.profile&&!!to.profile&&!same&&!shared.length;
 const merge=async(e:React.FormEvent)=>{
  e.preventDefault();if(!ready||busy||!from.profile||!to.profile)return;
  const a=from.profile.student,b=to.profile.student;
  if(!confirm(`确认这两份档案属于同一位学生？\n将 ${a.display_name} #${a.id} 合并到 ${b.display_name} #${b.id}。\n保留 ${b.display_name} 的姓名、年级和校区，转移班级、档位和评价。此操作不可直接撤销，历史快照保持不变。`))return;
  setBusy(true);try{await api('/admin/students/merge','POST',{source_id:a.id,target_id:b.id});setSource('');setTarget('');onMerged();notify('学生档案已合并')}catch(e){notify((e as Error).message,true);setRetry(v=>v+1)}finally{setBusy(false)}
 };
 const preview=(identity:ReturnType<typeof useStudentIdentity>)=><div className="merge-identity" aria-live="polite">{identity.loading?<p>正在查找学生…</p>:identity.error?<div className="error-box" role="alert">{identity.error}<button type="button" disabled={busy} onClick={()=>setRetry(v=>v+1)}>重新查找</button></div>:identity.profile?<div className="merge-profile"><strong>{identity.profile.student.display_name} · #{identity.profile.student.id}</strong><p>{identity.profile.student.grade} · {campusName(identity.profile.student.campus_id)}</p>{identity.profile.classes.length?identity.profile.classes.map(c=><p key={c.id}>{c.teacher} · {c.subject} · {c.display_name}（班级 #{c.id}）</p>):<p>尚未关联班级</p>}</div>:<p className="help">输入编号后，自动显示对应学生信息。</p>}</div>;
 return <section className="panel"><h2>人工合并重复学生</h2><p className="help">输入编号即可查看对应学生。请核对两份档案确为同一人；合并后保留目标档案的姓名、年级和校区。</p><form onSubmit={merge}><div className="manual-merge-field"><label>待合并的学生编号<input type="number" min={1} step={1} required value={source} disabled={busy} onChange={e=>setSource(e.target.value)}/></label>{preview(from)}</div><div className="manual-merge-field"><label>保留的学生编号<input type="number" min={1} step={1} required value={target} disabled={busy} onChange={e=>setTarget(e.target.value)}/></label>{preview(to)}</div>{same&&<p className="error-box">请选择两个不同的学生编号。</p>}{shared.length>0&&<p className="error-box">两个档案同时在以下班级，请先人工处理重复关联：{shared.map(c=>`${c.display_name} #${c.id}`).join('、')}。</p>}<button disabled={busy||!ready} className="danger-text">{busy?'正在合并…':'确认合并档案'}</button></form></section>;
}
