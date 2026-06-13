# Engineering Spec — Core Accounting v1

> 基于 design.md + ux-design.md，本文档定义可实施的工程规格。
> 所有接口、数据模型、组件接口均为实现级粒度。

---

## 1. 开发环境

```bash
# 后端
Python 3.11+
PostgreSQL 15
Redis 7
# 前端
Node.js 20+
pnpm 9+
```

**启动命令：**
```bash
# 后端
cd backend && cp .env.example .env && docker compose up -d db redis
uvicorn app.main:app --reload

# 前端
cd frontend && pnpm install && pnpm dev
```

---

## 2. 数据模型

### 2.1 科目表 accounts

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | |
| code | VARCHAR(20) | UNIQUE, NOT NULL | 科目编码 1001 |
| name | VARCHAR(100) | NOT NULL | 科目名称 |
| parent_id | UUID | FK→accounts.id | 树形层级 |
| level | SMALLINT | NOT NULL | 层级 1-4 |
| type | VARCHAR(20) | NOT NULL | asset/liability/equity/revenue/expense |
| dc_type | CHAR(1) | NOT NULL | 余额方向 D/C |
| is_cash | BOOLEAN | DEFAULT false | 现金银行科目标记 |
| aux_types | JSONB | DEFAULT '[]' | 辅助核算类型 ["部门","个人"] |
| is_quantity | BOOLEAN | DEFAULT false | 是否数量核算 |
| quantity_unit | VARCHAR(20) | | 计量单位 |
| is_enabled | BOOLEAN | DEFAULT true | |
| created_at | TIMESTAMPTZ | | |
| updated_at | TIMESTAMPTZ | | |

### 2.2 凭证表 vouchers

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | |
| voucher_no | VARCHAR(20) | UNIQUE, NOT NULL | JZ-2026-06-001 |
| date | DATE | NOT NULL | 凭证日期 |
| period_id | UUID | FK→periods.id | 会计期间 |
| attachments | SMALLINT | DEFAULT 0 | 附单据数 |
| status | VARCHAR(20) | NOT NULL | draft/audited/posted/reversed |
| creator_id | UUID | FK→users.id | |
| auditor_id | UUID | FK→users.id | 审核人 |
| posted_at | TIMESTAMPTZ | | 记账时间 |
| source | VARCHAR(50) | DEFAULT 'manual' | manual/template/ai/import |
| ai_conversation | JSONB | | AI 生成时的对话记录 |
| deleted_at | TIMESTAMPTZ | | 软删除标记 |
| reversed_voucher_id | UUID | FK→vouchers.id | 冲销来源凭证 |
| reversal_type | VARCHAR(20) | | full/partial |

### 2.3 凭证分录 voucher_entries

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | |
| voucher_id | UUID | FK→vouchers.id, RESTRICT | |
| row_number | SMALLINT | NOT NULL | 分录行号 |
| account_id | UUID | FK→accounts.id | |
| summary | VARCHAR(200) | NOT NULL | 摘要 |
| debit_amount | NUMERIC(18,2) | DEFAULT 0 | 借方金额 |
| credit_amount | NUMERIC(18,2) | DEFAULT 0 | 贷方金额 |
| quantity | NUMERIC(18,4) | | 数量（数量金额账） |
| price | NUMERIC(18,4) | | 单价 |

**约束**：CHECK (debit_amount = 0 OR credit_amount = 0)，CHECK (debit_amount > 0 OR credit_amount > 0)

### 2.4 辅助核算关联 entry_auxiliaries

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| entry_id | UUID | FK→voucher_entries.id, RESTRICT |
| aux_type | VARCHAR(20) | 部门/个人/单位/项目 |
| department_id | UUID | FK→departments.id, NULLABLE |
| individual_id | UUID | FK→individuals.id, NULLABLE |
| counterparty_id | UUID | FK→counterparties.id, NULLABLE |
| project_id | UUID | FK→projects.id, NULLABLE |

**约束**：四个档案 FK 均为可空，CHECK 约束确保恰好一个非空：
```sql
CHECK (
  (CASE WHEN department_id IS NOT NULL THEN 1 ELSE 0 END +
   CASE WHEN individual_id IS NOT NULL THEN 1 ELSE 0 END +
   CASE WHEN counterparty_id IS NOT NULL THEN 1 ELSE 0 END +
   CASE WHEN project_id IS NOT NULL THEN 1 ELSE 0 END) = 1
)
```

> 说明：不再使用多态 FK，改为四个独立可空列，保留引用完整性。

### 2.5 辅助核算档案（四张表，结构相同）

`departments` / `individuals` / `counterparties` / `projects`

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| code | VARCHAR(20) | UNIQUE |
| name | VARCHAR(100) | NOT NULL |
| is_enabled | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMPTZ | |

### 2.6 会计期间 periods

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| year | SMALLINT | NOT NULL |
| month | SMALLINT | 1-12 |
| status | VARCHAR(20) | open/closed |
| closed_at | TIMESTAMPTZ | |
| closed_by | UUID | FK→users.id |

**约束**：UNIQUE(year, month)

### 2.7 结转记录 carry_forwards

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| period_id | UUID | FK→periods.id |
| template_id | UUID | FK→carry_templates.id |
| voucher_id | UUID | FK→vouchers.id |
| from_account_id | UUID | FK→accounts.id |
| to_account_id | UUID | FK→accounts.id |
| amount | NUMERIC(18,2) | |
| executed_at | TIMESTAMPTZ | |

### 2.8 结转模板 carry_templates

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(100) | 结转制造费用 |
| description | TEXT | |
| rules | JSONB | 结转规则定义 |
| sort_order | SMALLINT | |
| is_enabled | BOOLEAN | DEFAULT true |

### 2.9 科目余额快照 account_balances

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| period_id | UUID | FK→periods.id |
| account_id | UUID | FK→accounts.id |
| opening_debit | NUMERIC(18,2) | 期初借方 |
| opening_credit | NUMERIC(18,2) | 期初贷方 |
| current_debit | NUMERIC(18,2) | 本期借方 |
| current_credit | NUMERIC(18,2) | 本期贷方 |
| closing_debit | NUMERIC(18,2) | 期末借方 |
| closing_credit | NUMERIC(18,2) | 期末贷方 |

