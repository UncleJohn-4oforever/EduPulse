# 架构与统计口径

## 单主机结构

浏览器 → 同源 FastAPI（生产React静态资源 + JSON REST + WebSocket）→ SQLAlchemy → SQLite。默认一个进程，可处理多个浏览器；不用云服务器、CDN、付费API或外部推送服务。Vite只用于开发和构建。

## 核心数据关系

- dictionaries 使用 kind 区分campus/subject/grade；接口校验关联对象类型。
- users 保存角色、校区、Argon2id哈希和session_version；sessions只存令牌哈希、用户ID、版本、CSRF、过期时间。
- classes → users，classes → dictionaries；weekly_slots → classes。
- students 为全局稳定主键，enrollments 唯一(student_id,class_id)，student_evaluations 唯一enrollment_id。评价归属于具体班级关联。
- broadcasts、broadcast_targets固定目标；targets的confirmed_at是每任务每教师唯一当前确认。每次确认的审计保留历次操作，而不是额外创建重复当前确认。
- broadcast_snapshots 保存结束时不可变JSON，含汇总、班级、学生评价、教师及目标名单。所有历史导出读取JSON，而非重新连接当前表。
- audit_logs 记录操作者、动作、对象、时间及少量关联元数据，不记录密码及文字评价。
- schema_versions 记录创建版本。所有FK启用，容量、星期、程度标签有数据库约束；请求字段另有Pydantic验证。

## 统计公式

满班率 = 班内学生关联数 / 容量。教师各班型满班率 = 该班型全部席位 / 全部容量。小班综合 = (一对三席位 + 一对六席位)/(一对三容量 + 一对六容量)。没有分母时返回null；不平均百分比，不把一对一计入小班。

周负荷 = 班级固定时段记录条数之和，按容量分组。班名不参与计算，学生人数不倍增课次。

学生报科数 = 其当前关联班级 subject_id 的集合大小；展示每一条班级评价，以便同科多个班可追溯。席位与去重学生人数是不同指标。

筛选科目时在班级级别重算各教师统计；不会把未筛选科目的容量混入。所有报表和导出共用同一统计函数。当前报表不填写硬编码假数。

## 写入一致性

SQLite BEGIN IMMEDIATE串行化写事务。取得锁后复查当前会话，先冻结过期广播，再执行业务更新。班级version必须与当前版本相同；重复学生、超容量、不存在关联、无时段和无权限均拒绝。保存班级、时段、评价在同一事务中完成。

快照在全部确认/截止/主管结束时固定。过期后台15秒核验，任意写操作前也核验，重启后补核验；无写入时短暂延迟不会导致数据漂移。所有时间用UTC ISO字符串（输入统一转UTC），展示换算北京时间。

## 接口组织

提供 /api/auth、/api/dictionaries、/api/admin/teachers、/api/students/search、/api/students、/api/teacher/classes、/api/broadcasts、/api/admin/broadcasts、/api/admin/reports、/api/admin/students/merge、/api/admin/audit 和 /ws/events。

与规格建议的拆分时段/学生/评价接口不同，本项目使用整班原子保存：POST/PATCH /api/teacher/classes 包含 weekly_slots 和 students（student_id/level/note），减少手机端多次提交和部分保存的不一致。所有数组完整验证，编辑时携带version。后端仍独立存储规范化时段、关联和评价表。

/api/admin/reports 返回完整汇总；/occupancy、/workload、/students 返回专项数据；/export.png 与 /export.xlsx 使用相同筛选及broadcast_id。实际部署可访问 /openapi.json 查看OpenAPI定义；业务接口本身仍须登录。默认Swagger界面使用CDN，在严格CSP/离线环境不作为可用入口。

## 第一版容量与限制

报表以校区轻量级使用为目标，在一个请求中加载必要关联并聚合，未为数万班级的大规模场景做性能承诺；更多学校/高并发需另行做数据库、分页查询、队列及跨进程WS扩展。内存IP限速和WS连接仅属于单进程；生产入口固定workers=1。

## schema v2与一致读取

学生和班级主键显式启用SQLite AUTOINCREMENT，删除/合并后不复用编号。旧库通过migrations.py备份后原子重建这两张表，保持原ID、约束、索引与关联，并使用快照/审计中的历史编号提高序列。普通报告显式BEGIN读取事务，所有SQL查询使用同一个WAL版本；导出前释放读事务再记录导出审计，避免读锁升级冲突。恢复工具校验完整表/字段与外键，恢复时清空会话。

## 1.2版本：学生归属时段与删除

新增student_weekly_slots → enrollments，时段按学生在具体科目/班级的报名关联保存，包含weekday、slot_number(1..6)、slot_label、选填start_time/end_time。每位学生至少一条；同一学生不能重复同星期同档。同班同档填写了具体时间时须一致。班级weekly_slots响应是学生时段的并集，只用于展示/统计；班级保存请求中不再接收顶层weekly_slots。空班没有学生时段，周负荷0。不同班不去重，不做自动排课冲突检查。

users.deleted_at用于保留教师审计/广播身份，删除同时清理其当前班级，撤销哈希和会话，从当前名单/统计移除。dictionaries.deleted_at隐藏新记录选项但保留旧引用，允许已有班级沿用旧类别。重复新增已删除的同名类别恢复原ID。广播的目标名单不会因删除教师改变，名单标注已删除。

数据库目前schema v4；v2升级备份后添加删除字段，并把原班级weekly_slots复制到每条学生enrollment。只解析明确六档名称，无法明确映射的名称保留slot_number=NULL，页面要求人工确认，历史JSON不改写。恢复工具按备份版本检查表/字段，继续支持v1/v2备份；恢复旧版后启动时依次迁移。

## schema v4：班级命名来源

classes.name_is_manual区分手动与自动班名。自动名称按第一位学生的第一个档位计算并保存；旧名称保守视为手动，不猜测改写，教师可在界面恢复自动命名。显式v3→v4迁移先备份，事务内添加默认true的列并检查外键，历史快照不改写。恢复工具保留旧备份兼容。详见BUG_FIXES_2026-10-15.md。
