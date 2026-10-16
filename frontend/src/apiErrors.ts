const labels:Record<string,string>={display_name:'名称',name_is_manual:'自动命名标记',subject_id:'科目',grade:'年级',capacity:'班型容量',students:'学生',student_id:'学生编号',weekly_slots:'上课档位',weekday:'星期',slot_number:'档位',start_time:'开始时间',end_time:'结束时间',level:'程度',note:'评价',version:'数据版本',teacher_id:'任课老师'};

export function apiErrorMessage(detail:unknown){
 if(typeof detail==='string')return detail;
 if(!Array.isArray(detail))return '服务返回异常，请稍后重试';
 const errors=detail.filter(e=>e&&typeof e==='object').map(e=>({...e,loc:Array.isArray(e.loc)?e.loc:[]})) as {type?:string;msg?:string;loc?:Array<string|number>}[];
 if(!errors.length)return '服务返回异常，请稍后重试';
 if(errors.some(e=>e.type==='extra_forbidden'&&e.loc?.includes('name_is_manual'))){
  return '主机仍在运行旧版服务，暂不支持新版班级保存。请联系主管重启主机服务后重试，当前填写内容会保留。';
 }
 return '字段校验失败：'+errors.map(e=>{
  const field=(e.loc||[]).filter(k=>k!=='body').map(k=>typeof k==='number'?`第${k+1}项`:(labels[k]||k)).join(' / ');
  const message=e.type==='extra_forbidden'?'当前服务不支持此字段，请刷新页面；仍失败时请联系主管重启服务':e.type==='missing'?'此项未填写':e.msg||'内容无效';
  return `${field?field+'：':''}${message}`;
 }).join('；');
}