**约束**：UNIQUE(period_id, account_id)

### 2.10 用户/角色/权限

```sql
users: id, username, password_hash, display_name, role_id(FK), is_enabled, last_login_at
roles: id, name(finance_staff/finance_manager/admin), permissions(JSONB bitmap)
```

**权限矩阵：**

| Permission | finance_staff | finance_manager | admin |
|---|---|---|---|
| voucher:create | ✓ | ✓ | ✓ |
| voucher:edit:own | ✓ | ✓ | ✓ |
| voucher:edit:any |   | ✓ | ✓ |
| voucher:delete:draft | ✓ | ✓ | ✓ |
| voucher:audit |   | ✓ |   |
| voucher:unaudit |   | ✓ |   |
| voucher:post |   | ✓ |   |
| voucher:reverse |   | ✓ |   |
| account:read | ✓ | ✓ | ✓ |
| account:manage |   |   | ✓ |
| ledger:read | ✓ | ✓ | ✓ |
| report:read | ✓ | ✓ | ✓ |
| report:export | ✓ | ✓ | ✓ |
| period:close |   | ✓ | ✓ |
| period:reopen |   |   | ✓ |
| aux:manage | ✓ | ✓ | ✓ |
| cashier:use | ✓ | ✓ | ✓ |
| assets:manage |   | ✓ | ✓ |
| ai:use | ✓ | ✓ | ✓ |
| admin:users |   |   | ✓ |
| admin:roles |   |   | ✓ |
| admin:backup |   |   | ✓ |
| admin:audit-log |   |   | ✓ |

### 2.11 refresh_tokens

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK→users.id, CASCADE |
| token_hash | VARCHAR(255) | UNIQUE, NOT NULL |
| expires_at | TIMESTAMPTZ | NOT NULL |
| revoked_at | TIMESTAMPTZ | | 注销时间 |
| created_at | TIMESTAMPTZ | |

> 存储 refresh token 的 SHA-256 哈希，用于 logout 时吊销。

### 2.12 审计日志 audit_logs

| 列 | 类型 |
|---|---|
| id | BIGSERIAL PK |
| user_id | UUID |
| action | VARCHAR(50) |
| resource_type | VARCHAR(50) |
| resource_id | UUID |
| old_values | JSONB |
| new_values | JSONB |
| ip_address | INET |
| created_at | TIMESTAMPTZ |

### 2.13 现金/银行日记账

```sql
cash_journals / bank_journals:
  id, date, voucher_id(FK), account_id(FK), summary, debit, credit, balance,
  serial_no, counterparty, created_at
```

### 2.14 固定资产

```sql
fixed_assets:
  id, code, name, category, purchase_date, purchase_amount,
  salvage_value, useful_life_months, depreciation_method(straight/double_declining/sum_of_years),
  monthly_depreciation, accumulated_depreciation, net_value,
  status(in_use/disposed/cleared), dept_id(FK), created_at
```

### 2.15 关键索引（DDL）

> 以下索引是生产性能必需，需与建表 DDL 一并执行。

```sql
-- 凭证分录（最高优先级）
CREATE INDEX idx_voucher_entries_account ON voucher_entries(account_id);
CREATE INDEX idx_voucher_entries_voucher ON voucher_entries(voucher_id);
CREATE INDEX idx_voucher_entries_account_voucher ON voucher_entries(account_id, voucher_id);

-- 凭证
CREATE INDEX idx_vouchers_period_status ON vouchers(period_id, status);
CREATE INDEX idx_vouchers_date ON vouchers(date);
CREATE INDEX idx_vouchers_status_date ON vouchers(status, date);

-- 辅助核算关联
CREATE INDEX idx_entry_aux_entry ON entry_auxiliaries(entry_id);
CREATE INDEX idx_entry_aux_dept ON entry_auxiliaries(department_id);
CREATE INDEX idx_entry_aux_individual ON entry_auxiliaries(individual_id);
CREATE INDEX idx_entry_aux_counterparty ON entry_auxiliaries(counterparty_id);
CREATE INDEX idx_entry_aux_project ON entry_auxiliaries(project_id);

-- 审计日志（支持按时间倒序分页）
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_user_created ON audit_logs(user_id, created_at);

-- 出纳
CREATE INDEX idx_cash_journals_account_date ON cash_journals(account_id, date);
CREATE INDEX idx_bank_journals_account_date ON bank_journals(account_id, date);

-- 固定资产
CREATE INDEX idx_fixed_assets_dept_status ON fixed_assets(dept_id, status);
CREATE INDEX idx_fixed_assets_status ON fixed_assets(status);

-- 结转
CREATE INDEX idx_carry_forwards_period ON carry_forwards(period_id);
CREATE INDEX idx_carry_templates_sort ON carry_templates(sort_order);
```

---

## 3. API 契约

Base: `/api/v1` | Auth: `Authorization: Bearer <jwt>`

### 3.1 通用格式

**分页请求：**
```
GET /resource?page=1&page_size=20&sort=name&order=asc
```

**分页响应：**
```json
{
  "items": [],
  "total": 128,
  "page": 1,
  "page_size": 20,
  "pages": 7
}
```

**错误响应：**
```json
{
  "error": {
    "code": "VOUCHER_NOT_FOUND",
    "message": "凭证不存在",
    "detail": {}
  }
}
```

### 3.2 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/login | `{username, password}` → `{access_token, refresh_token, user}` |
| POST | /auth/refresh | `{refresh_token}` → `{access_token}` |
| POST | /auth/logout | 注销 refresh token |
| GET | /auth/me | 当前用户信息 |

### 3.3 凭证

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /vouchers | 列表(筛选:date_from,date_to,status,keyword,period_id) |
| POST | /vouchers | 创建凭证 |
| GET | /vouchers/{id} | 凭证详情(含分录+辅助核算) |
| PUT | /vouchers/{id} | 更新凭证(仅草稿) |
| DELETE | /vouchers/{id} | 软删除凭证(仅草稿，设 deleted_at) |
| POST | /vouchers/{id}/audit | 审核 |
| POST | /vouchers/{id}/unaudit | 反审核 |
| POST | /vouchers/{id}/post | 记账 |
| POST | /vouchers/{id}/reverse | 冲销 → 返回新凭证ID |
| GET | /vouchers/{id}/print | 打印数据 |
| POST | /vouchers/import | 批量导入(Excel) |
| GET | /vouchers/export | 批量导出(Excel, 同筛选参数) |

