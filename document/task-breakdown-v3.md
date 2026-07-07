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

### 2026-07-08 进展快照（分支 `feat/p3-p6-hardening`,5 commits）

- **P0–P1 已全清**(见下),本轮完成 **P3/P4/P5 核心项 + P6 三项**,明细见各节勾选与说明。
- 测试基线:后端 **101 通过 / 0 失败**(xfail 1、xpass 4),前端 **19 通过** + `tsc -b`/`vite build` 绿;新增 CI 工作流。
- **端到端 live 验证**(Postgres 5433 + Redis 6380 + uvicorn 8002 + vite 5173):登录 → 建期间(2026-07)→ 录凭证 JZ-2026-07-001(¥800)→ 双人审核(制单人自审被正确拒绝)→ 记账 → 试算平衡 800/800 → 利润表净利 -800;缓存 key 记账时实际失效;审计 old_values 落库;限流计数在 Redis 递增。
- 验证用数据:admin/admin123;新增 `auditor1/auditor123`(finance_manager,双签验证用,可删);测试凭证 JZ-2026-07-001 已记账(period 2026-07)。

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

### P1.1 首次启动 / 建账引导 ✅
- [x] 标准会计科目表种子:从 18 增至 34 个科目,补二级/末级(货币资金明细、预付/其他应收、累计折旧、无形资产、应付职工薪酬/增值税子目、长期借款、资本/盈余公积、其他业务成本、税金及附加、所得税费用),并按 `parent` code 连成树(`parent_id` 落地);存货(原材料/库存商品)标 `is_quantity`+`quantity_unit`,银行子户标 `is_cash`(`seed.py`)。
- [x] 首个会计期间创建引导:`PeriodManage`(`/admin/periods`)已有空状态引导「请先创建一个会计期间开始使用」+ 创建对话框(年/月、重复校验),满足从零建期间。(未做多步 wizard,MVP 够用。)
- [x] 期初余额录入界面(`/period/opening-balances`):新增后端 `GET/PUT /periods/{id}/opening-balances`(校验:期间开放、无记账活动、单边为零、仅末级、借贷平衡;closing=opening),前端末级科目借/贷录入 + 实时平衡校验 + 只读态(已结账/已有凭证)。

### P1.2 环境与配置 ✅
- [x] `.env.prod` 模板(`backend/.env.prod.example`)+ 启动校验:新增 `ENVIRONMENT`(development/production,与 `DEBUG` 解耦以免本地 `DEBUG=false` 被误判)。生产启动拒绝不安全默认值(默认/过短 `JWT_SECRET`、DB 占位密码、localhost CORS);缺 `DEEPSEEK_API_KEY` 仅告警不阻断。compose.prod 注入 `ENVIRONMENT=production`。
- [x] 生产关闭 SQLAlchemy `echo`:`database.py` 已 `echo=settings.DEBUG`,prod `DEBUG=false` 即关闭(已确认并文档化)。

### P1.3 报表导出落地（spec §3.7 / P6.4）✅
- [x] `POST /statements/export` 真正产出 Excel(资产负债表/利润表/现金流量表已实现,补 `openpyxl` 依赖——此前缺依赖会 500;新增 `trial_balance` 类型 + 树形 Excel helper)。PDF 仍返回 501(明确提示用 Excel)。
- [x] 前端「导出」按钮接活:新增 `exportStatement()` 下载工具 + `ExportButton` 组件(blob 下载、loading/error、无期间禁用),接到 TrialBalance / BalanceSheet / IncomeStatement / CashFlowStatement(原为死按钮/无按钮)。

---

## P2 — AI 模块激活与完善（spec §3.12 / §7.3）🟡

> 后端已实现四大功能 + NL 查询安全(sqlparse 仅 SELECT、强制 LIMIT 1000、ai_readonly 只读库、5s `statement_timeout`)。主要差「配 key + 实测 + 前端补全」。

- [ ] 后端到端实测:智能凭证生成/修正、报表解读、期末检查、NL 查询 + 解释。(2026-07-08 更新:`DEEPSEEK_API_KEY` **已在 `.env` 配置且真实调通**——测试套件实际命中 DeepSeek,NL→SQL 生成了合法 PostgreSQL;缺的是四大功能的 UI 级端到端实测。)
- [ ] 智能凭证:校验「科目必须存在 → 借贷平衡 → 不平自动修正(≤1 次)」实际生效(§7.3)。
- [ ] NL 查询:`conversation_id` 连续追问、执行耗时、SQL 可展开。
- [ ] 前端缺口:`AIChatPanel`(右下角全局悬浮面板)、独立 `AIPeriodChecker` 页(目前期末检查并入 PeriodClose)。
- [ ] 成本与稳定:LLM 调用重试/超时/降级(主备模型已有);记录 token 用量。

