# Core Accounting v1 — 技术设计文档

## 1. 概述

绿色项目，替代浪潮内账系统。面向 3 类角色（财务人员/财务经理/管理员），覆盖凭证管理、账表查询、辅助核算、财务报表、期末处理、系统管理、AI 辅助、出纳与固定资产 9 大模块，共 87 项需求。

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React 18)                    │
│  Vite + TypeScript + Tailwind + TanStack Router/Query    │
│  React Hook Form + Zod + Recharts + Shadcn/ui            │
├─────────────────────────────────────────────────────────┤
│                  API Gateway (FastAPI)                    │
│  JWT Auth / RBAC / Rate Limiting / CORS                  │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ 凭证服务 │ 账表服务 │ 报表服务 │ 期末服务 │ 出纳/固定资产 │
│ 辅助核算 │ AI 服务  │ 系统管理 │ 审计日志 │ LangChain    │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│              PostgreSQL 15 + Redis (Celery)              │
│              SQLAlchemy 2.0 (async) + Alembic            │
└─────────────────────────────────────────────────────────┘
```

**部署**：Docker Compose（前端 Nginx 静态托管 + FastAPI + PostgreSQL + Redis + Celery Worker）

---

## 3. 后端设计

### 3.1 项目结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理 (Pydantic Settings)
│   ├── models/                 # SQLAlchemy ORM 模型
│   │   ├── voucher.py          # 凭证/分录/模板
│   │   ├── account.py          # 科目/科目余额
│   │   ├── auxiliary.py        # 辅助核算项/关联
│   │   ├── report.py           # 报表模板/报表
│   │   ├── period.py           # 会计期间/结转/结账
│   │   ├── cashier.py          # 现金/银行日记账
│   │   ├── asset.py            # 固定资产卡片
│   │   └── system.py           # 用户/角色/权限/日志
│   ├── schemas/                # Pydantic 请求/响应模式
│   ├── api/                    # 路由层 (REST)
│   │   ├── v1/
│   │   │   ├── vouchers.py     # POST/GET/PUT/DELETE /vouchers
│   │   │   ├── accounts.py     # /accounts, /ledgers
│   │   │   ├── reports.py      # /reports, /balance-sheet
│   │   │   ├── periods.py      # /period-close, /carry-forward
│   │   │   ├── cashier.py      # /cash-journals, /bank-journals
│   │   │   ├── assets.py       # /fixed-assets
│   │   │   ├── ai.py           # /ai/* (自然语言/AI接口)
│   │   │   └── admin.py        # /users, /roles, /permissions
│   │   └── deps.py             # 公共依赖 (Auth, DB Session)
│   ├── services/               # 业务逻辑层
│   │   ├── voucher_service.py
│   │   ├── ledger_service.py
│   │   ├── report_service.py
│   │   ├── period_service.py
│   │   ├── cashier_service.py
│   │   ├── asset_service.py
│   │   └── ai_service.py
│   ├── ai/                     # AI 模块
│   │   ├── llm_client.py       # LangChain + OpenAI 封装
│   │   ├── voucher_generator.py
│   │   ├── report_interpreter.py
│   │   ├── period_checker.py
│   │   └── nl_query.py         # 自然语言 → SQL
│   ├── core/
│   │   ├── security.py         # JWT/RBAC/密码哈希
│   │   ├── errors.py           # 统一异常处理
│   │   └── audit.py            # 审计日志中间件
│   └── tasks/                  # Celery 任务
│       ├── export.py           # 异步导出 (Excel/PDF)
│       └── backup.py           # 数据库备份
├── alembic/                    # 数据库迁移
├── tests/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

### 3.2 数据库设计（关键表）

```
┌────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  accounts   │     │ voucher_entries  │     │    vouchers       │
│  (科目表)   │◄────│  (凭证分录)       │────►│   (凭证表)        │
│  - code     │     │  - voucher_id     │     │  - voucher_no     │
│  - name     │     │  - account_id     │     │  - date           │
│  - type     │     │  - debit_amount   │     │  - status         │
│  - level    │     │  - credit_amount  │     │  - auditor_id     │
│  - parent_id│     │  - summary        │     │  - creator_id     │
└────────────┘     └────────┬─────────┘     └──────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │entry_aux   │ │entry_aux   │ │entry_aux   │
     │(部门关联)  │ │(个人关联)  │ │(项目关联)  │
     └────────────┘ └────────────┘ └────────────┘