**创建凭证请求：**
```json
{
  "date": "2026-06-13",
  "period_id": "uuid",
  "attachments": 2,
  "entries": [
    {
      "row_number": 1,
      "account_id": "uuid",
      "summary": "支付差旅费",
      "debit_amount": "5000.00",
      "credit_amount": "0",
      "auxiliaries": [
        {"aux_type": "个人", "aux_entity_id": "uuid"}
      ]
    }
  ]
}
```

### 3.4 凭证模板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /voucher-templates | 列表 |
| POST | /voucher-templates | 创建模板 |
| GET | /voucher-templates/{id} | 模板详情 |
| PUT | /voucher-templates/{id} | 更新模板 |
| DELETE | /voucher-templates/{id} | 删除模板 |

### 3.5 科目

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /accounts | 科目列表（树形平铺，parent_id=null 为根） |
| GET | /accounts/tree | 科目树（嵌套 JSON） |
| POST | /accounts | 创建科目 |
| PUT | /accounts/{id} | 更新科目 |
| DELETE | /accounts/{id} | 删除（检查是否有凭证引用） |

### 3.6 账表查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /reports/trial-balance | 科目余额表（period_id, level, include_zero） |
| GET | /reports/general-ledger | 总账（period_id, account_id） |
| GET | /reports/detail-ledger/{account_id} | 三栏明细账（period_id, date_from, date_to） |
| GET | /reports/multi-column-ledger/{account_id} | 多栏明细账 |
| GET | /reports/journal | 序时账（period_id 必选, date_from, date_to） |
| GET | /reports/quantity-ledger/{account_id} | 数量金额账 |

**科目余额表响应：**
```json
{
  "period": {"year": 2026, "month": 6},
  "rows": [
    {
      "account": {"id": "uuid", "code": "1001", "name": "现金", "level": 1},
      "opening_balance": "100000.00",
      "current_debit": "50000.00",
      "current_credit": "30000.00",
      "closing_balance": "120000.00",
      "children": [...]
    }
  ],
  "summary": {
    "total_opening_debit": "...",
    "total_opening_credit": "...",
    "total_current_debit": "...",
    "total_current_credit": "...",
    "total_closing_debit": "...",
    "total_closing_credit": "..."
  }
}
```

### 3.7 财务报表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /statements/balance-sheet | 资产负债表(period_id, template_id) |
| GET | /statements/income | 利润表(period_id, template_id) |
| GET | /statements/cash-flow | 现金流量表(period_id, template_id) |
| GET | /statements/templates | 报表模板列表 |
| POST | /statements/export | 导出报表(body:{type,period_id,format:excel/pdf}) |

**资产负债表响应简化：**
```json
{
  "period": {"year": 2026, "month": 6},
  "template": {"name": "一般企业", "id": "uuid"},
  "sections": [
    {
      "label": "流动资产",
      "items": [
        {"name": "货币资金", "closing": "600000.00", "opening": "450000.00"}
      ],
      "subtotal": {"closing": "720000.00", "opening": "600000.00"}
    }
  ],
  "totals": {
    "assets": {"closing": "970000.00", "opening": "900000.00"},
    "liabilities_equity": {"closing": "970000.00", "opening": "900000.00"}
  }
}
```

### 3.8 期末处理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /periods | 期间列表 |
| GET | /periods/current | 当前打开的会计期间 → `{id, year, month, status}` |
| POST | /periods/{id}/close | 结账 |
| POST | /periods/{id}/reopen | 反结账 |
| GET | /carry-forward/templates | 结转模板列表 |
| POST | /carry-forward/execute | 执行结转 `{period_id, template_ids[]}` |
| GET | /carry-forward/check | AI 检查 `{period_id}` → 10 项检查结果 |
| GET | /periods/{id}/trial-balance | 试算平衡 |

**AI 检查响应：**
```json
{
  "period_id": "uuid",
  "checks": [
    {"id": 1, "name": "未记账凭证", "status": "pass", "detail": "0 条"},
    {"id": 2, "name": "折旧计提", "status": "warn", "detail": "本月未计提折旧"},
    {"id": 3, "name": "暂估清理", "status": "fail", "detail": "3 笔暂估未清理: PO-001, PO-005, PO-012"}
  ],
  "summary": {"pass": 8, "warn": 1, "fail": 1},
  "can_close": false
}
```

### 3.9 辅助核算

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /auxiliaries/{type} | 档案列表 (type: departments/individuals/counterparties/projects) |
| POST | /auxiliaries/{type} | 创建档案 |
| PUT | /auxiliaries/{type}/{id} | 更新 |
| DELETE | /auxiliaries/{type}/{id} | 删除(检查引用) |
| GET | /auxiliaries/{type}/{id}/ledger | 辅助核算明细账 |
| GET | /auxiliaries/{type}/{id}/aging | 账龄分析 |

### 3.10 出纳

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /cash-journals | 现金日记账(account_id, date_from, date_to) |
| POST | /cash-journals | 录入日记账 |
| GET | /bank-journals | 银行日记账 |
| POST | /bank-journals/import | 导入银行流水(Excel) |
| POST | /bank-reconcile | 银行对账(account_id, period_id) |

### 3.11 固定资产

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /fixed-assets | 资产列表(筛选:status,dept_id,category) |
| POST | /fixed-assets | 新增资产 |
| PUT | /fixed-assets/{id} | 变更 |
| POST | /fixed-assets/{id}/depreciate | 单个折旧 |
| POST | /fixed-assets/depreciate-batch | 批量折旧(period_id) |
| POST | /fixed-assets/{id}/dispose | 清理 |
| GET | /fixed-assets/reports | 资产报表(depreciation_summary...) |

