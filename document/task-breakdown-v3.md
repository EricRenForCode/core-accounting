# Core Accounting — 改进与完善任务分解 v3

> **来源**: 基于 `task-breakdown-v2.md`(现状) + `document/engineering-spec.md` v0.2 + 本轮端到端实测结果
> **创建**: 2026-06-28
> **定位**: v2 记录「建了什么 / 修了什么」;**v3 记录「还能改进什么、接下来做什么」**——按优先级排序的收尾与提升路线图。

---

## 0. 现状基线（v2 结束时）

- 核心会计流程端到端跑通：科目→凭证→审核(双人)→记账→账表→报表→冲销,账目勾稽正确。
- 前端 `npm run build` 通过;后端测试 **84 通过 / 5 失败(仅 AI 模块)**。
- 已加:仪表盘、总账/明细账前端、金额「分」录入、闲置 10 分钟自动登出、refresh token 1 天。
- 已修真实 bug:记账崩溃、审核/记账/冲销 MissingGreenlet、审计 date/Decimal、校验 422、AccountPicker 崩溃、利润表两列。
- 代码在分支 `fix/mvp-voucher-reports-dashboard`(未合并 master)。

---

## P0 — 正确性收尾（先清这些，风险最高 / 投入最小）🔴

### P0.1 AI 模块 2 个 Decimal 序列化 bug ✅
- [x] `test_ai_report_interpret`(integration + unit)报 `Object of type Decimal is not JSON serializable`——与已修的 date/audit 同类。
- [x] 定位:`app/ai/report_interpreter.py:43` 的 `json.dumps(report_data.model_dump())`——报表 NUMERIC 字段 `model_dump()` 出来是 `Decimal`。改为 `model_dump(mode="json")`,一次性把 Decimal/date/UUID 转成 JSON 安全值(`voucher_generator.py:176` 的 `parsed` 是 `json.loads` 结果,纯 JSON 类型,无此问题)。
- [x] **不依赖 OPENAI_API_KEY 即可修**:失败发生在调用 LLM 之前的 prompt 构建阶段。
- [x] 结果:后端 **86 通过**(原 84),两条 interpret 测试转绿,无回归。
- 附:修复测试环境依赖缺口——`aiosqlite`(测试内存库)加入 dev extras;`bcrypt` 固定 `==4.0.1`(与 `requirements.txt` 对齐,`pyproject.toml` 原无 pin 被解析到 5.0.0,与 passlib 不兼容)。

### P0.2 refresh token 轮换前后端不一致 ⚠️（会话实际比预期短）✅
- [x] 后端 `/auth/refresh` 会**轮换**(撤销旧 refresh、签发新 access+refresh 对,`auth.py:174` `rotate_refresh_token`);但前端 `lib/api.ts` 刷新后**只保存了 `access_token`,丢弃了新 refresh_token** → 下次刷新拿着已撤销的旧 token → 提前被登出。
- [x] 修前端拦截器:刷新成功后 `if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)`,与后端轮换对齐(`lib/api.ts:76-83`)。
- [x] 复核有效期语义(结论):access=120min、refresh=1 天,但 `rotate_refresh_token`(`security.py:388-397`)**每次刷新都重签 24h**——是**滑动窗口**,不是「登录起固定 24h」。
  - 修复前:第 1 次刷新(~2h)成功但存了失效的旧 refresh → 第 2 次刷新(~4h)拿已撤销 token → 401 强制登出(即所谓「提前掉线」,约每 4h)。
  - 修复后:轮换链不断,**活跃用户可持续续期**;闲置满 24h(实际由前端「闲置 10min 自动登出」先触发)才登出。**既非每 2h 掉线,也非登录起 24h 强制重登**。
  - ⚠️ 待产品决策:若真要「每天强制重登」(绝对 24h 上限),需在轮换时保留首次登录的 `exp`/加 `absolute_expiry`,而非每次重签——目前实现下活跃用户永不强制重登。
- [x] 验证:改动与相邻 `data.access_token` 同型(带守卫),不引入类型错误;前端全量 `tsc -b`/`vitest` 待 `pnpm install` 后跑。

### P0.3 其余 4 张账表页仍是无效占位 ✅
- [x] 实测复核:`TrialBalance` **已**是正确的 `/periods` 下拉模式(文档此处偏旧);真正坏的是另外三张:
  - `JournalLedger`:硬编码 `const periodId = 'current'` + `enabled: periodId !== 'current'` → query 从不触发。
  - `QuantityLedger` / `MultiColumnLedger`:虽有 `periodId` state,但用**裸文本框让用户手输科目/期间 UUID**,且未拉取 `/periods`,实际同样点不动。
