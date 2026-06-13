# Backend Architect Review — Core Accounting v1

> Review of `engineering-spec.md` (v0.1, 2026-06-13)
> Cross-referenced against `design.md` and `summary-design.md`
> Reviewer: Backend Architect Agent | Date: 2026-06-13

---

## Executive Summary

The engineering spec is solid for a greenfield internal accounting system. The architecture (FastAPI + SQLAlchemy async + PostgreSQL + React/TanStack) is well-chosen for the 9-module scope. The voucher→entry→auxiliary model correctly implements Chinese-style double-entry bookkeeping. Major concerns are: **(1) missing database indexes will cause query degradation at moderate scale**, **(2) the AI NL→SQL execution path lacks mandatory read-only enforcement**, **(3) the balance snapshot update logic in §7.1 is incomplete for credit-natured accounts**, and **(4) the `entry_auxiliaries` polymorphic FK design is ambiguous and needs resolution**. Below is the detailed analysis.

---

## 1. Database Schema Review

### 1.1 Double-Entry Accounting Correctness

**Voucher Entry Model (§2.3) — Generally Correct**

The XOR constraint design is sound:
```
CHECK (debit_amount = 0 OR credit_amount = 0)   -- at most one non-zero
CHECK (debit_amount > 0 OR credit_amount > 0)   -- at least one non-zero
```
Combined, these enforce that exactly one of `debit_amount` or `credit_amount` is non-zero — this is the standard Chinese accounting convention (each line is either a debit or a credit, never both).

**Issue 1.1.1** — These two CHECK constraints can be consolidated into one for clarity and slight performance gain:
```sql
ALTER TABLE voucher_entries ADD CONSTRAINT ck_entry_xor
  CHECK ((debit_amount = 0 AND credit_amount > 0) OR (debit_amount > 0 AND credit_amount = 0));
```