### 3.12 AI 模块

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /ai/voucher/generate | NL 生成凭证 `{description, period_id}` |
| POST | /ai/voucher/refine | 修正重生成 `{conversation_id, refinement}` |
| POST | /ai/reports/interpret | 报表解读 `{period_id, report_type}` |
| POST | /ai/period/check | 期末检查 `{period_id}` |
| POST | /ai/query | 自然语言查询 `{question, conversation_id?}` |
| POST | /ai/query/explain | 解释 SQL |

**AI NL→SQL 安全措施：**
- **只读数据库连接**：AI 查询使用独立的 `ai_readonly` PostgreSQL 用户，仅有 SELECT 权限，禁止 DML/DDL。
- **SQL 解析验证**：执行前使用 `sqlparse` 检查，仅允许 SELECT 语句；非 SELECT 直接拒绝（403）。
- **强制 LIMIT**：若 LLM 生成的 SQL 不含 LIMIT，自动追加 `LIMIT 1000`。
- **语句超时**：AI 连接设置 `statement_timeout = 5000`（5 秒），防止失控查询。
- **输入长度**：`question` 最大长度 500 字符（Pydantic `max_length=500`）。

**自然语言生成凭证请求：**
```json
{
  "description": "支付张三差旅费5000元，从工商银行转出",
  "period_id": "uuid"
}
```

**响应：**
```json
{
  "conversation_id": "uuid",
  "entries": [
    {
      "row_number": 1,
      "account": {"id": "uuid", "code": "6602", "name": "差旅费"},
      "summary": "支付差旅费",
      "debit_amount": "5000.00",
      "credit_amount": "0",
      "auxiliaries": [
        {"aux_type": "个人", "entity": {"id": "uuid", "name": "张三"}}
      ]
    },
    {
      "row_number": 2,
      "account": {"id": "uuid", "code": "100201", "name": "银行存款-工商银行"},
      "summary": "支付差旅费",
      "debit_amount": "0",
      "credit_amount": "5000.00",
      "auxiliaries": []
    }
  ],
  "is_balanced": true,
  "matched_accounts": ["差旅费(6602)", "银行存款-工商银行(100201)"],
  "ai_notes": "已将差旅费 5000 元归入科目 6602"
}
```

**自然语言查询响应：**
```json
{
  "conversation_id": "uuid",
  "question": "上个月管理费用超过1万的科目",
  "sql": "SELECT a.code, a.name, SUM(...) ...",
  "columns": ["科目编码", "科目名称", "金额"],
  "rows": [
    ["6602-01", "差旅费", "35000.00"],
    ["6602-02", "办公费", "18000.00"]
  ],
  "row_count": 3,
  "execution_time_ms": 124
}
```

### 3.13 系统管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | /admin/users | 用户管理 |
| PUT/DELETE | /admin/users/{id} | |
| GET/POST | /admin/roles | 角色管理 |
| GET | /admin/audit-logs | 审计日志(筛选:user_id,action,date_from,date_to) |
| POST | /admin/backup | 手动备份 |
| GET | /admin/backups | 备份列表 |
| GET | /admin/params | 系统参数 |
| PUT | /admin/params | 更新参数 |

### 3.14 仪表盘 & 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /dashboard/summary | 仪表盘摘要 `{period_id}` → 凭证状态计数、试算平衡汇总、近期活动 |
| GET | /health | 健康检查 → `{status, db, redis, version}` |

**仪表盘响应：**
```json
{
  "period": {"id": "uuid", "year": 2026, "month": 6},
  "voucher_counts": {"draft": 12, "audited": 45, "posted": 230, "total": 287},
  "trial_balance": {"total_debit": "15420000.00", "total_credit": "15420000.00", "is_balanced": true},
  "recent_activity": [
    {"action": "voucher:post", "voucher_no": "JZ-2026-06-045", "user": "李四", "at": "2026-06-13T14:30:00Z"}
  ]
}
```

---

## 4. API 中间件栈

```
Request → CORS → CorrelationID → RateLimiter → Auth(JWT) → RBAC(permission_check)
        → AuditLog(middleware) → Router → Service → DB
```

- **CorrelationID**：每个请求注入 `X-Correlation-ID`（UUID），贯穿日志和错误响应。
- **RateLimiter**：60 req/min 全局，AI 接口 10 req/min；认证接口 5 req/min/IP。
- **RBAC**：装饰器 `@require_role("finance_manager")` / `@require_permission("voucher:audit")`
- **AuditLog**：监听 SQLAlchemy after_flush 事件，记录 INSERT/UPDATE/DELETE
- **AI 只读 DB**：AI NL→SQL 路径使用独立 `ai_readonly` 数据库连接，`statement_timeout=5s`，仅 SELECT。
```python
# SQL 验证（AI 查询路径）
import sqlparse

def validate_readonly_sql(sql: str) -> bool:
    """仅允许 SELECT 语句，拒绝任何 DML/DDL。"""
    statements = sqlparse.parse(sql)
    for stmt in statements:
        if stmt.get_type() != 'SELECT':
            raise ReadOnlyViolation(f"Only SELECT allowed, got {stmt.get_type()}")
    # 自动追加 LIMIT
    if 'LIMIT' not in sql.upper():
        sql += ' LIMIT 1000'
    return True
```

---

## 5. 前端组件规格

### 5.1 目录结构（实现级）