---

## P3 — 测试与质量（spec §8）🟡（2026-07-08 大部分完成,分支 `feat/p3-p6-hardening`）

- [x] 修复 AI 余下 3 个测试 → 后端全绿(**101 通过 / 0 失败**)。全部按产品 bug 修,非改测试:
  - `/ai/voucher/generate` 期间不存在时先 404 再调 LLM(原先白白消耗 token 后 502);
  - NL 查询执行 LLM 生成的 SQL 增加异常处理 → 干净 502 + 回滚(原先未处理异常且污染连接,导致后续请求 401);
  - 测试夹具改为 commit(原 flush-only 数据会被错误路径的 rollback 抹掉,表现为间歇 401)。
- [ ] 后端覆盖率达标:**已测得 45%**(services ≥80% 目标不适用——`app/services` 是空包,逻辑在 api/v1;API 模块 12–78% 不等)。达标仍待补测试。
- [ ] Playwright e2e:未做(本轮以 curl 实测了完整凭证流水线:录入→双人审核→记账→账表勾稽,见 P4/P5 验证记录)。
- [x] 前端组件测试:修复 VoucherForm 测试套件(vi.mock 提升 bug 导致 0 条运行、断言全是恒真 `>=0`)→ 19 通过且真实断言。`useVouchers` hook 测试仍缺。
- [x] CI 流水线:`.github/workflows/ci.yml` — PR/push 触发后端 `uv run pytest` + 前端 `pnpm tsc -b + vitest + build`(CI 无 DEEPSEEK key,AI 测试按设计容忍 502)。e2e 未纳入。
- [x] 回归测试(`tests/unit/test_regressions.py` 等 12 条新增):审计 Decimal/date/UUID 序列化、datetime-是-date 陷阱、NL 查询坏 SQL、404-不调-LLM、审计 old_values、限流、缓存降级。
- [x] 附带修复:audit 监听器改为幂等 + `AuditLog` BIGINT 主键加 sqlite 变体 → **审计路径首次在测试中被真实执行**(原先 lifespan 不跑,监听器从未装上)。

---

## P4 — 性能与基础设施（spec §2.15 / §4 / §7）🟢（2026-07-08 核心项完成）

- [x] **索引核对**(§2.15):已逐条对照**运行中 Postgres** 确认全部存在——凭证 period_status/date/status_date、分录 account/voucher/account_voucher、审计 created/resource/user_created、余额 period+account 唯一(`voucher_no` 由唯一约束索引覆盖,等价)。
- [x] **Redis 缓存真实落地**(`app/core/cache.py`):JSON 缓存助手,任何 Redis 故障降级为 miss/no-op,`CACHE_ENABLED=false` 供测试关闭。
  - 试算平衡:按 (period, level, include_zero) 缓存 10min,**记账时失效**(替换原 no-op stub);
  - 科目树:缓存 5min,科目增删改时失效;
  - 实测:tree 89ms→3.5ms(25×);记账后 `trial-balance:*` key 实际消失(live 验证)。
- [ ] **Celery 异步任务**:未做(`app/tasks/` 仍空包)。本轮明确降级——无长任务瓶颈证据前不做。
- [ ] API P95 / `EXPLAIN ANALYZE` 慢查询分析:未做。
- [x] 分页现状核实:凭证列表已有分页;明细账/序时账按单期间天然有界(带余额滚动列的账页无法简单分页),MVP 规模下判定够用——大数据量虚拟滚动留待有真实数据量再做。

---

## P5 — 安全加固 🟢（2026-07-08 核心项完成）

- [x] **限流中间件**(`app/core/ratelimit.py`):固定窗口按 IP——登录 10/min、AI 30/min、写接口 240/min(env 可调);Redis 计数(跨 worker),不可用时进程内降级;429 走标准错误信封;`RATE_LIMIT_ENABLED=false` 供测试。实测 Redis 中 `ratelimit:login/write:*` 计数在真实请求下递增;登录连错 e2e 测试拿到 429。
- [x] 审计日志补 `old_values`:after_flush 中用 attribute history(在 after_flush_postexec 前仍完整)取变更列旧值,只记变更列(兼作 change set)。**live 验证**:凭证 draft→audited→posted 两次 UPDATE 均带 old_values。
- [ ] 密码策略(强度/改密/锁定)、JWT_SECRET 走密管、HTTPS 证书/HSTS:未做。
- [x] 权限矩阵核对:逐模块统计 routes vs `require_permission`,补上两个真实缺口——**凭证模板 5 个路由原先零权限校验**(现要求 `voucher:create`)、凭证导出补 `report:export`。凭证 list/get 保持仅登录(所有种子角色均有凭证读能力,属有意决策)。auth/health 天然开放、dashboard 仅登录,合理。
- [ ] 可选项(多标签页同步登出、绝对会话上限):未做。⚠️ P0.2 遗留的产品决策(活跃用户永不强制重登 vs 绝对 24h)仍待拍板。

