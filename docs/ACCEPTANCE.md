# EduPulse 1.1 开发与验收报告

验证日期：2026-10-14。代码未上传GitHub；交付形式为可下载ZIP，包含源码和预构建界面。本文记录初始交付验收，之前的独立检查见 [BUG_REVIEW.md](BUG_REVIEW.md)，目前新增功能和升级结果见 [RELEASE_1.2.md](RELEASE_1.2.md)。

## 阶段完成记录

| 阶段 | 已完成 | 验证与运行方式 | 下一步/限制 |
|---|---|---|---|
| 1 骨架与账号 | 空目录建立React/TS/Vite/Tailwind、FastAPI/SQLAlchemy/SQLite；数据库v1、强哈希、教师账号与一次性随机密码 | init-db成功；最终自动测试覆盖独立账号、管理员权限、匿名拒绝、同名账号、重置与停用失效 | 无默认主管密码；初始化命令在主机交互运行 |
| 2 教师填写 | 两列字段、独立学生卡片、A/B/C、备注、结构化周时段、搜索新建移除、容量与版本保护 | API验收及浏览器真实填写/保存/刷新通过；预览入口 / | 保留学生档案；移除/删除需明确确认；无自动排课 |
| 3 管理统计 | 加权满班率、周负荷、学生去重与多教师评价、筛选排序分页、展开明细 | 6/9、6/12、12/21、无班N/A、六人班4生2时段只算2课次等断言通过 | 轻量校区单进程；未做大规模压力承诺 |
| 4 广播快照 | 目标冻结、开始/截止、WS实时提醒、轮询补查、再次确认、固定快照 | API及真实浏览器2位教师2/2确认通过；截止后编辑不改变旧快照 | 在线网页才实时收到；离线截止前登录可补看 |
| 5 导出部署 | 中文PNG、6 Sheet XLSX、Windows安装/启动、SQLite一致备份恢复、手册 | 生产构建通过；PNG/XLSX真实下载；备份/恢复完整性通过；31个Windows wheels依赖闭包验证 | 实际执行环境为Linux，Windows批处理及目标Windows机器未实机运行 |

测试在核心闭环实现后集中执行，并在浏览器验证发现问题后修正和重跑；不将分阶段工作列表误写成每阶段独立测试运行记录。

## 最终自动测试

命令：`cd backend && ../.venv/bin/python -m pytest -q`

结果：**11 passed, 1 warning，12.76秒**。警告为Starlette TestClient对AnyIO旧别名的弃用提示，不影响执行；生产入口不使用TestClient。

11组验收覆盖：

1. 教师独立随机密码、同名唯一账号、归属隔离、获取/修改/删除他人班级拒绝、管理员接口拒绝、匿名拒绝、请求teacher_id拒绝、重置旧密码/会话失效、停用立即失效、无明文持久化。
2. 一对三66.67%、一对六50%、小班57.14%、一对一独立、无班N/A、学生两科及同科多个班去重、同名不同ID、最少身份搜索。
3. 六人班4生2时段仅计2课次，加一个一对一每周1次共3次；改班名不改负荷；评价持久化；旧版本冲突；超容量及重复学生拒绝。
4. 保存不等于确认、2/3进度、再次确认、离线重登补看、目标人数固定、完成快照、后续修改及下一轮不会漂移、中文XLSX结构/百分比类型、PNG尺寸、数据库连接重启后仍在。
5. 过期确认拒绝，未确认快照明确标注。
6. CSRF、非同源拒绝、WS鉴权和实时事件、no-store、登录失败限速。
7. 主管手动结束、学生人工合并与去重。
8. 截止后第一笔数据写入前冻结，历史人数不被后来修改覆盖。
9. 删除明确确认、删除审计、历史评价仍可读取。
10. SQLite Backup API备份、完整性检查、恢复，Excel文本不作为公式执行。
11. 教师姓名筛选仍保留其学生统计，学生姓名搜索独立于教师名搜索。

