import {useEffect,useState} from 'react';

const sizes=[10,20,50,100];
export function usePageSize(){
 const [size,setSize]=useState(()=>{try{const n=Number(localStorage.getItem('edupulse-page-size'));return sizes.includes(n)?n:20}catch{return 20}});
 const change=(n:number)=>{setSize(n);try{localStorage.setItem('edupulse-page-size',String(n))}catch{/* Browsers may disable local storage. */}};
 return [size,change] as const;
}
export function Pager({total,page,setPage,pageSize,setPageSize}:{total:number;page:number;setPage:(n:number)=>void;pageSize:number;setPageSize:(n:number)=>void}){
 const pages=Math.max(1,Math.ceil(total/pageSize));
 useEffect(()=>{if(page>pages)setPage(pages)},[page,pages,setPage]);
 return <div className="pager"><span>共 {total} 条记录</span><label className="page-size">每页显示<select aria-label="每页显示条数" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1)}}>{sizes.map(n=><option key={n} value={n}>{n} 条</option>)}</select></label><div><button disabled={page<=1} onClick={()=>setPage(page-1)}>上一页</button><span>{Math.min(page,pages)} / {pages}</span><button disabled={page>=pages} onClick={()=>setPage(page+1)}>下一页</button></div></div>;
}
