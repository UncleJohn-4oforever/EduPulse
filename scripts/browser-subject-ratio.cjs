/* Read-only verification against an isolated seeded test database. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const b=await chromium.launch({channel:'chrome',headless:true});
 try{
  const p=await b.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await p.goto(process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8075');
  await p.getByLabel('登录账号',{exact:true}).fill('browser-admin');await p.getByLabel('密码',{exact:true}).fill('BrowserTestOnly2026');await p.getByRole('button',{name:'进入工作台'}).click();
  const card=p.locator('.report-secondary .stat-card').filter({hasText:'科目比'});await card.waitFor();
  async function verify(query=''){
   const data=await p.evaluate(async q=>(await fetch('/api/admin/reports'+q)).json(),query);
   const n=data.students.length,total=data.students.reduce((sum,s)=>sum+s.subject_count,0),value=n?(total/n).toFixed(2)+' 科/人':'—';
   await p.waitForFunction(value=>[...document.querySelectorAll('.report-secondary .stat-card')].find(el=>el.textContent.includes('科目比'))?.querySelector('strong').textContent===value,value);
   assert.equal(await card.locator('small').innerText(),`${total} 个学生科目 ÷ ${n} 名学生`);
  }
  await verify();await p.getByLabel('每页显示条数').selectOption('10');await verify();assert.equal(await p.locator('.report-secondary .stat-card').count(),4);
  const ys=await p.locator('.report-secondary .stat-card').evaluateAll(els=>els.map(el=>el.getBoundingClientRect().y));assert.ok(ys.every(y=>y===ys[0]));
  const subject=await p.getByLabel('科目',{exact:true}).locator('option').nth(1).getAttribute('value');await p.getByLabel('科目',{exact:true}).selectOption(subject);await verify('?subject_id='+subject);
  await p.getByLabel('科目',{exact:true}).selectOption('');await p.getByLabel('搜索',{exact:true}).fill('不存在的教师0000');await verify('?q='+encodeURIComponent('不存在的教师0000'));
  await p.getByLabel('搜索',{exact:true}).fill('');await verify();
  if(await p.getByLabel('统计范围',{exact:true}).locator('option').count()>1){const id=await p.getByLabel('统计范围',{exact:true}).locator('option').nth(1).getAttribute('value');await p.getByLabel('统计范围',{exact:true}).selectOption(id);await verify('?broadcast_id='+id)}
  for(const width of [1440,1280,1024,768,390,360]){await p.setViewportSize({width,height:900});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width}`)}
  console.log('PASS: subject totals, zero students, filters, history, pagination independence, four desktop cards and six screen widths.');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