```
frontend/src/
├── main.tsx                          # ReactDOM.createRoot
├── App.tsx                           # QueryClientProvider + RouterProvider
├── routes/
│   ├── __root.tsx                    # 根布局（Header+Sidebar+Content）
│   ├── index.tsx                     # → 重定向 /dashboard
│   ├── dashboard.tsx                 # 首页仪表盘
│   ├── vouchers.tsx                  # 凭证路由组
│   ├── ledgers.tsx                   # 账表路由组
│   ├── auxiliary.tsx                 # 辅助核算路由组
│   ├── reports.tsx                   # 报表路由组
│   ├── period.tsx                    # 期末处理路由组
│   ├── cashier.tsx                   # 出纳路由组
│   ├── assets.tsx                    # 固定资产路由组
│   ├── ai.tsx                        # AI 工作台
│   └── admin.tsx                     # 系统管理路由组
├── features/
│   ├── vouchers/
│   │   ├── VoucherList.tsx           # 凭证列表页
│   │   ├── VoucherForm.tsx           # 凭证录入页
│   │   ├── VoucherDetail.tsx         # 凭证详情（滑出面板）
│   │   ├── VoucherTemplateList.tsx   # 模板列表
│   │   ├── VoucherTemplateForm.tsx   # 模板编辑
│   │   ├── VoucherImport.tsx         # 导入对话框
│   │   └── useVouchers.ts           # TanStack Query hooks
│   ├── ledgers/
│   │   ├── TrialBalance.tsx          # 科目余额表
│   │   ├── GeneralLedger.tsx         # 总账
│   │   ├── DetailLedger.tsx          # 三栏明细账
│   │   ├── MultiColumnLedger.tsx     # 多栏明细账
│   │   ├── JournalLedger.tsx         # 序时账
│   │   └── QuantityLedger.tsx        # 数量金额账
│   ├── auxiliary/
│   │   ├── AuxList.tsx               # 档案列表（通用组件，按 type 切换）
│   │   ├── AuxLedger.tsx             # 辅助核算明细账
│   │   └── AgingAnalysis.tsx         # 账龄分析
│   ├── reports/
│   │   ├── BalanceSheet.tsx          # 资产负债表
│   │   ├── IncomeStatement.tsx       # 利润表
│   │   ├── CashFlowStatement.tsx     # 现金流量表
│   │   └── ReportTemplateManager.tsx # 模板管理
│   ├── period/
│   │   ├── PeriodClose.tsx           # 结账/反结账
│   │   └── CarryForward.tsx          # 期末结转
│   ├── cashier/
│   │   ├── CashJournal.tsx           # 现金日记账
│   │   ├── BankJournal.tsx           # 银行日记账
│   │   └── BankReconcile.tsx         # 银行对账
│   ├── assets/
│   │   ├── AssetList.tsx             # 资产列表
│   │   ├── AssetForm.tsx             # 新增/编辑资产
│   │   └── AssetReports.tsx          # 资产报表
│   ├── ai/
│   │   ├── AIWorkspace.tsx           # AI 工作台主界面
│   │   ├── AIVoucherGenerator.tsx    # 智能凭证
│   │   ├── AIReportInterpreter.tsx   # 报表解读
│   │   ├── AIPeriodChecker.tsx       # 期末检查
│   │   ├── AINLQuery.tsx             # 自然语言查询
│   │   └── AIChatPanel.tsx           # 全局浮动 AI 面板
│   └── admin/
│       ├── AccountManage.tsx         # 科目管理
│       ├── AccountTreeEditor.tsx     # 科目树编辑器
│       ├── UserManage.tsx            # 用户管理
│       ├── RoleManage.tsx            # 角色权限
│       ├── PeriodManage.tsx          # 会计期间
│       ├── ParamsManage.tsx          # 系统参数
│       ├── AuditLogViewer.tsx        # 审计日志
│       └── BackupManage.tsx          # 数据备份
├── components/
│   ├── ui/                           # Shadcn/ui 原子组件
│   │   ├── button.tsx, input.tsx, select.tsx, dialog.tsx...
│   ├── layout/
│   │   ├── AppShell.tsx              # 全局布局
│   │   ├── Sidebar.tsx               # 侧边栏 + 菜单
│   │   ├── Header.tsx                # 顶部栏
│   │   └── Breadcrumb.tsx
│   ├── DataTable/
│   │   ├── DataTable.tsx             # 通用表格组件
│   │   ├── DataTablePagination.tsx
│   │   ├── DataTableToolbar.tsx      # 筛选 + 导出按钮
│   │   └── columns.tsx               # 列定义 helper
│   ├── AccountPicker.tsx             # 科目选择器（弹出树）
│   ├── AuxPicker.tsx                 # 辅助核算选择器
│   ├── PeriodPicker.tsx              # 会计期间下拉
│   ├── AmountInput.tsx               # 金额输入（千分位+右对齐）
│   ├── BalanceBar.tsx                # 借贷平衡指示器
│   ├── StatusBadge.tsx               # 状态标签（带颜色）
│   ├── EmptyState.tsx                # 空状态组件
│   ├── ErrorCard.tsx                 # 错误重试组件
│   ├── Skeleton.tsx                  # 骨架屏
│   ├── Toast.tsx                     # Toast 通知
│   └── ConfirmDialog.tsx             # 确认删除对话框
├── hooks/
│   ├── useAuth.ts                    # 认证状态
│   ├── useCurrentPeriod.ts           # 当前会计期间
│   └── usePermission.ts              # 权限检查
├── lib/
│   ├── api.ts                        # Axios 实例（baseURL, interceptor）
│   ├── constants.ts                  # 常量
│   └── utils.ts                      # 格式化(千分位/日期)、四舍五入
├── stores/
│   ├── appStore.ts                   # Zustand: sidebar, currentPeriod
│   └── userStore.ts                  # user info
└── types/
    ├── voucher.ts                    # Voucher, VoucherEntry, VoucherTemplate...
    ├── account.ts                    # Account, AccountTree...
    ├── report.ts                     # TrialBalance, BalanceSheet...
    └── api.ts                        # PaginatedResponse<T>, ErrorResponse
```

### 5.2 核心组件接口

```typescript
// DataTable 泛型组件
interface DataTableProps<T> {
  columns: ColumnDef<T>[];           // TanStack Table 列定义
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  onPaginationChange: (page: number, pageSize: number) => void;
  onSortChange?: (sort: string, order: string) => void;
  isLoading?: boolean;
  toolbar?: React.ReactNode;         // 筛选栏渲染
  rowActions?: (row: T) => React.ReactNode;
  onRowClick?: (row: T) => void;
  selectable?: boolean;
  selectedRows?: string[];
  onSelectionChange?: (ids: string[]) => void;
  footer?: React.ReactNode;          // 合计行
}

// AccountPicker 科目选择器
interface AccountPickerProps {
  value?: string;                    // account_id
  onChange: (account: Account) => void;
  disabled?: boolean;
  excludeIds?: string[];             // 排除的科目
  filter?: (account: Account) => boolean;
}

// BalanceBar 平衡指示器
interface BalanceBarProps {
  totalDebit: number;
  totalCredit: number;
}

// VoucherForm 凭证表单
interface VoucherFormProps {
  initialData?: Voucher;             // 编辑模式
  onSave: (data: CreateVoucherRequest) => Promise<void>;
}

// 凭证分录行组
interface EntryRow {
  id: string;
  accountId: string;
  accountCode?: string;
  accountName?: string;
  summary: string;
  debitAmount: string;
  creditAmount: string;
  auxiliaries: AuxiliaryRef[];
  quantity?: string;
  price?: string;
}
```

