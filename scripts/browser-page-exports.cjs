/* Use an isolated database with seed-browser-test.py, never production. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8074';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const p=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  p.on('pageerror',e=>errors.push(e.message));
  await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill('browser-admin');await p.getByLabel('密码',{exact:true}).fill('BrowserTestOnly2026');await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor();
  assert.equal(await p.getByRole('button',{name:/导出/}).count(),0);
  fs.mkdirSync('browser-test-data-export-downloads',{recursive:true});
  for(const [name,view] of [['教师满班率','occupancy'],['教师周课量','workload'],['学生列表','students']]){
   await p.getByRole('button',{name,exact:true}).click();await p.getByLabel('每页显示条数').selectOption('10');
   if(view==='students'){await p.getByLabel('学生排序').selectOption('subjects-desc');await p.locator('.student-detail').first().waitFor()}
   for(const ext of ['xlsx','png']){
    const request=p.waitForRequest(r=>r.url().includes('/api/admin/reports/export.'+ext));
    const download=p.waitForEvent('download');await p.getByRole('button',{name:ext==='xlsx'?'导出明细 XLSX':'导出看板 PNG',exact:true}).click();
    const url=new URL((await request).url()),d=await download;
    assert.equal(url.searchParams.get('view'),view);assert.equal(url.searchParams.get('search_type'),view==='students'?'student':'teacher');
    assert.ok(url.searchParams.get('ordered_ids').split(',').length>10,'All matching records must be exported, not just one page');
    assert.ok(d.suggestedFilename().includes(name));assert.equal(await d.failure(),null);
    await d.saveAs(`browser-test-data-export-downloads/${view}.${ext}`);
    const bytes=fs.readFileSync(`browser-test-data-export-downloads/${view}.${ext}`);assert.equal(ext==='xlsx'?bytes.subarray(0,2).toString():bytes.subarray(1,4).toString(),ext==='xlsx'?'PK':'PNG');
   }
  }
  // Selected subject/search/history filters travel with the page-specific export.
  await p.getByLabel('搜索',{exact:true}).fill('重名演示学生');await p.getByLabel('科目',{exact:true}).selectOption({index:1});
  const historical=await p.getByLabel('统计范围',{exact:true}).locator('option').count();if(historical>1)await p.getByLabel('统计范围',{exact:true}).selectOption({index:1});
  const request=p.waitForRequest(r=>r.url().includes('/api/admin/reports/export.xlsx')),download=p.waitForEvent('download');await p.getByRole('button',{name:'导出明细 XLSX',exact:true}).click();
  const url=new URL((await request).url());assert.equal(url.searchParams.get('q'),'重名演示学生');assert.ok(url.searchParams.get('subject_id'));if(historical>1)assert.ok(url.searchParams.get('broadcast_id'));assert.equal(await(await download).failure(),null);
  assert.deepEqual(errors,[]);console.log('PASS: no overview exports, matching page type and filenames, all filtered rows beyond pagination, student ordering, filters/history parameters and real XLSX/PNG downloads.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
