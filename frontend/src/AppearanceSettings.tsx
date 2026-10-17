import {Check,Shield,Sun} from 'lucide-react';
import './appearance.css';

export type AdminTheme='warcraft'|'classic';
export function readAdminTheme():AdminTheme{
 try{return localStorage.getItem('edupulse-admin-theme')==='classic'?'classic':'warcraft'}catch{return 'warcraft'}
}

export function AppearanceSettings({value,onChange}:{value:AdminTheme;onChange:(theme:AdminTheme)=>void}){
 return <section className="panel appearance-settings" aria-labelledby="appearance-title">
  <div className="section-title"><div><h2 id="appearance-title">界面风格</h2><p className="help">选择即刻生效，可随时切换。记住当前浏览器的选择。</p></div></div>
  <fieldset className="theme-options"><legend className="sr-only">选择主管工作台风格</legend>{[
   {id:'warcraft' as const,title:'魔兽 · 史诗',description:'深色石板、青铜雕饰与鎏金数字',Icon:Shield},
   {id:'classic' as const,title:'经典 · 清爽',description:'浅色底板与青绿色，适合明亮环境',Icon:Sun}
  ].map(({id,title,description,Icon})=><label className={'theme-choice'+(value===id?' selected':'')} key={id}>
   <input type="radio" name="admin-theme" value={id} checked={value===id} onChange={()=>onChange(id)}/>
   <span className={'theme-preview preview-'+id} aria-hidden="true"><span className="preview-nav"><i/><i/><i/><i/></span><span className="preview-content"><span className="preview-bar"/><span className="preview-metrics"><i>85.0<small>%</small></i><i>1.86<small>科/人</small></i><i>128<small>人</small></i></span><span className="preview-table"><i/><i/><i/></span></span></span>
   <span className="theme-choice-title"><Icon size={19}/><strong>{title}</strong>{value===id&&<span className="theme-selected"><Check size={14}/>当前风格</span>}</span>
   <span className="theme-description">{description}</span>
  </label>)}</fieldset>
 </section>;
}
