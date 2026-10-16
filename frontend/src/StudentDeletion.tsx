import {useCallback,useEffect,useState} from 'react';
import {api} from './api';

type Preview={student:{id:number;display_name:string;grade:string};classes:{id:number;display_name:string;teacher:string;subject:string}[];token:string};
export function StudentDeletion({id,onClose,onDeleted}:{id:number;onClose:()=>void;onDeleted:()=>void}){
 const [preview,setPreview]=useState<Preview|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{setLoading(true);setPreview(null);setError('');try{setPreview(await api(`/admin/students/${id}/deletion-preview`))}catch(e){setError((e as Error).message)}finally{setLoading(false)}},[id]);
 useEffect(()=>{load()},[load]);
 const remove=async()=>{if(!preview||busy)return;setBusy(true);setError('');try{await api(`/admin/students/${id}?confirmed=true&token=${preview.token}`,'DELETE');onDeleted()}catch(e){setPreview(null);setError((e as Error).message)}finally{setBusy(false)}};
 return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-label="删除学生档案"><div className="section-title"><h2>删除学生档案</h2><button disabled={busy} onClick={onClose}>关闭</button></div>{loading&&<p>正在核对学生和关联班级…</p>}{error&&<div className="error-box" role="alert">{error}<button disabled={busy} onClick={load}>重新核对</button></div>}{preview&&<><h3>{preview.student.display_name} · #{preview.student.id}</h3><p className="help">{preview.student.grade}</p><p>删除后将移除此学生的当前档案，以及所有班级中的关联、档位和评价。班级保留，历史广播快照和冻结记录保持不变。</p><h3>受影响班级 · {preview.classes.length}个</h3>{preview.classes.length?<ul className="deletion-classes">{preview.classes.map(c=><li key={c.id}>{c.teacher} · {c.subject} · {c.display_name}（班级 #{c.id}）</li>)}</ul>:<p className="help">该学生尚未关联班级。</p>}<p className="notice warning">请确认是输错或无需保留的学生。删除不能直接撤销，操作会记录到审计日志。</p></>}<button className="danger-text full" disabled={!preview||loading||busy} onClick={remove}>{busy?'正在删除…':`确认删除学生 #${id}`}</button></section></div>;
}
