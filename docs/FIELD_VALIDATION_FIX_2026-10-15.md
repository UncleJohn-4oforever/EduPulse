# 教师保存出现 Extra inputs are not permitted 的现场修复

## 定位证据

本轮直接读取正在使用的`http://127.0.0.1:8000/openapi.json`，其`ClassIn`只有`display_name,subject_id,grade,capacity,students,version`，仍要求`grade`，没有新版页面提交的`name_is_manual`。旧Python服务自16:57启动，未随源码和前端构建更新。后端严格拒绝未知字段，因此返回422；旧版英文验证消息被直接展示。

没有通过放宽字段校验、删除自动命名参数或重置数据库解决问题。

## 已实施

- 使用SQLite Backup API在线备份原`EduPulseData/edupulse.sqlite3`并检查完整性和外键，备份位于项目`backups/before-service-update/edupulse-20261015-184645-452487.sqlite3`。
- 核对旧服务进程身份后，在原数据目录重新启动当前版本服务，自动完成v3→v4迁移。账号、学生、班级和会话沿用，生产服务继续监听原8000端口。
- 现场确认健康接口正常，运行中的`ClassIn`已包含`name_is_manual`且不再要求班级年级，教师WebSocket连接已重新建立。
- 新增前端统一错误格式化。遇到旧服务拒绝自动命名字段时，说明主机仍运行旧版、需要主管重启，填写内容保留。其他未知字段与缺失字段显示中文说明和字段位置，异常错误结构也不会触发前端二次异常。

## 验证

- TypeScript和Vite生产构建通过。
- `scripts/test-api-errors.cjs`通过，覆盖旧服务、多层学生字段、必填项和异常错误格式。
- `scripts/browser-version-compat.cjs`在独立虚构数据库验证：模拟旧后端422，中文说明正确、表单和学生信息保留；解除模拟后正常保存，重试不重复创建学生。
- 现场只检查服务契约、健康状态和请求状态，没有向正式数据库插入测试班级或测试学生。新版服务自动迁移已生效，迁移前备份保留。
- 检查更新后的现场访问日志时，已出现3次班级成功写入（HTTP 200），班级写入422为0；这些是实际使用请求，不是测试灌入。

老师可直接重试保存。若页面还显示旧提示，可先复制尚未保存的重要文字，再强制刷新；已保存记录保留。生产服务在隐藏窗口中运行，日志位于`logs/service.stdout.log`和`logs/service.stderr.log`。后续更新后端代码后，必须重启Python服务，刷新浏览器本身不会替换运行中的后端代码。