**Issue 1.1.2** — Voucher-level balancing is NOT enforced at the database level. There is no DB constraint ensuring Σ(debit) = Σ(credit) within a voucher. The spec relies on application logic (§7.1) for this check, which is correct for an accounting system (you don't want a rigid DB constraint during draft editing), but there should be a DB-level trigger or check on `status = 'posted'` to guarantee that no unbalanced voucher is ever posted. **Recommend:** Add a deferred constraint or an application-level invariant enforced inside the `post_voucher` transaction.

**Account Balance Snapshot (§2.9) — Needs Opening Balance Direction Clarification**

The `account_balances` table has both `opening_debit` and `opening_credit` per account per period. In Chinese accounting, an account's opening balance is directional: it is either a debit or a credit, never both (except for dual-nature accounts which are rare). Having both columns is workable but introduces a risk of inconsistent data (e.g., both opening_debit=1000 and opening_credit=500 on the same account). 

**Issue 1.2.1** — The UNIQUE(period_id, account_id) constraint is correct but doesn't prevent double-opening. **Recommend:** Add a CHECK constraint: `CHECK (opening_debit = 0 OR opening_credit = 0)`.

**Issue 1.2.2** — The same applies to `closing_debit`/`closing_credit`. A properly maintained balance should have only one non-zero closing amount per account. Add: `CHECK (closing_debit = 0 OR closing_credit = 0)`.

**Issue 1.2.3** — The spec does not define the initialization process for balance rows. When a new account is created mid-period, a balance row with zeros should be created for remaining open periods. This is NOT specified.

### 1.2 Critical Missing Indexes

The engineering spec defines tables but omits all index declarations. Below are the indexes required for production performance. Without them, queries like "all entries for account X" or "all vouchers in period Y" will perform full table scans.

| Table | Index | Rationale |
|-------|-------|-----------|
| `voucher_entries` | `(account_id)` | Detail ledger queries: `WHERE account_id = ?` — **highest priority** |
| `voucher_entries` | `(voucher_id)` | Fetch all entries for a voucher. FK does NOT auto-create index in PostgreSQL. |
| `voucher_entries` | `(account_id, voucher_id)` | Covering index for ledger→voucher drill-down |
| `vouchers` | `(period_id, status)` | Core filter: "all posted vouchers in period" |
| `vouchers` | `(date)` | Date-range filtering |
| `vouchers` | `(status, date)` | List by status sorted by date |
| `vouchers` | `(voucher_no)` | UNIQUE constraint creates implicit index — good |
| `account_balances` | `(period_id, account_id)` | Created implicitly via UNIQUE — good |
| `account_balances` | `(period_id)` standalone | Trial balance fetches all balances for a period; the UNIQUE index may not serve this efficiently if account_id is the leading column in some index implementations. Verify execution plan. |
| `entry_auxiliaries` | `(entry_id)` | FK lookup — not auto-indexed in PostgreSQL |
| `entry_auxiliaries` | `(aux_type, aux_entity_id)` | Auxiliary ledger queries |
| `audit_logs` | `(created_at DESC)` | Chronological log browsing |
| `audit_logs` | `(resource_type, resource_id)` | "Show all changes to voucher X" |
| `audit_logs` | `(user_id, created_at)` | Per-user audit trails |
| `cash_journals` | `(account_id, date)` | Cash diary lookups |
| `bank_journals` | `(account_id, date)` | Bank diary lookups |
| `fixed_assets` | `(dept_id, status)` | Departmental asset queries |
| `fixed_assets` | `(status)` | Filter by in_use/disposed |
| `carry_forwards` | `(period_id)` | "All carry-forwards done this period" |
| `carry_templates` | `(sort_order)` | Ordered execution |

**Recommended DDL additions** to the engineering spec §2:
```sql
-- Voucher entries (CRITICAL)
CREATE INDEX idx_voucher_entries_account ON voucher_entries(account_id);
CREATE INDEX idx_voucher_entries_voucher ON voucher_entries(voucher_id);
CREATE INDEX idx_voucher_entries_account_voucher ON voucher_entries(account_id, voucher_id);

-- Vouchers
CREATE INDEX idx_vouchers_period_status ON vouchers(period_id, status);
CREATE INDEX idx_vouchers_date ON vouchers(date);
CREATE INDEX idx_vouchers_status_date ON vouchers(status, date);

-- Entry auxiliaries
CREATE INDEX idx_entry_aux_entry ON entry_auxiliaries(entry_id);
CREATE INDEX idx_entry_aux_type_entity ON entry_auxiliaries(aux_type, aux_entity_id);

-- Audit logs (for fast pagination)
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- Cash/Bank journals
CREATE INDEX idx_cash_journals_account_date ON cash_journals(account_id, date);
CREATE INDEX idx_bank_journals_account_date ON bank_journals(account_id, date);

-- Fixed assets
CREATE INDEX idx_fixed_assets_dept_status ON fixed_assets(dept_id, status);

-- Carry forwards
CREATE INDEX idx_carry_forwards_period ON carry_forwards(period_id);
```

### 1.3 Missing Tables, Columns, and Constraints

**Issue 1.3.1 — Polymorphic FK in `entry_auxiliaries` is ambiguous (§2.4)**

The spec states:
```
aux_entity_id | UUID | FK→对应档案表
```
"对应档案表" (the corresponding archive table) is ambiguous — a single column cannot FK-reference four different tables. There are two standard solutions:

**Option A — Separate nullable columns (recommended for accounting):**
```sql
department_id UUID REFERENCES departments(id),
individual_id UUID REFERENCES individuals(id),
counterparty_id UUID REFERENCES counterparties(id),
project_id UUID REFERENCES projects(id),
-- CHECK exactly one is non-null
CHECK (
  (CASE WHEN department_id IS NOT NULL THEN 1 ELSE 0 END +
   CASE WHEN individual_id IS NOT NULL THEN 1 ELSE 0 END +
   CASE WHEN counterparty_id IS NOT NULL THEN 1 ELSE 0 END +
   CASE WHEN project_id IS NOT NULL THEN 1 ELSE 0 END) = 1
)
```
This preserves referential integrity and is self-documenting.

**Option B — Polymorphic association (less type-safe):**
```sql
aux_entity_type VARCHAR(20),  -- 'department'|'individual'|'counterparty'|'project'
aux_entity_id UUID,           -- no FK constraint possible
```
Option B loses referential integrity guarantees. **Strongly recommend Option A.**

**Issue 1.3.2 — Missing `voucher_reversals` or `reversed_voucher_id`**

The `POST /vouchers/{id}/reverse` endpoint (§3.3) creates a new voucher but the schema has no column tracking which voucher reverses which. Critical for audit trails. **Recommend** adding to `vouchers`:
```sql
reversed_voucher_id UUID REFERENCES vouchers(id) NULL,
reversal_type VARCHAR(20) NULL,  -- 'full' | 'partial'
```

**Issue 1.3.3 — Missing `voucher_entries.updated_at`**

Only `vouchers` has timestamps, but entries can be updated during draft editing. Every table should have `created_at` and `updated_at` for auditability. **Recommend** adding `updated_at TIMESTAMPTZ` to `voucher_entries`, `entry_auxiliaries`, and all auxiliary archive tables.

**Issue 1.3.4 — Missing `currency` support**

Even for an internal system ("内账"), a currency column is future-proofing that adds minimal overhead:
```sql
currency CHAR(3) DEFAULT 'CNY'
```
Adding it to vouchers/entries/balances now avoids a painful migration later.

**Issue 1.3.5 — Missing fiscal year boundary definition**

`periods` has year/month but no concept of fiscal year start/end. If the organization's fiscal year differs from calendar year (e.g., April–March), the carry-forward logic needs to know which periods form a fiscal year. **Recommend** a `fiscal_years` table:
```sql
fiscal_years: id, name, start_month, end_month, is_active
```

**Issue 1.3.6 — Missing chart of accounts versioning**

When the chart of accounts changes (accounts added, renamed, disabled), there is no way to know what the chart looked like at the time a historical voucher was created. This affects audit and reconciliation. **Options:**
- Add `valid_from`/`valid_to` to accounts (temporal table)
- Snapshot the account tree per period (simpler)
- At minimum: log account changes to audit_log

**Issue 1.3.7 — Missing `period_id` on `cash_journals` and `bank_journals`**

These tables have `date` but no `period_id`. For period-based reporting and close validation, each diary entry should be associated with a period. **Recommend** adding `period_id UUID REFERENCES periods(id)`.

### 1.4 Data Integrity Concerns

**Cascading Deletes (§2.3) — Dangerous for Financial Data**

`voucher_id UUID FK→vouchers.id, CASCADE` on `voucher_entries` means deleting a voucher cascades to entries and (via `entry_auxiliaries` CASCADE) to auxiliary associations. Financial records should **never be physically deleted** except in draft state. The DELETE endpoint (§3.3) already restricts deletion to drafts, but the CASCADE constraint is still present at the DB level and could be triggered by a bug or direct DB access.

**Recommendation:**
1. Remove CASCADE from `voucher_entries` → use `ON DELETE RESTRICT`
2. Implement logical deletion only — add `deleted_at` to `vouchers`
3. If drafts must be deletable, handle it in application code with explicit FK ordering

**Foreign Key Completeness:**
- `voucher_entries.account_id → accounts.id`: No ON DELETE specified. Should be `ON DELETE RESTRICT` (never delete an account that has vouchers).
- `vouchers.creator_id → users.id`: What happens when a user is deleted? Should be `ON DELETE SET NULL` or `RESTRICT`.
- `vouchers.auditor_id → users.id`: Same concern.
- The spec doesn't specify ON DELETE behavior for most FKs. This should be explicit.

---

## 2. API Design Review

### 2.1 RESTful Convention Adherence

The API generally follows RESTful conventions well:
- Resource-oriented URLs (`/vouchers`, `/accounts`, `/periods`)
- Standard HTTP methods (GET/POST/PUT/DELETE)
- Nested action endpoints for state transitions (`POST /vouchers/{id}/audit`, `POST /vouchers/{id}/post`)

**Issue 2.1.1 — Action endpoints use POST, which is acceptable but could use PATCH for state transitions**

`POST /vouchers/{id}/audit` and `POST /vouchers/{id}/post` are action endpoints. The alternative RESTful approach is `PATCH /vouchers/{id}` with `{"status": "audited"}`. The current design is pragmatic and common in accounting systems. This is a style choice — no action needed, but document the convention.

**Issue 2.1.2 — Inconsistent sub-resource patterns**

- `GET /auxiliaries/{type}/{id}/ledger` — nested sub-resource with type parameter. This works but mixes path parameters and resource types.
- `POST /vouchers/{id}/reverse` — this is a sub-resource action, returns a new voucher ID. Good.
- `POST /fixed-assets/depreciate-batch` — this should probably be `POST /fixed-assets/depreciation` with a body containing asset IDs. The current naming is acceptable but note the inconsistency.

### 2.2 Missing Critical Endpoints

| # | Missing Endpoint | Importance | Notes |
|---|-----------------|------------|-------|
| 1 | `GET /periods/current` | **High** | Frontend needs to know the current open period for default filters, voucher creation |
| 2 | `GET /vouchers/next-number` | **Medium** | Preview the next voucher number for the user before creation |
| 3 | `POST /vouchers/batch-audit` | **Medium** | Batch audit multiple vouchers (common workflow in period-end) |
| 4 | `POST /vouchers/batch-post` | **Medium** | Batch post multiple audited vouchers |
| 5 | `GET /dashboard/summary` | **High** | The frontend has a dashboard route (§5.3 `dashboard.tsx`) but no corresponding API endpoint is defined. The dashboard needs period summary data (voucher counts by status, trial balance totals, recent activity) |
| 6 | `GET /reports/trial-balance/compare` | **Low** | Multi-period comparison (frontend UX mentions "多期对比" in design.md §4.2) |
| 7 | `GET /accounts/{id}/balance` | **Medium** | Quick balance lookup for a single account (useful in pickers, validation) |
| 8 | `PATCH /vouchers/{id}/entries/{entryId}` | **Low** | Individual entry editing (currently only full voucher PUT) |
| 9 | `GET /health` | **High** | Health check endpoint for deployment monitoring |
| 10 | `GET /api/v1/openapi.json` | **Low** | FastAPI auto-generates this, but document it explicitly |

### 2.3 Authentication/Authorization Model

**JWT + RBAC — Appropriate and Sufficient**

The spec defines JWT (access token + refresh token) with RBAC decorators. The design.md §6 clarifies: access token 2h, refresh token 7d.

**Issue 2.3.1 — Permission model is underspecified**

The spec mentions three roles (`finance_staff`, `finance_manager`, `admin`) and a permissions JSONB bitmap on the roles table. However, it does not define:
- What permissions each role has
- What the permission key namespace looks like (e.g., `voucher:audit`, `voucher:post`, `account:create`)
- Whether permissions compose (can a user have multiple roles?)
- How the `permissions` JSONB is checked at runtime

**Recommendation:** Add a permission matrix to the spec:
```markdown
| Permission | finance_staff | finance_manager | admin |
|---|---|---|---|
| voucher:create | ✓ | ✓ | ✓ |
| voucher:edit:own | ✓ | ✓ | ✓ |
| voucher:edit:any |   | ✓ | ✓ |
| voucher:audit |   | ✓ |   |
| voucher:post |   | ✓ |   |
| voucher:reverse |   | ✓ |   |
| account:manage |   |   | ✓ |
| period:close |   | ✓ | ✓ |
| period:reopen |   |   | ✓ |
| ai:use | ✓ | ✓ | ✓ |
| admin:users |   |   | ✓ |
| admin:roles |   |   | ✓ |
```

**Issue 2.3.2 — Refresh token rotation not specified**

The spec mentions `POST /auth/logout` which "注销 refresh token" (invalidates the refresh token). This implies a server-side token store (e.g., a `refresh_tokens` table or Redis), but no such store is defined. Without a store, logout cannot actually invalidate the refresh token.

**Recommendation:** Add a `refresh_tokens` table or use Redis with a blacklist. Define the invalidation strategy explicitly.

**Issue 2.3.3 — Single role per user is limiting**

The `users` table has `role_id` (singular). For a 10-person finance team this is fine, but as the organization grows, users may need multiple roles (e.g., someone who is both a finance_staff for AP and a finance_manager for AR). **Recommend** a `user_roles` join table:
```sql
user_roles: user_id UUID FK, role_id UUID FK, PRIMARY KEY (user_id, role_id)
```

**Issue 2.3.4 — No mention of token refresh endpoint behavior on the frontend**

The spec doesn't specify how the frontend Axios interceptor should handle 401 responses (auto-refresh, redirect to login). This is an implementation detail but should be noted in §5 (`lib/api.ts`).

### 2.4 Error Handling Patterns

**Issue 2.4.1 — Error code catalog is missing**

The error response format (§3.1) is good:
```json
{"error": {"code": "VOUCHER_NOT_FOUND", "message": "凭证不存在", "detail": {}}}
```
But no catalog of error codes is defined. The frontend team needs to know which codes to handle:
- `VOUCHER_NOT_FOUND` → 404
- `VOUCHER_NOT_DRAFT` → 409 (trying to edit a posted voucher)
- `PERIOD_CLOSED` → 409
- `INSUFFICIENT_PERMISSIONS` → 403
- `VALIDATION_ERROR` → 422
- `AI_RATE_LIMITED` → 429
- `AI_GENERATION_FAILED` → 502
- `UNBALANCED_VOUCHER` → 422

**Recommendation:** Add an error code appendix listing 15-20 expected error codes with their HTTP status codes.

**Issue 2.4.2 — Validation error format not specified**

Pydantic validation errors (422) use a different format (`detail: [{loc: [...], msg: "...", type: "..."}]`). The spec should either standardize on this or wrap it into the `{error: {code, message, detail}}` format consistently.

**Recommendation:** Add a FastAPI exception handler that transforms Pydantic `ValidationError` and `RequestValidationError` into the standard format:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "detail": {
      "fields": {
        "date": "凭证日期不能为空",
        "entries[0].debit_amount": "借方金额必须≥0"
      }
    }
  }
}
```

---

## 3. AI Module Architecture Review

### 3.1 NL to Voucher Generation (§7.3)

**Flow Analysis**

The pseudocode in §7.3 is reasonable for a v1:
1. Gather context (all accounts + all auxiliaries)
2. Build prompt → LLM invoke → parse structured JSON
3. Balance check → retry if unbalanced
4. Return preview (NOT auto-save) → user confirms

**Issue 3.1.1 — Context size explosion (HIGH)**

Sending ALL enabled accounts to the LLM is the biggest risk in this module. A real chart of accounts for a medium enterprise has 500-2000 accounts at levels 1-4. Each account carries code, name, type, dc_type, and aux_types. This could easily be 50K-200K tokens just for the accounts list, leaving little room for instructions and conversation history.

**Recommendations:**
1. **Don't send the full chart of accounts.** Instead, structure it as:
   - A compressed representation: only level-3/4 leaf accounts that are commonly used, or
   - Use a RAG approach: embed accounts by name/code and retrieve the top-N relevant ones based on the user's NL description, or
   - Use function/tool calling: let the LLM request account searches by keyword
2. **Minimum:** Paginate or filter accounts by `is_enabled` and only send leaf accounts (accounts with no children)
3. Add a `MAX_ACCOUNTS_CONTEXT` config limit with graceful degradation

**Issue 3.1.2 — No account usage frequency weighting**

The LLM is given all accounts equally. In practice, 80% of voucher entries use 20% of accounts (Pareto principle). **Recommend:** Track account usage frequency and prioritize commonly-used accounts in the prompt. This also improves accuracy.

**Issue 3.1.3 — Hallucinated accounts are not caught**

The retry logic (§7.3 step 3) only checks for balance (debit = credit). If the LLM hallucinates an account code `6602-XYZ` that doesn't exist, the `parse_entries()` function must detect this, but the pseudocode doesn't show validation. **Recommend:** Add explicit validation:
```python
# After parsing, validate every account_id exists
invalid = [e.account_id for e in parsed.entries if e.account_id not in valid_ids]
if invalid:
    fix_prompt = build_fix_prompt(description, parsed, invalid_accounts=invalid)
