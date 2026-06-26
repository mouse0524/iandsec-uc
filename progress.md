## 2026-06-26 - Task: 工单产研流转最小化设计

### What was done

- 结合现有工单流程，明确采用轻量内部产研任务替换 Redmine。
- 保留现有工单主状态，把产品、研发、测试迁入新增产研任务池。
- 明确第一版边界：只做工单转产研、任务关联、产研状态流转、任务详情和历史 Redmine 只读展示。

### Testing

- 只新增设计文档，未修改业务代码。
- 已进行人工核对：设计覆盖当前工单状态、技术处理页 Redmine 入口、工单详情展示和后续验证标准。

### Notes

- `docs/plans/2026-06-26-ticket-rd-workflow-design.md`：新增工单产研流转最小化设计文档。
- `progress.md`：追加本轮设计交付记录。
- 回滚方式：删除 `docs/plans/2026-06-26-ticket-rd-workflow-design.md`，并移除 `progress.md` 中本轮 `2026-06-26 - Task: 工单产研流转最小化设计` 记录。

## 2026-06-26 - Task: 轻量产研任务替换 Redmine 入口

### What was done

- 新增产研任务类型、状态、任务表、工单关联表和任务日志表，支持工单转产研、关联工单、产研状态流转。
- 新增产研任务后端接口和权限初始化，把产研任务菜单挂入工单中心，并为技术、产品、研发、测试、客服、管理员配置对应入口。
- 技术处理页新增“转产研任务”入口，历史 Redmine 信息保留为只读展示。
- 新增产研任务列表/详情页，支持按类型、状态、关键词筛选和任务流转。
- 工单详情新增关联产研任务展示，产研完成后只提示关联工单继续现场闭环，不自动关闭工单。

### Testing

- `python -m compileall app`
- `python -m pytest tests/test_rd_task_workflow.py`
- `python -m pytest tests/test_rd_task_workflow.py tests/test_redmine_ticket_workflow.py tests/test_redmine_metadata.py`
- `cd web && pnpm.cmd run build`
- `git diff --check`：通过，仅输出 Git 换行转换提示。

### Notes

- `app/models/enums.py`：新增产研任务类型和状态枚举。
- `app/models/admin.py`：新增产研任务、产研任务与工单关联、产研任务日志模型。
- `app/controllers/rd_task.py`：新增产研任务创建、关联、流转、列表和详情控制器。
- `app/schemas/rd_tasks.py`：新增产研任务接口入参 schema。
- `app/api/v1/rd_tasks/`：新增产研任务 API 路由。
- `app/api/v1/__init__.py`：挂载产研任务路由。
- `app/controllers/ticket.py`：工单详情返回关联产研任务列表。
- `app/core/init_app.py`：初始化产研任务菜单、角色和 API 权限。
- `web/src/api/index.js`：新增产研任务 API 方法。
- `web/src/views/ticket/components/ticket-meta.js`：新增产研任务类型和状态文案。
- `web/src/views/ticket/tech/index.vue`：技术处理页新增转产研任务入口，Redmine 改为历史展示。
- `web/src/views/ticket/components/TicketDetailModal.vue`：工单详情展示关联产研任务。
- `web/src/views/ticket/rd-task/index.vue`：新增产研任务列表和详情页面。
- `tests/test_rd_task_workflow.py`：新增产研任务核心流程测试。
- 回滚方式：回退上述文件改动，并移除本轮 `2026-06-26 - Task: 轻量产研任务替换 Redmine 入口` 记录。

## 2026-06-26 - Task: 修复产研任务流转审查问题

### What was done

- 收紧产研任务流转服务端校验，按当前状态和角色限制可执行动作，避免任意角色跨阶段推进任务。
- 补充产研任务流转回归测试，覆盖非法状态跳转和客服越权流转场景。
- 调整 `.gitignore`，只放行产研任务测试文件，避免测试已写但不会进入提交。

### Testing

- `python -m pytest tests/test_rd_task_workflow.py`：通过。

### Notes

- `app/controllers/rd_task.py`：新增产研任务动作规则表，并在流转时校验角色和当前状态。
- `app/api/v1/rd_tasks/rd_tasks.py`：流转接口把当前用户角色和超管标识传入控制器。
- `tests/test_rd_task_workflow.py`：补充状态跳转和角色越权回归用例。
- `.gitignore`：放行 `tests/test_rd_task_workflow.py`，保证本轮测试文件可提交。
- `progress.md`：追加本轮修复记录。
- 回滚方式：回退上述文件改动，并移除本轮 `2026-06-26 - Task: 修复产研任务流转审查问题` 记录。