### 5.3 路由与权限守卫

```typescript
// TanStack Router 路由定义（关键路由）
const routeTree = rootRoute.addChildren([
  // 公开路由
  loginRoute,
  // 受保护路由组
  authenticatedRoute.addChildren([
    dashboardRoute,
    vouchersRoute.addChildren([
      voucherListRoute,
      voucherNewRoute,
      voucherDetailRoute,
      voucherTemplatesRoute,
    ]),
    ledgersRoute.addChildren([...]),
    reportsRoute.addChildren([...]),
    periodRoute.addChildren([...]),
    cashierRoute.addChildren([...]),
    assetsRoute.addChildren([...]),
    aiRoute.addChildren([...]),
    // 管理员专属
    adminRoute.addChildren([...]),   // beforeLoad: check role==='admin'
  ]),
]);
```

**权限检查模式：**
```typescript
// 路由级
beforeLoad: ({ context }) => {
  if (!context.auth.isAuthenticated) throw redirect({ to: '/login' });
}

// 组件级
function AuditButton({ voucherId }: { voucherId: string }) {
  const { can } = usePermission();
  if (!can('voucher:audit')) return null;
  return <Button onClick={() => auditVoucher(voucherId)}>审核</Button>;
}
```

---

## 6. 状态管理细节

### TanStack Query Key 规范

```typescript
// 凭证列表
['vouchers', { page, pageSize, status, dateFrom, dateTo, keyword }]
// 凭证详情
['voucher', voucherId]
// 科目树
['accounts', 'tree']
// 科目余额表
['trial-balance', { periodId, level }]
// 结转模板
['carry-templates']
// AI 检查
['period-check', periodId]
```

**缓存策略：**
- 列表类：staleTime 30s
- 科目树/结转模板：staleTime 5min（变化极少）
- 余额/报表：staleTime 0（写操作后手动 invalidate）

### Zustand Store

```typescript
interface AppStore {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  currentPeriod: { id: string; year: number; month: number } | null;
  setCurrentPeriod: (period: Period) => void;
}

interface UserStore {
  user: User | null;
  permissions: Set<string>;
  setUser: (user: User) => void;
  logout: () => void;
  can: (permission: string) => boolean;
}
```

---

## 7. 关键业务逻辑伪码

### 7.1 凭证记账

```python
async def post_voucher(voucher_id: UUID) -> Voucher:
    voucher = await get_voucher(voucher_id)
    assert voucher.status == "audited"
    
    async with db.transaction():
        # 1. 检查期间未结账（行锁防并发关账）
        period = await db.execute(
            select(Period).where(Period.id == voucher.period_id).with_for_update()
        )
        period = period.scalar_one()
        assert period.status == "open"
        
        # 2. 更新凭证状态
        voucher.status = "posted"
        voucher.posted_at = utcnow()
        
        # 3. 按科目聚合分录金额（减少余额行锁竞争）
        account_totals = {}
        for entry in voucher.entries:
            key = entry.account_id
            if key not in account_totals:
                account_totals[key] = {"debit": 0, "credit": 0, "dc_type": entry.account.dc_type}
            account_totals[key]["debit"] += entry.debit_amount
            account_totals[key]["credit"] += entry.credit_amount
        
        # 4. 逐科目更新余额快照（SELECT FOR UPDATE 防并发写）
        for account_id, totals in account_totals.items():
            balance = await db.execute(
                select(AccountBalance)
                .where(AccountBalance.period_id == period.id, AccountBalance.account_id == account_id)
                .with_for_update()
            )
            balance = balance.scalar_one_or_none()
            if not balance:
                balance = AccountBalance(period_id=period.id, account_id=account_id)
                db.add(balance)
            
            # 更新本期发生额
            balance.current_debit += totals["debit"]
            balance.current_credit += totals["credit"]
            
            # 计算期末余额（方向敏感性）
            if totals["dc_type"] == "D":
                balance.closing_debit = (
                    balance.opening_debit + balance.current_debit - balance.current_credit
                )
                balance.closing_credit = 0
            else:  # dc_type == "C"
                balance.closing_credit = (
                    balance.opening_credit + balance.current_credit - balance.current_debit
                )
                balance.closing_debit = 0
        
        # 5. 写入审计日志
        await audit("voucher:post", voucher_id)
    
    # 6. 失效相关缓存
    await cache.delete_pattern(f"trial-balance:{period.id}*")
    return voucher
```

### 7.2 科目余额表查询

```python
async def get_trial_balance(period_id: UUID, level: int = None) -> TrialBalance:
    # 从快照表查询 + Redis 缓存
    cache_key = f"trial-balance:{period_id}:{level}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    balances = await db.query(AccountBalance).filter_by(period_id=period_id).all()
    accounts = await db.query(Account).filter(Account.is_enabled == True).all()
    
    # 构建树形结构
    tree = build_account_tree(accounts, balances, level)
    
    result = {"period": await get_period(period_id), "rows": tree}
    await redis.set(cache_key, json.dumps(result), ex=300)
    return result
```

### 7.3 AI 凭证生成