```

**Issue 3.1.4 — No structured output guarantee**

The spec says "结构化 JSON 输出" but doesn't mention using OpenAI's structured output / JSON mode / function calling. Without this, parsing failures will be common. **Recommend:** Use LangChain's `with_structured_output()` or OpenAI's `response_format={"type": "json_object"}` with a strict JSON schema.

**Issue 3.1.5 — Conversation storage mismatch**

The spec has `ai_conversation` JSONB on `vouchers` (§2.2), but the generation flow saves a `conversation_id` (UUID) to an unknown store. The relationship between `vouchers.ai_conversation` and the conversation store is undefined. If it's the same thing, the column should be `ai_conversation_id UUID` referencing a `conversations` table, not JSONB.

### 3.2 NL to SQL Query Safety (§3.12, design.md §6)

**Issue 3.2.1 — Read-only replica enforcement is UNDOCUMENTED in the engineering spec (CRITICAL)**

The design.md §6 states: "LLM 生成的 SQL 在只读副本执行，禁止 DML". However, the engineering spec §3.12 and §4 (API middleware) contain **zero mention** of a read-only database connection. The API endpoint `POST /ai/query` returns SQL results but never references a read-only replica.

This is the highest-severity security concern in the entire spec. If AI-generated SQL executes against the primary database with write permissions, a malicious or poorly-generated query could:
- `DROP TABLE vouchers`
- `UPDATE vouchers SET status = 'posted' WHERE ...`
- `DELETE FROM account_balances`

**Mandatory requirements for the NL→SQL path:**
1. **Separate database connection:** Create a dedicated `ai_readonly_engine` in SQLAlchemy with a PostgreSQL user that has `SELECT` only (no INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER).
2. **SQL validation before execution:** Before running the generated SQL:
   ```python
   import sqlparse
   def validate_readonly_sql(sql: str) -> bool:
       statements = sqlparse.parse(sql)
       for stmt in statements:
           if stmt.get_type() != 'SELECT':
               raise ReadOnlyViolation(f"Only SELECT allowed, got {stmt.get_type()}")
       return True
   ```
3. **Forced LIMIT:** Always append `LIMIT 1000` if no LIMIT clause exists, preventing unbounded result sets.
4. **Statement timeout:** Set `statement_timeout = 5000` (5s) on the AI database connection to prevent runaway queries.
5. **Row-level restrictions:** Consider a Postgres row security policy that limits what an AI query can see (e.g., filter to current period only).

**Issue 3.2.2 — `POST /ai/query` lacks input validation**

The endpoint body is `{question, conversation_id?}`. There is no restriction on question length or content. A very long or adversarial question could produce expensive or dangerous SQL. **Recommend:** Add `max_length=500` on the question field via Pydantic.

**Issue 3.2.3 — No explainability for failed queries**

If the generated SQL fails (syntax error, timeout, permission denied), the user gets an error with no insight into what went wrong. **Recommend:** Always return the generated SQL alongside the error so users can debug.

### 3.3 Prompt Engineering Strategy Concerns

The spec has **no prompt templates defined** anywhere. This is a significant gap. Each AI endpoint needs:

1. **System prompt** — Role, domain context (Chinese accounting standards), output format instructions
2. **Few-shot examples** — At minimum 3-5 example voucher generation pairs for common scenarios (差旅费, 采购, 销售收入, 折旧, 工资)
3. **Output schema** — The exact JSON structure expected

**Recommendation:** Add an appendix to the engineering spec with the initial prompt templates for each AI endpoint. At minimum:

```markdown
### AI Prompts (Initial Version)