- [x] 统一改为真实期间下拉(复用 `GET /periods` 模式,默认选中最近期间)。
- [x] `Quantity`/`MultiColumn` 的科目输入改为 `AccountPicker`;数量账加**末级 + `is_quantity` 科目筛选**(`filter={(a) => a.is_quantity && 无子节点}`)。
- [x] 验证:`tsc -b` + `vite build` 均通过。

### P0.4 登录初始化可用性 ✅
- [x] 根因:`seed.py` 开头 `SELECT count(*) FROM roles > 0` 就整体 `return` → 只要有任何角色,**用户和科目都被一并跳过**。
- [x] 改为「分段幂等」:角色按唯一 `name`、admin 用户按唯一 `username`、科目按唯一 `code`(`ON CONFLICT (code) DO NOTHING`)各自 get-or-create;重复运行只补缺失项。
- [x] admin 用户缺失时按 `admin/admin123` 建;已存在则保留(不改密),并在输出中明确提示。
- [x] 顺带修正:角色 `permissions` 用 `json.dumps`(原 `str().replace("'",'"')` 会生成非法 JSON 的 `True/False`)。
- [x] 默认账号:**admin / admin123**(见 seed 输出与 [[P8 文档]])。
- [x] 验证:`python -m py_compile seed.py` 通过;后端 86 测试无回归。(实际连库跑 seed 需 DB,建议部署时随 `alembic upgrade head` 后执行。)

---

## P1 — 让真实用户能直接用（MVP 上线前必备）🟠

### P1.1 首次启动 / 建账引导
- [x] 标准会计科目表种子:从 18 增至 34 个科目,补二级/末级(货币资金明细、预付/其他应收、累计折旧、无形资产、应付职工薪酬/增值税子目、长期借款、资本/盈余公积、其他业务成本、税金及附加、所得税费用),并按 `parent` code 连成树(`parent_id` 落地);存货(原材料/库存商品)标 `is_quantity`+`quantity_unit`,银行子户标 `is_cash`(`seed.py`)。
- [ ] 首个会计期间创建引导(目前需手动建期间才能录凭证)。
- [ ] 期初余额录入界面(新建账套必备;spec §2.9 account_balances 有 opening_*)。**需先加后端期初余额写入接口**(现 `periods.py` 只有 create/close/reopen,无 opening balance 写入)。

### P1.2 环境与配置 ✅
- [x] `.env.prod` 模板(`backend/.env.prod.example`)+ 启动校验:新增 `ENVIRONMENT`(development/production,与 `DEBUG` 解耦以免本地 `DEBUG=false` 被误判)。生产启动拒绝不安全默认值(默认/过短 `JWT_SECRET`、DB 占位密码、localhost CORS);缺 `DEEPSEEK_API_KEY` 仅告警不阻断。compose.prod 注入 `ENVIRONMENT=production`。
- [x] 生产关闭 SQLAlchemy `echo`:`database.py` 已 `echo=settings.DEBUG`,prod `DEBUG=false` 即关闭(已确认并文档化)。

### P1.3 报表导出落地（spec §3.7 / P6.4）✅
- [x] `POST /statements/export` 真正产出 Excel(资产负债表/利润表/现金流量表已实现,补 `openpyxl` 依赖——此前缺依赖会 500;新增 `trial_balance` 类型 + 树形 Excel helper)。PDF 仍返回 501(明确提示用 Excel)。
- [x] 前端「导出」按钮接活:新增 `exportStatement()` 下载工具 + `ExportButton` 组件(blob 下载、loading/error、无期间禁用),接到 TrialBalance / BalanceSheet / IncomeStatement / CashFlowStatement(原为死按钮/无按钮)。

---

## P2 — AI 模块激活与完善（spec §3.12 / §7.3）🟡

> 后端已实现四大功能 + NL 查询安全(sqlparse 仅 SELECT、强制 LIMIT 1000、ai_readonly 只读库、5s `statement_timeout`)。主要差「配 key + 实测 + 前端补全」。

- [ ] 配置 `OPENAI_API_KEY` 后端到端实测:智能凭证生成/修正、报表解读、期末检查、NL 查询 + 解释。
- [ ] 智能凭证:校验「科目必须存在 → 借贷平衡 → 不平自动修正(≤1 次)」实际生效(§7.3)。
- [ ] NL 查询:`conversation_id` 连续追问、执行耗时、SQL 可展开。
- [ ] 前端缺口:`AIChatPanel`(右下角全局悬浮面板)、独立 `AIPeriodChecker` 页(目前期末检查并入 PeriodClose)。
- [ ] 成本与稳定:LLM 调用重试/超时/降级(主备模型已有);记录 token 用量。

---

## P3 — 测试与质量（spec §8）🟡