```python
async def generate_voucher(description: str, period_id: UUID) -> AIVoucherResponse:
    # 1. 获取上下文 — 相关性过滤，不全量发送科目表
    #    策略：仅发送末级科目（无子节点）+ 高频使用科目
    leaf_accounts = await get_leaf_accounts(enabled_only=True)
    frequent_accounts = await get_frequent_accounts(period_id, top_n=50)
    accounts = merge_and_dedupe(leaf_accounts, frequent_accounts)
    
    #    辅助核算档案（量小，全量发送）
    aux_entities = await get_all_auxiliaries()
    
    # 2. 构建压缩上下文提示词
    prompt = build_compressed_prompt(description, accounts, aux_entities)
    
    # 3. 调用 LLM（结构化输出，JSON mode）
    response = await llm.invoke(
        prompt,
        response_format={"type": "json_object"}  # 强制 JSON
    )
    parsed = parse_and_validate_entries(response, accounts)
    
    # 4. 校验：科目必须存在于上下文列表中
    invalid = [e.account_id for e in parsed.entries if e.account_id not in account_ids]
    if invalid:
        raise AIGenerationError(f"LLM 返回不存在的科目: {invalid}")
    
    # 5. 平衡校验 + 自动修正（最多重试一次）
    total_debit = sum(e.debit_amount for e in parsed.entries)
    total_credit = sum(e.credit_amount for e in parsed.entries)
    
    if abs(total_debit - total_credit) > 0.01:
        fix_prompt = build_fix_prompt(description, parsed, total_debit, total_credit, accounts)
        response = await llm.invoke(fix_prompt, response_format={"type": "json_object"})
        parsed = parse_and_validate_entries(response, accounts)
    
    # 6. 保存对话记录
    conversation_id = uuid4()
    await save_conversation(conversation_id, description, parsed)
    
    return AIVoucherResponse(
        conversation_id=conversation_id,
        entries=parsed.entries,
        is_balanced=True,
        matched_accounts=parsed.matches,
    )
```

### 7.4 期末结转执行

```python
async def execute_carry_forward(period_id: UUID, template_ids: list[UUID]) -> CarryForwardResult:
    period = await get_period(period_id)
    assert period.status == "open"
    
    # 1. 预检（AI 10 项）
    checks = await run_period_checks(period_id)
    if any(c.status == "fail" for c in checks):
        raise CarryForwardError("检查未通过", checks)
    
    results = []
    async with db.transaction():
        for tid in template_ids:
            template = await get_template(tid)
            # 2. 按规则计算结转金额
            entries = await calculate_carry_entries(template, period_id)
            # 3. 自动生成结转凭证（system_user）
            voucher = await create_voucher(period_id, "carry_forward", entries,
                                           creator_id=SYSTEM_USER_ID)
            # 4. 自动审核+记账
            await audit_voucher(voucher.id, auditor_id=SYSTEM_USER_ID)
            await post_voucher(voucher.id)
            # 5. 记录结转
            await create_carry_record(period_id, tid, voucher.id, entries)
            results.append({"template": template.name, "voucher_no": voucher.voucher_no})
    
    # 失效缓存
    await cache.delete_pattern(f"trial-balance:{period_id}*")
    
    return CarryForwardResult(executed=len(results), details=results)


async def close_period(period_id: UUID) -> Period:
    """结账：结转执行后，初始化下期科目余额。"""
    async with db.transaction():
        # 1. 行锁 — 防止并发结账
        period = await db.execute(
            select(Period).where(Period.id == period_id).with_for_update()
        )
        period = period.scalar_one()
        if period.status == "closed":
            raise PeriodAlreadyClosed()
        
        # 2. 校验：本期所有已审核凭证均已记账
        unaudited = await count_vouchers(period_id, status="audited")
        if unaudited > 0:
            raise PeriodCloseError(f"存在 {unaudited} 张已审核未记账凭证")
        
        # 3. 将本期期末余额 → 下期期初余额
        next_period = await get_or_create_period(period.year, period.month + 1)
        balances = await db.execute(
            select(AccountBalance).where(AccountBalance.period_id == period_id)
        )
        for balance in balances.scalars():
            next_balance = AccountBalance(
                period_id=next_period.id,
                account_id=balance.account_id,
                opening_debit=balance.closing_debit,
                opening_credit=balance.closing_credit,
                current_debit=0,
                current_credit=0,
                closing_debit=balance.closing_debit,
                closing_credit=balance.closing_credit,
            )
            db.add(next_balance)
        
        # 4. 标记结账
        period.status = "closed"
        period.closed_at = utcnow()
        
        await audit("period:close", period_id)
    
    return period
```

---

## 8. 测试策略

### 后端

```
tests/
├── conftest.py             # fixtures: test_db, client, auth_headers
├── unit/
│   ├── test_voucher_service.py
│   ├── test_ledger_service.py
│   ├── test_period_service.py
│   └── test_ai_service.py  # mock LLM
├── integration/
│   ├── test_api_vouchers.py
│   ├── test_api_ledgers.py
│   ├── test_api_reports.py
│   ├── test_api_ai.py
│   └── test_auth.py
└── factories/              # factory_boy fixtures
    ├── account.py
    ├── voucher.py
    └── user.py
```

**覆盖率目标**：services ≥ 80%, API routes ≥ 70%

### 前端

```
frontend/src/__tests__/
├── setup.ts
├── components/
│   ├── DataTable.test.tsx       # vitest + @testing-library/react
│   ├── AccountPicker.test.tsx
│   └── VoucherForm.test.tsx     # 凭证录入核心交互测试
├── hooks/
│   └── useVouchers.test.ts
└── e2e/                         # Playwright
    ├── voucher-flow.spec.ts     # 录入→审核→记账→查询完整流程
    ├── ledger-flow.spec.ts      # 余额表→联查明细账
    ├── period-close.spec.ts     # 结转→结账
    └── ai-voucher.spec.ts       # AI 凭证生成
```

**前端测试重点**：
- 凭证录入表单（借贷平衡校验、辅助核算关联）
- DataTable 通用组件（排序/筛选/分页/选择）
- AI 对话组件（流式响应渲染）

---

## 9. 实施计划与任务拆解

### Phase 1: 脚手架 (Week 1)

- [ ] `P1.1` 初始化 monorepo：backend + frontend + docker-compose
- [ ] `P1.2` 后端 FastAPI 骨架：config / models / alembic 初迁移
- [ ] `P1.3` 前端 Vite 骨架：Tailwind / Shadcn / TanStack Router / Query 配置
- [ ] `P1.4` 认证模块：JWT login/refresh/logout + 前端 LoginPage
- [ ] `P1.5` 全局布局：AppShell / Sidebar / Header