---

## P6 — 功能 / UX 完善 🟢（2026-07-08 完成 3 项）

- [x] 利润表「上期金额」对比列:后端按 (year, month-1)(跨年取 12 月)查上期余额,逐行/小计/合计计算上期净额,无上期时字段省略;前端条件渲染该列。「上年同期」口径仍未做。
- [x] 凭证模板「生成凭证」预填:原按钮只跳转不预填(死一半的功能)。VoucherForm 现读取 `?templateId=`,拉取模板 + 科目表,预填科目/方向/摘要并解析 code/name/辅助核算类型,**金额留空由用户填**;模板加载失败降级为空白凭证。
- [ ] 银行对账 UX:未做。
- [ ] 固定资产(折旧计划预览/批量折旧进度/卡片变更历史):未做。
- [ ] 辅助核算前端页打磨:未做。
- [x] 数量金额账单价显示:后端返回分录**录入的单价**(`unit_price_in/out`,无单价时按金额÷数量兜底),前端优先显示录入单价(原先只能前端反算)。多栏明细账动态列仍未做。
- [ ] 全局键盘流/打印样式/空状态统一:未做。
- [x] 附带修复(live 实测发现的存量 bug):旧种子科目行 `is_quantity/is_cash/aux_types` 为 NULL,导致 `GET /accounts` 与 `/accounts/tree` 直接 500——schema 加 before-validator 容忍 NULL + 端点 bool() 防御 + 存量数据 SQL 回填。

---

## P7 — 部署与运维 🟢

- [ ] Alembic 迁移核对:确保模型变更(如本轮 `posted_at` tz)有对应迁移;首部署 `alembic upgrade head` 流程。⚠️ 本轮新增注意:线上/其他环境的存量科目 NULL 布尔列需要回填迁移(本地已手工 `UPDATE`,schema 层已容错,但建议补一条 data migration 固化)。
- [ ] 生产 compose 实跑验证(Nginx + FastAPI + Celery + DB + Redis);健康检查/重启策略。(开发 compose 的 db/redis 已实跑验证 ✅)
- [ ] 数据库备份/恢复脚本验证(`backups/` 目录已在,内容待核)。
- [ ] 日志/监控:结构化日志(已有 CorrelationID)、错误上报、基础指标。
- [ ] 代码分支合并:**`feat/p3-p6-hardening` → master(评审后,5 commits,含 CI)**。

---

## P8 — 文档与交付 🟢

- [ ] 面向会计的「使用手册」(非技术):建账→录凭证→审核记账→出报表→期末结账。
- [ ] README / 部署文档 / API 文档(`/docs` 已自动生成,补业务说明)。
- [ ] 默认账号、初始化步骤、常见问题(如金额「分」录入规则、双人审核约束)。

---

## 🎯 建议执行顺序（最小代价 → 最大价值）

1. ~~**P0 全清**~~ ✅
2. ~~**P1.1 + P1.2**(建账引导 + .env.prod)~~ ✅
3. **P2 前端补全 + AI 全功能实测**——key 已配好(DEEPSEEK,测试已真实调通 NL→SQL);剩 `AIChatPanel`、`AIPeriodChecker` 页与四大功能 UI 端到端。~~P3 修 AI 测试~~ ✅
4. ~~**P1.3 报表导出**~~ ✅ + **P6 剩余 UX**(银行对账/固定资产/辅助核算/键盘流,已完成 3 项)。
5. ~~P4 缓存与索引 / P5 限流·审计·权限~~ ✅;剩:**Celery、P95 分析、密码策略/HSTS、P7 部署验证**——上线前硬化。
6. **P3 e2e(Playwright)+ 覆盖率达标** / **P8 文档**——可持续维护。~~CI~~ ✅

> 下一轮最短路径:合并 `feat/p3-p6-hardening` → P8 使用手册 + P7 生产 compose 实跑 → Playwright e2e 四条主流程。

---

## 📌 一句话
> v2 把系统从「会崩」修到「能用」;**v3 的目标是从「能演示」到「能交付给真实财务每天用」**——重点是 P0 收尾正确性、P1 建账引导、P2 AI 激活,其余按上线节奏推进。