- [ ] 修复 AI 余下 5 个测试(配 key 后)→ 后端全绿。
- [ ] 后端覆盖率达标:services ≥ 80%、API ≥ 70%(目前未测覆盖率)。
- [ ] Playwright e2e(spec §8 前端):`voucher-flow`(录入→审核→记账→查询)、`ledger-flow`、`period-close`、`ai-voucher`。
- [ ] 前端组件/hook 测试补充(VoucherForm 交互、useVouchers)。
- [ ] CI 流水线:PR 触发 `pytest` + `tsc -b` + `vitest` + e2e。
- [ ] 回归:把本轮修的真实 bug 各补一条针对性测试(记账 tz、序列化、MissingGreenlet)。

---

## P4 — 性能与基础设施（spec §2.15 / §4 / §7）🟢

- [ ] **索引核对**(§2.15):逐条确认 DDL 索引已建(凭证 period/status/date、分录 account、审计 created/resource、余额 period+account 唯一等)。
- [ ] **Redis 缓存真实落地**:目前 `trial-balance` 失效为 best-effort no-op;接真 Redis(科目树 5min stale、试算平衡缓存 + 记账后失效)。
- [ ] **Celery 异步任务**:`app/tasks/` 仅有空包;把批量折旧、期末结转执行等长任务改异步(prod compose 已留 celery worker);进度回传前端。
- [ ] API 响应 P95 < 200ms(不含 AI):对账表/报表做 `EXPLAIN ANALYZE` 慢查询分析。
- [ ] 大数据量分页/虚拟滚动(凭证列表、明细账)。

---

## P5 — 安全加固 🟢

- [ ] **限流中间件**:目前只有 CORS / CorrelationID / AuditContext,无 rate limit(spec §4 提及)。给登录、AI、写接口加限流。
- [ ] 审计日志补 `old_values`(目前 after_flush 只记 new_values;UPDATE 拿不到旧值,§2.12 设计有 old/new 对比)。
- [ ] 密码策略(强度/改密/锁定)、JWT_SECRET 走密管、HTTPS(nginx 已在,补证书/HSTS)。
- [ ] 权限矩阵端到端核对(§2.10 的 23 项权限是否都在接口 `require_permission` 落地)。
- [ ] 闲置登出已做 ✅;可选:多标签页同步登出、绝对会话上限提示。

---

## P6 — 功能 / UX 完善 🟢

- [ ] 利润表「上期对比」列:需有上一期间数据才显差异;补「上年同期」对比口径(spec §3.7 本期/本年累计已对)。
- [ ] 凭证模板「生成凭证」预填(从模板带入分录到录入页)。
- [ ] 银行对账 UX:自动匹配结果可手工调整、余额调节表打印。
- [ ] 固定资产:折旧计划表预览、批量折旧进度、卡片变更历史。
- [ ] 辅助核算:明细账 + 账龄分析前端页打磨(后端已实现)。
- [ ] 多栏明细账动态列前端体验;数量金额账单价显示。
- [ ] 全局:键盘流(凭证录入快捷键已部分)、打印样式、空状态/错误态统一。

---

## P7 — 部署与运维 🟢

- [ ] Alembic 迁移核对:确保模型变更(如本轮 `posted_at` tz)有对应迁移;首部署 `alembic upgrade head` 流程。
- [ ] 生产 compose 实跑验证(Nginx + FastAPI + Celery + DB + Redis);健康检查/重启策略。
- [ ] 数据库备份/恢复脚本验证(`backups/` 目录已在,内容待核)。
- [ ] 日志/监控:结构化日志(已有 CorrelationID)、错误上报、基础指标。
- [ ] 代码分支合并:`fix/mvp-voucher-reports-dashboard` → master(评审后)。

---

## P8 — 文档与交付 🟢

- [ ] 面向会计的「使用手册」(非技术):建账→录凭证→审核记账→出报表→期末结账。
- [ ] README / 部署文档 / API 文档(`/docs` 已自动生成,补业务说明)。
- [ ] 默认账号、初始化步骤、常见问题(如金额「分」录入规则、双人审核约束)。

---

## 🎯 建议执行顺序（最小代价 → 最大价值）

1. **P0 全清**(AI Decimal、refresh 前后端、4 张账表页、seed/登录)——半天到一天,清掉所有「看起来坏了」。
2. **P1.1 + P1.2**(建账引导 + .env.prod)——让非技术用户能从零开账套。
3. **P2 配 key 实测 AI** + **P3 修 AI 测试**——后端全绿、AI 可用。
4. **P1.3 报表导出** + **P6 关键 UX**——交付感。
5. **P4 性能 / P5 安全 / P7 部署**——上线前硬化。
6. **P3 e2e + CI / P8 文档**——可持续维护。

---

## 📌 一句话
> v2 把系统从「会崩」修到「能用」;**v3 的目标是从「能演示」到「能交付给真实财务每天用」**——重点是 P0 收尾正确性、P1 建账引导、P2 AI 激活,其余按上线节奏推进。