#### Voucher Generation System Prompt
你是一位资深会计，精通中国企业会计准则。
根据用户的业务描述，生成借贷记账法的凭证分录。
- 输出应为严格 JSON 格式
- 每行分录的借方或贷方金额只能有一个非零
- 所有分录的借方合计必须等于贷方合计
- 科目编码必须从提供的科目列表中选择
- 识别并关联辅助核算（个人、部门、单位、项目）

#### NL→SQL System Prompt
你是一个将中文自然语言转换为 PostgreSQL SQL 查询的助手。
数据库表结构如下：[schema description]
- 只生成 SELECT 语句
- 金额字段类型为 NUMERIC(18,2)
- 总是包含 LIMIT 子句
- 返回格式：{sql: string, columns: string[], explanation: string}
```

### 3.4 Rate Limiting for AI Endpoints

The spec (§4) sets AI endpoints to 10 req/min. This is reasonable but insufficiently specified:

**Issue 3.4.1 — No token-based rate limiting**

10 requests/min is a per-request limit, but a single request could consume 100K tokens (sending the full chart of accounts). This doesn't control cost. **Recommend:** Add a daily token budget per user/tenant, e.g., 500K tokens/day for AI operations.

**Issue 3.4.2 — No cost attribution**

AI usage should be tracked per user for cost allocation. **Recommend:** Add an `ai_usage` table:
```sql
ai_usage: id, user_id, endpoint, model, prompt_tokens, completion_tokens, created_at
```

**Issue 3.4.3 — No model fallback strategy**

If OpenAI is down or rate-limited, there's no mention of a fallback provider. The design.md mentions DeepSeek as an alternative. **Recommend:** Define a primary/secondary model configuration and automatic fallback in the LLM client.

---

## 4. Business Logic Review

### 4.1 Voucher Posting and Balance Update (§7.1)

**Issue 4.1.1 — Missing credit-natured account calculation (BUG)**

The pseudocode in §7.1 has an incomplete balance calculation:
```python
if entry.account.dc_type == "D":
    balance.closing_debit = balance.opening_debit + balance.current_debit - balance.current_credit