### Phase 2: 系统管理 (Week 2-3)

- [ ] `P2.1` 科目管理 CRUD + 树形编辑器
- [ ] `P2.2` 用户/角色/权限 CRUD + RBAC 中间件
- [ ] `P2.3` 会计期间管理
- [ ] `P2.4` 系统参数
- [ ] `P2.5` 审计日志查看器

### Phase 3: 凭证管理 (Week 4-6)

- [ ] `P3.1` 凭证录入页（分录表格 + 科目选择器 + 辅助核算 + 平衡指示器 + 快捷键）
- [ ] `P3.2` 凭证列表页（筛选 + 排序 + 分页 + 状态标签 + 批量操作）
- [ ] `P3.3` 凭证审核流程
- [ ] `P3.4` 凭证记账 + 余额快照更新
- [ ] `P3.5` 凭证冲销
- [ ] `P3.6` 凭证模板 CRUD
- [ ] `P3.7` 凭证导入导出（Excel）

### Phase 4: 账表查询 (Week 7-8)

- [ ] `P4.1` 科目余额表（树形展开 + 多期对比 + 缓存）
- [ ] `P4.2` 总账
- [ ] `P4.3` 三栏明细账 + 联查凭证
- [ ] `P4.4` 多栏明细账（动态列）
- [ ] `P4.5` 序时账
- [ ] `P4.6` 数量金额账

### Phase 5: 辅助核算 + 出纳 + 固定资产 (Week 9-11)

- [ ] `P5.1` 辅助核算档案管理（四类型通用组件）
- [ ] `P5.2` 辅助核算明细账 + 账龄分析
- [ ] `P5.3` 现金日记账
- [ ] `P5.4` 银行日记账 + 流水导入
- [ ] `P5.5` 银行对账
- [ ] `P5.6` 固定资产卡片 + 折旧（3 种方法）
- [ ] `P5.7` 资产变更/清理
- [ ] `P5.8` 固定资产报表

### Phase 6: 财务报表 (Week 12-13)

- [ ] `P6.1` 资产负债表（模板渲染 + 分级展开）
- [ ] `P6.2` 利润表
- [ ] `P6.3` 现金流量表
- [ ] `P6.4` 报表模板管理
- [ ] `P6.5` 导出 Excel/PDF

### Phase 7: 期末处理 (Week 14-15)

- [ ] `P7.1` 结转模板配置 + 规则引擎
- [ ] `P7.2` 试算平衡
- [ ] `P7.3` 期末结转执行（12+ 模板，一键执行 + 进度）
- [ ] `P7.4` 结账/反结账

### Phase 8: AI 模块 (Week 16-18)

- [ ] `P8.1` LLM Client 封装（LangChain + OpenAI/DeepSeek）
- [ ] `P8.2` 自然语言生成凭证（科目匹配 + 平衡校验 + 修正）
- [ ] `P8.3` AI 凭证生成前端（描述输入 → 预览编辑 → 确认）
- [ ] `P8.4` 报表解读（三表 + 同比环比 + 风险提示）
- [ ] `P8.5` 期末检查（10 项自动检查）
- [ ] `P8.6` 自然语言查询（NL→SQL + 只读执行 + 连续追问）
- [ ] `P8.7` AI 工作台前端（卡片入口 + 对话面板）

### Phase 9: 测试 + 优化 + 部署 (Week 19-20)

- [ ] `P9.1` 集成测试补充
- [ ] `P9.2` E2E 测试（核心流程）
- [ ] `P9.3` 性能优化（慢查询分析、缓存策略）
- [ ] `P9.4` Docker 部署配置（Nginx + FastAPI + Celery + DB + Redis）
- [ ] `P9.5` 文档完善 + README

---

## 10. 文档索引

| 文档 | 内容 |
|------|------|
| `document/summary-design.md` | 技术设计摘要 |
| `document/summary-ux.md` | UX 设计摘要 |
| `document/design.md` | 完整技术设计 |
| `document/ux-design.md` | 完整 UX 设计 |
| `document/engineering-spec.md` | 本文档：实施工程规格 |

---

*文档版本：v0.2 | 日期：2026-06-13*

---

## 附录 A：错误代码目录

| HTTP | 错误码 | 说明 |
|------|--------|------|
| 400 | `VALIDATION_ERROR` | 请求参数校验失败（Pydantic） |
| 401 | `UNAUTHORIZED` | 未认证或 token 过期 |
| 403 | `INSUFFICIENT_PERMISSIONS` | 权限不足 |
| 403 | `AI_READONLY_VIOLATION` | AI 查询包含非 SELECT 语句 |
| 404 | `VOUCHER_NOT_FOUND` | 凭证不存在 |
| 404 | `ACCOUNT_NOT_FOUND` | 科目不存在 |
| 404 | `PERIOD_NOT_FOUND` | 会计期间不存在 |
| 404 | `TEMPLATE_NOT_FOUND` | 模板不存在 |
| 409 | `VOUCHER_NOT_DRAFT` | 凭证非草稿状态，不可编辑 |
| 409 | `VOUCHER_ALREADY_POSTED` | 凭证已记账，不可重复操作 |
| 409 | `PERIOD_CLOSED` | 期间已结账，不可操作 |
| 409 | `PERIOD_ALREADY_CLOSED` | 期间已结账，不可重复结账 |
| 409 | `UNBALANCED_VOUCHER` | 凭证借贷不平衡 |
| 409 | `ACCOUNT_HAS_VOUCHERS` | 科目存在凭证引用，不可删除 |
| 422 | `UNBALANCED_ENTRIES` | 分录借贷合计不相等 |
| 429 | `RATE_LIMITED` | 请求频率超限 |
| 429 | `AI_RATE_LIMITED` | AI 接口请求频率超限 |
| 500 | `INTERNAL_ERROR` | 服务器内部错误 |
| 502 | `AI_GENERATION_FAILED` | LLM 生成失败（超时/服务不可用） |
| 502 | `AI_INVALID_RESPONSE` | LLM 返回格式不符预期 |
| 503 | `SERVICE_UNAVAILABLE` | 依赖服务不可用（DB/Redis） |
