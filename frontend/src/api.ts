import {apiErrorMessage} from './apiErrors';
let csrf='';
export function setCsrf(value:string){csrf=value}
export async function api(path:string,method='GET',body?:unknown,options:{quietUnauthorized?:boolean}={}){
  const response=await fetch('/api'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json',...(method==='GET'?{}:{'X-CSRF-Token':csrf})},body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok){const data=await response.json().catch(()=>({detail:'服务连接失败'})); if(response.status===401 && path!='/auth/login' && !options.quietUnauthorized) window.dispatchEvent(new Event('session-expired')); throw new Error(apiErrorMessage(data.detail));}
  return response.json();
}
export async function download(path:string,name:string){const r=await fetch('/api'+path);if(!r.ok){const e=await r.json();throw new Error(e.detail)}saveBlob(await r.blob(),name)}
export function saveBlob(blob:Blob,name:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
export const date=(v:string|null)=>v?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'medium',timeStyle:'short',hour12:false}).format(new Date(v)):'—';
export const rate=(v:number|null)=>v===null?'—':(v*100).toFixed(2)+'%';
export const weekdays=['一','二','三','四','五','六','日'];