# MISSING: else branch for dc_type == "C"
```

For credit-natured accounts (liabilities, equity, revenue), the correct formula is:
```python
elif entry.account.dc_type == "C":
    balance.closing_credit = balance.opening_credit + balance.current_credit - balance.current_debit
```

This is a **blocking bug** — without it, credit-natured account balances will be wrong. All liability, equity, and revenue accounts will have incorrect closing balances.

Additionally, the current pseudocode overwrites `closing_debit` but doesn't clear `closing_credit` (and vice versa). For D-type accounts, `closing_credit` should be 0; for C-type accounts, `closing_debit` should be 0.

**Corrected pseudocode:**
```python
for entry in voucher.entries:
    balance = await get_or_create_balance(period.id, entry.account_id)
    balance.current_debit += entry.debit_amount
    balance.current_credit += entry.credit_amount
    
    if entry.account.dc_type == "D":
        balance.closing_debit = balance.opening_debit + balance.current_debit - balance.current_credit
        balance.closing_credit = 0
    else:  # dc_type == "C"
        balance.closing_credit = balance.opening_credit + balance.current_credit - balance.current_debit
        balance.closing_debit = 0
```

**Issue 4.1.2 — No concurrency control on balance updates**

If two users post vouchers simultaneously, both transactions could read the same `account_balances` row and write conflicting updates (lost update problem). The pseudocode uses `db.transaction()` but not row-level locking.

**Recommendation:** Use `SELECT ... FOR UPDATE` when fetching the balance row:
```python
balance = await db.execute(
    select(AccountBalance)
    .where(AccountBalance.period_id == period.id, AccountBalance.account_id == entry.account_id)
    .with_for_update()
)
```

**Issue 4.1.3 — No unpost logic**

The spec has `POST /vouchers/{id}/reverse` which creates a new reversal voucher, but there is no `POST /vouchers/{id}/unpost` endpoint. Reversal and unposting are different operations:
- **Reversal**: Creates a new negating voucher in the current period (leaves original posted)
- **Unpost**: Reverts the original posting (minus balance updates) and returns status to "audited"

Both are needed. Chinese accounting systems typically support both.

**Issue 4.1.4 — Voucher number generation race condition**

Voucher numbers format: `JZ-2026-06-001`. The spec doesn't specify how the sequential number (001) is generated. If this is done with `SELECT MAX(voucher_no) + 1`, there is a race condition under concurrent creation. **Recommend:** Use a PostgreSQL sequence or `SELECT ... FOR UPDATE` on a dedicated counter table.

### 4.2 Period Close and Carry-Forward (§7.4)

**Issue 4.2.1 — Opening balance setup for next period is MISSING**

The carry-forward execution in §7.4:
1. Runs checks
2. Creates carry-forward vouchers
3. Auto-audits and posts them
4. Invalidates cache

But it does NOT create the next period's account balance rows with `opening_*` values populated. While the trial balance query could compute "opening" dynamically from the previous period's closing, this is computationally expensive and error-prone.

**The period close flow must include:**
```python
async def close_period(period_id: UUID) -> None:
    # 1. Verify all vouchers are posted
    # 2. Execute carry-forward templates
    # 3. For each account with a balance row in this period:
    #    Create next period's balance row with:
    #      opening_debit = this_period.closing_debit
    #      opening_credit = this_period.closing_credit
    # 4. Mark period as closed
    # 5. Create next period if it doesn't exist