┌────────────┐     ┌─────────────────┐
│  periods    │     │  carry_forward   │
│ (会计期间)  │────►│  (结转记录)       │
│  - year     │     │  - template_id    │
│  - month    │     │  - from/to_acct   │
│  - status   │     │  - amount         │
└────────────┘     └─────────────────┘
```

### 3.3 API 设计原则

- **RESTful**：资源命名用复数名词，/api/v1/vouchers
- **分页统一**：`{ items: [], total, page, page_size }`
- **错误统一**：`{ error: { code, message, detail } }`
- **认证**：Bearer JWT（access token 2h, refresh token 7d）
- **权限**：装饰器 `@require_role("finance_manager")`
- **审计**：所有写操作记录 operator_id / action / ip / timestamp

### 3.4 性能策略

- 科目余额表：月度快照表 + Redis 缓存（写操作后失效）
- 多栏明细账：分页 + 按科目预聚合
- 报表：异步生成，前端轮询 /tasks/{id}
- 数据导出：Celery 异步任务，完成后通知

---

## 4. 前端设计

### 4.1 项目结构

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx                   # 路由配置
│   ├── routes/                   # TanStack Router 路由
│   ├── features/                 # 按模块组织
│   │   ├── vouchers/             # 凭证管理
│   │   │   ├── VoucherList.tsx
│   │   │   ├── VoucherForm.tsx   # 录入/编辑凭证
│   │   │   ├── VoucherTemplate.tsx
│   │   │   └── useVouchers.ts    # TanStack Query hooks
│   │   ├── ledgers/              # 账表查询
│   │   ├── auxiliary/            # 辅助核算
│   │   ├── reports/              # 财务报表
│   │   ├── period/               # 期末处理
│   │   ├── cashier/              # 出纳
│   │   ├── assets/               # 固定资产
│   │   ├── admin/                # 系统管理
│   │   └── ai/                   # AI 功能面板
│   ├── components/               # 共享组件
│   │   ├── ui/                   # Shadcn/ui 组件
│   │   ├── layout/               # Sidebar/Header/Breadcrumb
│   │   ├── DataTable.tsx         # 通用表格（排序/分页/导出）
│   │   ├── AccountPicker.tsx     # 科目选择器（树形）
│   │   └── AIChat.tsx            # AI 聊天面板
│   ├── hooks/                    # 通用 hooks
│   ├── lib/                      # axios 封装 / utils
│   ├── stores/                   # Zustand 全局状态
│   └── types/                    # TypeScript 类型定义
├── Dockerfile
├── package.json
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

### 4.2 核心交互

| 模块 | 关键组件 | 交互要点 |
|------|---------|---------|
| 凭证录入 | VoucherForm | 双栏借贷平衡表格，科目树选择，辅助核算弹出选择，实时合计线 |
| 科目余额表 | BalanceSheet | 树形展开/折叠，多期对比列，穿透至明细账 |
| 三栏明细账 | DetailLedger | 期初/本期/期末三栏，日期范围，联查凭证 |
| 多栏明细账 | MultiColumnLedger | 动态列（按子科目展开），分页加载 |
| 资产负债表 | BalanceSheetRpt | 分行业模板渲染，层级展开，导出 Excel/PDF |
| 期末结转 | CarryForward | 模板列表 + 勾选 + 一键执行，进度条 |
| 自然语言查询 | NLChat | 对话式输入，展示 SQL + 结果表格，支持连续追问 |
| AI 凭证生成 | AIVoucher | 自然语言描述 → 预览（可修正）→ 确认生成 |

### 4.3 状态管理

- **服务端状态**：TanStack Query（自动缓存/失效/重取）
- **UI 状态**：Zustand store（sidebar 折叠、当前期间、用户信息）
- **表单状态**：React Hook Form + Zod 校验

### 4.4 路由设计

```
/                          → 重定向到 /dashboard
/dashboard                 → 首页仪表盘
/vouchers                  → 凭证列表
/vouchers/new              → 凭证录入
/vouchers/:id              → 凭证详情/编辑
/vouchers/templates        → 模板管理
/ledgers/balance           → 科目余额表
/ledgers/general           → 总账
/ledgers/detail/:accountId → 三栏明细账
/ledgers/multi/:accountId  → 多栏明细账
/ledgers/journal           → 序时账
/auxiliary/:type           → 辅助核算（部门/个人/单位/项目）
/reports/balance-sheet     → 资产负债表
/reports/income            → 利润表
/reports/cash-flow         → 现金流量表
/period/close              → 期末结账
/period/carry              → 期末结转
/cashier/cash              → 现金日记账
/cashier/bank              → 银行日记账
/assets                    → 固定资产
/admin/accounts            → 科目管理
/admin/users               → 用户管理
/admin/permissions         → 权限管理
/admin/logs                → 审计日志
/ai                        → AI 工作台
```

---

## 5. AI 模块设计

### 5.1 自然语言生成凭证

```
用户输入: "支付张三差旅费 5000 元，从工行转出"
           ↓
