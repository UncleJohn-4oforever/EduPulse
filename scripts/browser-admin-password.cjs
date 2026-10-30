// Isolated test server only. Never run against production accounts.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const base='http://127.0.0.1:8077';
  await page.goto(base);await page.getByLabel('登录账号',{exact:true}).fill('browser-admin');await page.getByLabel('密码',{exact:true}).fill('BrowserTestOnly2026');await page.getByRole('button',{name:'进入工作台'}).click();await page.getByRole('button',{name:'设置',exact:true}).click();
  const panel=page.getByRole('region',{name:'修改教学主管密码',exact:true});await panel.waitFor();
  fs.mkdirSync('exports/admin-password-preview',{recursive:true});await page.screenshot({path:'exports/admin-password-preview/desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));await page.screenshot({path:'exports/admin-password-preview/mobile.png',fullPage:true});await page.setViewportSize({width:1440,height:1000});
  const other=await browser.newContext();await other.request.post(base+'/api/auth/login',{data:{username:'browser-admin',password:'BrowserTestOnly2026'}});
  await panel.getByLabel('主管原密码',{exact:true}).fill('wrong-old-password');await panel.getByLabel('主管新密码',{exact:true}).fill('NewBrowserAdminPassword2026');await panel.getByLabel('再次输入主管新密码',{exact:true}).fill('NewBrowserAdminPassword2026');await panel.getByRole('button',{name:'修改密码并重新登录'}).click();await panel.getByRole('alert').filter({hasText:'原密码不正确'}).waitFor();
  await panel.getByLabel('主管原密码',{exact:true}).fill('BrowserTestOnly2026');await panel.getByLabel('再次输入主管新密码',{exact:true}).fill('MismatchPassword2026');await panel.getByRole('button',{name:'修改密码并重新登录'}).click();await panel.getByRole('alert').filter({hasText:'两次新密码不一致'}).waitFor();
  await panel.getByLabel('再次输入主管新密码',{exact:true}).fill('NewBrowserAdminPassword2026');await panel.getByRole('button',{name:'修改密码并重新登录'}).click();await page.getByRole('button',{name:'进入工作台'}).waitFor();
  assert.equal((await other.request.get(base+'/api/auth/me')).status(),401);assert.equal((await other.request.post(base+'/api/auth/login',{data:{username:'browser-admin',password:'BrowserTestOnly2026'}})).status(),401);
  await page.getByLabel('登录账号',{exact:true}).fill('browser-admin');await page.getByLabel('密码',{exact:true}).fill('NewBrowserAdminPassword2026');await page.getByRole('button',{name:'进入工作台'}).click();await page.locator('.sidebar').waitFor();assert.deepEqual(errors,[]);
  await other.close();console.log('PASS: password settings, wrong password, mismatch, forced re-login, old-session revocation, new-password login, desktop/mobile layout.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