```

Without this step, the trial balance for the new period will show zero opening balances until the developer manually initializes them.

**Issue 4.2.2 — Carry-forward auto-post bypasses normal controls**

The carry-forward code auto-audits and auto-posts generated vouchers (§7.4 line: `await audit_voucher(voucher.id); await post_voucher(voucher.id)`). This means:
- No human reviews the automatically-generated voucher
- If the carry-forward template is misconfigured, wrong amounts are posted silently
- The auditor_id on these vouchers will be NULL or the system user

**Recommendations:**
1. Add a `system_user_id` configuration for automated operations
2. Log a prominent warning when auto-posting
3. Consider making auto-post configurable per template (some templates may need human review)

**Issue 4.2.3 — Period close locking**

The pseudocode doesn't lock the period during close. If two users trigger close simultaneously, you could get duplicate carry-forward vouchers or corrupted balances. **Recommend:**
```python
period = await db.execute(
    select(Period).where(Period.id == period_id).with_for_update()
)
if period.status == "closed":
    raise PeriodAlreadyClosed()
```

**Issue 4.2.4 — Reopen safety checks**

`POST /periods/{id}/reopen` is defined but the business logic is not specified. Reopening a closed period is dangerous because:
- Vouchers in subsequent periods may depend on the closed period's balances
- Carry-forward vouchers in the next period would be invalidated

**Minimum reopen requirements:**
1. Check that no subsequent periods are closed (reopen in reverse chronological order)
2. Warn/block if carry-forward vouchers exist in the next period
3. Reverse the closing balance initialization in the next period
4. Require admin role (not just finance_manager)

### 4.3 Edge Cases in Accounting Operations

**Issue 4.3.1 — Voucher date vs period mismatch**

A voucher has both a `date` and `period_id`. No validation ensures they're consistent (e.g., date `2026-07-15` with period `2026-06`). **Recommend:** Add validation in the service layer:
```python
period = await get_period(voucher.period_id)
if voucher.date.month != period.month or voucher.date.year != period.year:
    # Allow or warn based on system parameter
