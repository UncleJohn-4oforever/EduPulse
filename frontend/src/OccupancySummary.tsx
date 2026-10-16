import {rate} from './api';

type Group={classes:number;seats:number;capacity:number};
type Teacher={groups:Record<string,Group>};
export function averageClassSize(seats:number,classes:number){return classes?seats/classes:null}
export function classSizeText(seats:number,classes:number){const value=averageClassSize(seats,classes);return value===null?'—':value.toFixed(2)}
export function occupancyTotals(teachers:Teacher[]){
 const sum=(keys:string[])=>teachers.reduce((total,teacher)=>keys.reduce((n,key)=>{
  const g=teacher.groups[key];return {classes:n.classes+g.classes,seats:n.seats+g.seats,capacity:n.capacity+g.capacity};
 },total),{classes:0,seats:0,capacity:0});
 return {three:sum(['3']),six:sum(['6']),combined:sum(['3','6'])};
}

export function OccupancyValue({value,seats,classes}:{value:number|null;seats:number;classes:number}){
 return <div className="occupancy-value"><strong>{rate(value)}</strong><span className="class-size">班容 <b>{classSizeText(seats,classes)}</b>{classes>0&&<span> 人/班</span>}</span></div>;
}

export function OccupancySummary({teachers}:{teachers:Teacher[]}){
 const totals=occupancyTotals(teachers);
 return <section className="occupancy-overview" aria-label="小班满班率与班容">
  <div className="occupancy-heading"><h2>小班满班率与班容</h2><span>综合按容量加权 · 不含一对一</span></div>
  <div className="occupancy-metrics">{[
   {key:'three',label:'一对三满班率',data:totals.three},
   {key:'six',label:'一对六满班率',data:totals.six},
   {key:'combined',label:'综合平均满班率',data:totals.combined}
  ].map(({key,label,data})=><div className={'occupancy-metric '+key} key={key}>
   <h3>{label}</h3><OccupancyValue value={data.capacity?data.seats/data.capacity:null} seats={data.seats} classes={data.classes}/>
   <p>{data.seats} 席位 / {data.capacity} 总容量 · {data.classes} 个班</p>
  </div>)}</div>
  <div className="occupancy-explanation">班容 = 学生席位 ÷ 班级数，表示平均每班人数；空班计入，没有对应班型时显示“—”。</div>
 </section>;
}
