import {useRef,useState} from 'react';
import {api,setCsrf} from './api';
import './adminPassword.css';

export function AdminPasswordSettings(){
 const [current,setCurrent]=useState(''),[password,setPassword]=useState(''),[repeat,setRepeat]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const saving=useRef(false);
 const submit=async(event:React.FormEvent)=>{
  event.preventDefault();if(saving.current)return;setError('');
  if(password!==repeat){setError('两次新密码不一致，请重新核对。');return}
  if(password.length<14||password.length>256||!/[\p{L}]/u.test(password)||!/[\p{N}]/u.test(password)){setError('新密码须14至256位，包含字母和数字。');return}
  saving.current=true;setBusy(true);
  try{
   await api('/admin/change-password','POST',{current_password:current,new_password:password});
   setCurrent('');setPassword('');setRepeat('');setCsrf('');
   window.dispatchEvent(new CustomEvent('session-expired',{detail:{message:'主管密码已修改，请使用新密码重新登录',error:false}}));
  }catch(error){setError((error as Error).message)}finally{saving.current=false;setBusy(false)}
 };
 return <section className="panel admin-password-settings" aria-labelledby="admin-password-title">
  <h2 id="admin-password-title">修改教学主管密码</h2>
  <p className="help">修改当前登录账号的密码。新密码须14至256位，包含字母和数字；修改后本账号所有设备都需重新登录。</p>
  <form onSubmit={submit}><fieldset disabled={busy}><div className="admin-password-fields">
   <label>原密码<input aria-label="主管原密码" type="password" autoComplete="current-password" required maxLength={256} value={current} onChange={e=>setCurrent(e.target.value)}/></label>
   <label>新密码<input aria-label="主管新密码" type="password" autoComplete="new-password" required minLength={14} maxLength={256} value={password} onChange={e=>setPassword(e.target.value)}/></label>
   <label>再次输入新密码<input aria-label="再次输入主管新密码" type="password" autoComplete="new-password" required minLength={14} maxLength={256} value={repeat} onChange={e=>setRepeat(e.target.value)}/></label>
  </div>{error&&<p className="error-box" role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?'正在修改…':'修改密码并重新登录'}</button></fieldset></form>
  <p className="help">忘记原密码时，请在校区主机上双击“重置主管密码.bat”，按提示设置新密码。</p>
 </section>;
}