## 前端构建

命令：`cd frontend && npm run build`

TypeScript检查通过，Vite生产构建通过。1579个模块；最终生产JS约245.49 kB（gzip 76.46 kB），CSS约24.57 kB（gzip 6.41 kB）。不需要前端开发服务器即可使用随包生产页面。

## 真实浏览器验收

Chromium / Playwright验证结果：**PASS**，无pageerror。

主管界面新增张/李两位虚构教师，生成并读取当次凭据；两位教师分别登录。张老师通过表单新建高一数学六人班、添加3位虚构学生、选择ABC并填备注，保存、刷新验证；李老师建立英语三人班，从搜索中选择同一稳定学生ID并填写英语评价。主管发起广播，两个在线窗口实时显示提醒，两位无变化确认，主管看到2/2。真实统计为数学50%、英语33.33%、综合4/9=44.44%，共享学生2科。PNG/XLSX下载成功；390px手机视口无页面横向溢出；退出、后退和重新打开地址均不会显示原教师敏感内容。

运行脚本：`scripts/browser-smoke.cjs`。浏览器测试**只使用隔离数据目录**；不在正式数据库上执行。随包不包含测试数据库、教师凭据或Chromium依赖目录。

复现方法（Linux开发环境，测试密码只用于以下隔离库）：

```bash
npm install --prefix browser-tools playwright@1.51.1
./browser-tools/node_modules/.bin/playwright install chromium
EDUPULSE_DATA_DIR=/tmp/edupulse-test-empty .venv/bin/python scripts/seed-browser-test.py
EDUPULSE_DATA_DIR=/tmp/edupulse-test-empty EDUPULSE_PORT=8017 .venv/bin/python run.py start
# 另一终端，在项目根目录：
node scripts/browser-smoke.cjs
```

脚本拒绝覆盖已有数据库。重复测试请用新的空目录。可用 EDUPULSE_TEST_URL 指向测试地址；不要用公开测试密码初始化正式账号。

## 离线包检查

命令：`.venv/bin/python scripts/verify-wheels.py`

结果：**31个Windows Python3.12 x64 wheels，依赖闭包和每个wheel ZIP完整性通过**；包括WebSocket驱动wsproto、Windows测试所需colorama和Windows时区所需tzdata。所有Python依赖锁定在 requirements.lock.txt。

发布ZIP由 scripts/package.py生成，含每个文件SHA256清单和整体SHA256；排除.env、运行数据库、备份、开发虚拟环境、node_modules、测试运行目录及密钥。压缩包再次解压并做文件哈希校验。

## 界面示例

以下截图来自实际运行系统中的**明确虚构验收数据**，不是预置业务数据；正式首次启动为空数据库。

- [主管概览](screenshots/admin-overview.png)
- [教师电脑表单](screenshots/teacher-desktop.png)
- [教师手机表单](screenshots/teacher-mobile.png)
- [实际PNG导出](screenshots/report-export.png)

## 已知限制

- Python解释器不随包提供；Windows需Python3.12 x64及Python Launcher。Windows批处理已检查路径/失败分支/CRLF，但未在Windows实机执行，实际防火墙与局域网访问须在校区验收。
- 默认受控局域网HTTP不加密传输；提供HTTPS配置，未配置或测试实际校区证书。跨公网部署不在本版范围。
- 使用单进程SQLite；未对多人真实手机、网络断电、大规模并发做现场压力测试。
- 备份一致性与恢复已自动验证；Windows任务计划程序需主机用户自行配置。
- 当前修复版包含schema v1→v2显式迁移；升级必须停止旧服务，详细步骤和迁移验证见BUG_REVIEW.md。
- 教师不能在本版修改自己的密码，主管不能在界面代填/调配班级；教师名单粘贴导入，凭据输出CSV。详细设计假设见README。