LLM (GPT-4o / DeepSeek-V4)
  - 科目匹配 (费用科目 + 银行科目)
  - 辅助核算识别 (张三 → 个人核算)
  - 借方/贷方金额拆分
           ↓
返回凭证预览（可编辑）
  - 科目 code + name
  - 借方/贷方金额
  - 辅助核算关联
  - 借贷平衡校验 (不平衡则重试)
           ↓
用户确认 → 写入 voucher + voucher_entries
```

### 5.2 报表解读

- 输入：资产负债表/利润表/现金流量表 数据 snapshot
- 输出：同比/环比变化、关键比率（流动比率、负债率等）、风险提示
- 异常检测：波动超过 20% 标注

### 5.3 期末结转检查（10 项）

1. 未记账凭证检查
2. 期间匹配检查
3. 结转模板完整性
4. 借贷平衡检查
5. 固定资产折旧计提
6. 暂估清理检查
7. 损益结转完整性
8. 辅助核算一致性
9. 科目余额方向异常
10. 银行对账未达项

### 5.4 自然语言查询

```
用户: "上个月管理费用超过 1 万的条目"
  → LLM 生成 SQL → 执行 → 结果表格
  → 支持追问: "其中招待费有多少?"
```

---

## 6. 安全设计

- **认证**：JWT access + refresh，refresh token 存在 httpOnly cookie
- **授权**：RBAC 三级角色 + 可扩展权限位（bitmask）
- **审计**：独立 audit_log 表，不可删除，定期归档
- **数据**：传输层 TLS，存储层 PostgreSQL 行级安全策略（可选）
- **AI 安全**：LLM 生成的 SQL 在只读副本执行，禁止 DML

---

## 7. 技术选型理由

| 决策 | 选择 | 理由 |
|------|------|------|
| 前端框架 | React 18 | 生态成熟，TanStack 系列支持好 |
| 构建工具 | Vite | 快速 HMR，TS 原生支持 |
| CSS | Tailwind + Shadcn/ui | 快速原型，组件可定制 |
| 后端框架 | FastAPI | 异步支持，自动 OpenAPI 文档 |
| ORM | SQLAlchemy 2.0 async | 成熟稳定，Alembic 迁移 |
| 任务队列 | Celery + Redis | 导出/备份异步化 |
| AI | LangChain + OpenAI | 灵活的链式调用 |
| 数据库 | PostgreSQL 15 | 财务场景的事务一致性，JSON 支持 |
| 缓存 | Redis | Celery broker + 热数据缓存 |

---

## 8. 开发计划

| 阶段 | 内容 | 估时 |
|------|------|------|
| Phase 1 | 项目脚手架、CI/CD、数据库 migrate | 1 周 |
| Phase 2 | 系统管理（科目/用户/权限/日志） | 2 周 |
| Phase 3 | 凭证管理（录入/审核/记账/查询） | 3 周 |
| Phase 4 | 账表查询（余额表/总账/明细账） | 2 周 |
| Phase 5 | 辅助核算 + 出纳 + 固定资产 | 3 周 |
| Phase 6 | 财务报表（核心三表） | 2 周 |
| Phase 7 | 期末处理（结转/结账） | 2 周 |
| Phase 8 | AI 模块 | 3 周 |
| Phase 9 | 集成测试 + 性能优化 + 部署 | 2 周 |

**预计总工期**：约 20 周（5 个月）

---

*文档版本：v0.1 | 日期：2026-06-13*
