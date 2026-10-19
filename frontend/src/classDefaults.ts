type Slot = {weekday:number;slot_number?:number|null;start_time?:string|null;end_time?:string|null};
export function sharedClassSlot(students:{weekly_slots?:Slot[]}[],fallback:Slot={weekday:3,slot_number:3,start_time:null,end_time:null}) {
  const slots=students.flatMap(s=>s.weekly_slots||[]);
  const slot=slots.find(s=>s.start_time&&s.end_time)||slots[0]||fallback;
  return {weekday:slot.weekday,slot_number:slot.slot_number??null,start_time:slot.start_time||null,end_time:slot.end_time||null};
}
const subjects = new Map<string,number>();
const subjectKey = (user:{id:number;username:string}) => `edupulse:last-subject:${user.id}:${user.username}`;

export function rememberedSubject(user:{id:number;username:string}, available:{id:number}[]) {
  const key=subjectKey(user);
  let id=subjects.get(key);
  try { id=Number(localStorage.getItem(key))||id; } catch { /* Keep session defaults when storage is unavailable. */ }
  return available.find(s=>s.id===id)?.id??available[0]?.id;
}
export function rememberSubject(user:{id:number;username:string}, id:number) {
  const key=subjectKey(user);subjects.set(key,id);
  try { localStorage.setItem(key,String(id)); } catch { /* Session memory still works. */ }
}
export function automaticClassName(students:{weekly_slots?:Slot[]}[]) {
  const slot=students[0]?.weekly_slots?.[0];
  return slot?.slot_number?`周${'一二三四五六日'[slot.weekday-1]}${'一二三四五六'[slot.slot_number-1]}档`:'';
}
export function inheritedSlots(students:{weekly_slots?:Slot[]}[]) {
  return structuredClone(students[0]?.weekly_slots?.length?students[0].weekly_slots:[{weekday:3,slot_number:3,start_time:null,end_time:null}]);
}
