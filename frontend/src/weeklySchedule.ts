type Row=Record<string,any>;
export const standardTimes=[['08:00','10:00'],['10:00','12:00'],['13:00','15:00'],['15:00','17:00'],['17:30','19:30'],['19:30','21:30']];
export type Lesson={key:string;teacher:Row;room:Row;day:number;period:number|null;slots:Row[];members:Row[];conflicts:string[]};
const identity=(s:Row)=>`${s.weekday}:${s.slot_number??s.slot_label??'未知'}`;
const timeKey=(s:Row)=>`${s.start_time||''}/${s.end_time||''}`;
export function lessonsFor(teachers:Row[]):Lesson[]{
 const result:Lesson[]=[];
 for(const teacher of teachers)for(const room of teacher.classes||[]){
  const grouped=new Map<string,Lesson>();
  const add=(slot:Row,member?:Row)=>{
   const id=identity(slot);let lesson=grouped.get(id);
   if(!lesson){lesson={key:`${teacher.id}:${room.id}:${id}`,teacher,room,day:slot.weekday,period:slot.slot_number>=1&&slot.slot_number<=6?slot.slot_number:null,slots:[],members:[],conflicts:[]};grouped.set(id,lesson)}
   if(!lesson.slots.some(s=>timeKey(s)===timeKey(slot)))lesson.slots.push(slot);
   if(member&&!lesson.members.some(m=>m.student_id===member.student_id))lesson.members.push(member);
  };
  // Student slots are the source of truth; old snapshots may only have class slots.
  const hasStudentSlots=(room.students||[]).some((m:Row)=>(m.weekly_slots||[]).length);
  if(hasStudentSlots)for(const member of room.students)for(const slot of member.weekly_slots||[])add(slot,member);
  else for(const slot of room.weekly_slots||[]){add(slot);for(const member of room.students||[])add(slot,member)}
  result.push(...grouped.values());
 }
 return result;
}
function overlaps(a:Row,b:Row){
 if(a.weekday!==b.weekday)return false;
 if(a.start_time&&a.end_time&&b.start_time&&b.end_time)return a.start_time<b.end_time&&b.start_time<a.end_time;
 return a.slot_number!=null&&a.slot_number===b.slot_number;
}
export function withConflicts(lessons:Lesson[],warnings:Row[]=[]){
 const result=lessons.map(l=>({...l,conflicts:[] as string[]}));
 const flag=(l:Lesson,text:string)=>{if(!l.conflicts.includes(text))l.conflicts.push(text)};
 for(let i=0;i<result.length;i++)for(let j=i+1;j<result.length;j++){
  const a=result[i],b=result[j];if(a.room.id===b.room.id||a.day!==b.day)continue;
  const teacherConflict=a.teacher.id===b.teacher.id&&(a.period!==null&&a.period===b.period||a.slots.some(sa=>b.slots.some(sb=>overlaps(sa,sb))));
  if(teacherConflict){flag(a,`教师排课冲突：${b.room.display_name}`);flag(b,`教师排课冲突：${a.room.display_name}`)}
  for(const member of a.members){
   const other=b.members.find(m=>m.student_id===member.student_id);if(!other)continue;
   const slots=(m:Row,l:Lesson)=>(m.weekly_slots||[]).filter((s:Row)=>identity(s)===identity(l.slots[0]));
   const aa=slots(member,a),bb=slots(other,b);
   if((aa.length?aa:a.slots).some((sa:Row)=>(bb.length?bb:b.slots).some((sb:Row)=>overlaps(sa,sb)))){
    flag(a,`学生${member.display_name}排课冲突`);flag(b,`学生${member.display_name}排课冲突`);
   }
  }
 }
 // Current advisories also include conflicts with classes outside the selected scope.
 for(const l of result)for(const w of warnings)if(w.weekday===l.day&&(w.classes||[]).some((c:Row)=>c.id===l.room.id&&l.slots.some(s=>identity(s)===identity(c)))){
  if(w.scope==='student')flag(l,`学生${w.student_name}排课冲突`);
  else if(!l.conflicts.some(t=>t.startsWith('教师排课冲突')))flag(l,'教师排课冲突');
 }
 return result;
}