```

**Issue 4.3.2 — Delete voucher with CASCADE risks (§2.3 discussed above)**

Even for drafts, cascading deletes destroy data. If a draft has 50 entries (complex voucher), a single DELETE removes all of them with no recovery.

**Issue 4.3.3 — Rounding in multi-entry allocations**

When splitting an amount across multiple lines (e.g., allocating 100 CNY across 3 departments), DECIMAL(18,2) can cause rounding discrepancies (33.33 + 33.33 + 33.33 = 99.99, not 100.00). The spec doesn't address allocation rounding strategies.

**Recommend:** Add a `rounding_adjustment` flag on voucher entries, or implement "last-entry adjustment" where the last allocation absorbs the rounding difference.

**Issue 4.3.4 — Zero-balance subsidiary accounts**

Accounts with level > 1 should theoretically roll up to their parent. The spec doesn't specify whether the trial balance enforces `Σ(children) = parent`. This is a common integrity check. **Recommend:** Add a validation routine that flags accounts where `SUM(child balances) ≠ parent balance`.

---

## 5. Overall Concerns

### 5.1 Performance Bottlenecks

**Bottleneck 1: Trial Balance Full Recomputation on Cache Miss**

The trial balance (§7.2) queries ALL account balances and ALL accounts, then builds a tree in Python. With 500 accounts and 12 periods of history, this is fast. But the design.md mentions "多期对比" (multi-period comparison), which would multiply the data. 

**Mitigation:** The current Redis cache (300s TTL) with write-invalidation is adequate for v1. Monitor cache hit rates and scale to materialized views if needed.

**Bottleneck 2: Balance Snapshot Write Amplification**

Every voucher entry updates a balance row. A period with 10,000 vouchers averaging 3 entries each = 30,000 balance updates. If all hit the same cash account, you get 10,000 updates to a single row. This serializes on the row lock.

**Mitigation:** 
- Batch balance updates within a voucher (update each account once, summing all entries for that account)
- Consider deferred balance recalculation for high-volume periods

**Current pseudocode updates balance per-entry — fix this:**
```python
# Instead of per-entry updates, aggregate first:
account_totals = {}
for entry in voucher.entries:
    key = entry.account_id
    if key not in account_totals:
        account_totals[key] = [0, 0]  # [debit, credit]
    account_totals[key][0] += entry.debit_amount
    account_totals[key][1] += entry.credit_amount

# Then update each balance once
for account_id, (debit, credit) in account_totals.items():
    balance = await get_or_create_balance(period.id, account_id)
    balance.current_debit += debit
    balance.current_credit += credit
    # ... closing calculation
```

**Bottleneck 3: No database connection pool configuration**

The spec mentions SQLAlchemy async but doesn't specify pool size, max overflow, or pool timeout. Default SQLAlchemy pool size is 5 connections, which is too low for a multi-user web app.

**Recommendation:** Add to config:
```python
DB_POOL_SIZE = 20           # Base pool size
DB_MAX_OVERFLOW = 10        # Extra connections under load
DB_POOL_TIMEOUT = 30        # Seconds to wait for a connection
DB_POOL_RECYCLE = 3600      # Recycle connections hourly
```

### 5.2 Security Red Flags

| # | Issue | Severity | Mitigation |
|---|-------|----------|------------|
| 1 | **AI SQL executed on primary DB** (§3.2.1) | 🔴 **Critical** | Mandatory read-only replica + SQL validation + forced LIMIT |
| 2 | **CASCADE deletes on financial tables** (§1.4) | 🔴 **High** | Replace with RESTRICT + soft deletes |
| 3 | **No password policy** | 🟡 **Medium** | Add password complexity, rotation, and lockout (at least bcrypt with cost factor 12, documented in design.md but not spec) |
| 4 | **Audit log captures old_values/new_values** (§2.11) — password hash changes could expose hashes | 🟡 **Medium** | Exclude `password_hash` from audit capture; audit that a password change happened without recording the hash |
| 5 | **No API key/secret management documented** — where are OpenAI API keys stored? | 🟡 **Medium** | Use environment variables + Pydantic `SecretStr`; never log or audit |
| 6 | **No CORS origin whitelist definition** (§4) | 🟡 **Medium** | Define allowed origins explicitly in config, not `allow_origins=["*"]` |
| 7 | **JWT refresh tokens potentially stored insecurely** — the design.md says httpOnly cookie, but the API spec shows `POST /auth/refresh` with `{refresh_token}` in the body, which implies the token is accessible to JS (XSS risk) | 🟡 **Medium** | Resolve the design.md vs engineering-spec.md conflict: if httpOnly cookie, the refresh endpoint should read from the cookie, not the request body |
| 8 | **No rate limiting on auth endpoints** — login endpoint should have stricter rate limiting (5 req/min per IP) to prevent brute force | 🟡 **Medium** | Add auth-specific rate limiting |
| 9 | **No mention of TLS/HTTPS enforcement** | 🟡 **Medium** | Add to deployment config |

### 5.3 Missing Pieces and Improvements

**Missing Infrastructure Components:**

1. **Database backup strategy is undefined.** §3.13 has `POST /admin/backup` and `GET /admin/backups`, but:
   - No scheduled backup (only manual)
   - No backup retention policy
   - No restore procedure
   - No backup verification
   - **Recommend:** Add a Celery periodic task for automated daily backups with a configurable retention period (e.g., keep 7 daily, 4 weekly, 12 monthly).

2. **No data migration strategy from the old system.** The spec mentions this is replacing "浪潮内账系统" but §9 (实施计划) has no data migration phase. This is typically the hardest part of an ERP replacement. **Recommend:** Add a Phase 0 or early task for data mapping and migration scripts.

3. **No logging/monitoring/observability.** The architecture has no:
   - Structured logging (JSON format for log aggregation)
   - Metrics export (Prometheus endpoint)
   - Health check endpoint (only implicit)
   - Request ID propagation (X-Correlation-ID mentioned in the API contract checklist in AGENTS.md but missing from the spec)
   - **Recommend:** Add a `/health` endpoint, structured logging with `structlog`, and correlation ID middleware.

4. **No Celery task definitions in the spec.** Celery is mentioned as part of the tech stack but no tasks are defined beyond design.md referencing "export" and "backup." **Recommend:** List all planned Celery tasks with their queues, retry policies, and error handling.

5. **No WebSocket/real-time support.** The AGENTS.md persona mentions "Stream real-time updates via WebSocket with guaranteed ordering" but the engineering spec has zero WebSocket endpoints. This is fine for v1 (polling-based refresh is adequate for an accounting system), but document the decision to defer WebSocket.

**Missing Design Decisions:**

6. **Voucher number generation strategy.** The format `JZ-2026-06-001` implies a monthly sequence. Define:
   - Does the counter reset each month?
   - What happens if a draft voucher is deleted — is the number reused?
   - What about different voucher types (receipt, payment, transfer)?

7. **No specification for template-based report rendering.** The balance sheet/income/cash flow statements (§3.7) accept a `template_id` parameter and return sections with labels, but there is no `statement_templates` table or template format specification. The report template is critical infrastructure — define its JSON schema.

8. **No data archiving/purging strategy.** Audit logs will grow unboundedly. Vouchers accumulate over years. **Recommend:** Define archiving policies:
   - Audit logs: archive to a separate table after 2 years, purge archived logs after 7 years
   - Vouchers: archive closed-period vouchers to cold storage after 3 years

9. **No i18n considerations.** The system is in Chinese, which is fine. But hardcoding Chinese strings in both frontend and backend makes future internationalization impossible. **Recommend:** At minimum, use string constants/enums in the backend for error messages; use i18n keys on the frontend even if only Chinese locale is defined.

10. **No environment configuration differentiation.** The spec has one `.env.example`. Production needs separate config for:
    - Database connection strings (different hosts)
    - AI API keys (different rate limits)
    - Log levels
    - CORS origins
    - **Recommend:** Document at minimum: `.env.development`, `.env.staging`, `.env.production` with clear variable definitions.

### 5.4 Spec Completeness Scorecard

| Section | Completeness | Notes |
|---------|-------------|-------|
| §2 Data Model | 75% | Missing indexes, polymorphic FK unresolved, no currency |
| §3 API Contract | 80% | Missing dashboard, health, error catalog, batch endpoints |
| §4 Middleware | 70% | Missing correlation ID, read-only DB connection for AI |
| §5 Frontend Spec | 90% | Well-defined component interfaces and routing |
| §6 State Management | 95% | Clear query key convention and caching strategy |
| §7 Business Logic | 60% | Missing C-type balance calc (bug), unpost, period open init |
| §8 Test Strategy | 80% | Good structure; missing performance/load test plan |
| §9 Implementation Plan | 85% | Reasonable phasing; missing data migration, env configs |
| AI Module Overall | 55% | Missing prompts, read-only enforcement, token management, cost tracking |

---

## Summary of Required Actions (Priority-Ordered)

### 🔴 Blocking (Must fix before/early in Phase 3: Voucher Management)

1. **Fix §7.1 balance calculation** — add C-type account formula
2. **Resolve §2.4 polymorphic FK** — choose Option A (separate columns) or Option B with clear documentation
3. **Remove CASCADE deletes** from `voucher_entries` and `entry_auxiliaries`
4. **Add all critical indexes** (see §1.2 table above)

### 🟡 High Priority (Must fix before Phase 8: AI Module)

5. **Implement read-only DB connection for AI SQL** (§3.2.1)
6. **Add SQL validation/sanitization to NL→SQL path**
7. **Add forced LIMIT and statement timeout on AI queries**
8. **Design account context strategy for NL→voucher** (don't send all accounts)
9. **Define permission matrix** (which role can do what)

### 🟢 Medium Priority (Should fix before production)

10. **Define prompt templates** for all AI endpoints
11. **Add period close → opening balance initialization** logic
12. **Add concurrency control** (SELECT FOR UPDATE) on balance updates
13. **Add refresh token table/blacklist** for logout
14. **Define error code catalog** with HTTP status codes
15. **Add auth rate limiting** (5 req/min per IP)
16. **Resolve refresh token storage conflict** (httpOnly cookie vs request body)

### 🔵 Nice to Have (Future iterations)

17. Add currency column
18. Add fiscal year table
19. Multi-role per user (user_roles join table)
20. AI usage tracking and cost attribution
21. WebSocket real-time updates
22. Data archiving/purging strategy
23. i18n infrastructure

---

*Review complete. All findings are actionable and referenced to specific sections of engineering-spec.md. The spec is a strong v0.1 — the issues identified are typical for a spec at this stage and can be resolved with targeted updates.*
