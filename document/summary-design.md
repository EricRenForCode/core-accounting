# 技术设计总结 — Core Accounting v1

## 定位
绿色项目，替代浪潮内账系统。React 18 + TS + Vite + Tailwind 前端，Python FastAPI + PostgreSQL + Celery + LangChain 后端。

## 架构分层
```
React SPA → FastAPI (JWT+RBAC) → Service Layer → SQLAlchemy 2.0 → PostgreSQL 15
                                    └→ Celery + Redis (异步任务)
```

## 后端核心决策
- **ORM**：SQLAlchemy 2.0 async + Alembic 迁移
- **缓存**：Redis（科目余额热数据 + Celery broker）
- **认证**：JWT access(2h) + refresh(7d)
- **审计**：独立 audit_log 表，不可删除
- **性能**：月度余额快照、分页预聚合、异步导出

## 前端核心决策
- **构建**：Vite，按模块 feature 组织
- **UI**：Tailwind + Shadcn/ui
- **状态**：TanStack Query（服务端）+ Zustand（客户端）
- **表单**：React Hook Form + Zod
- **路由**：TanStack Router（50+ 路由，按角色过滤）

## 数据库关键表
vouchers → voucher_entries(多分录) → entry_aux(辅助核算关联)
accounts(科目树) → 余额快照表
periods → carry_forward(结转记录)
固定表：cash_journals, bank_journals, fixed_assets, audit_log, report_templates

## AI 模块（4 个子模块）
1. **凭证生成**：NL→科目匹配→分录预览(可编辑)→平衡校验→确认写入
2. **报表解读**：三报表 snapshot→同比/环比/关键比率/风险
3. **期末检查**：10 项自动化检查（未记账/折旧/暂估/平衡...）
4. **自然语言查询**：NL→SQL(只读副本)→结果表格→连续追问

## 安全
- RBAC 三级角色（财务人员/经理/管理员）
- AI SQL 在只读副本执行，禁止 DML
- 全部写操作记录审计日志

## 开发周期
9 Phase / ~20 周，从脚手架→系统管理→凭证→账表→核算→报表→期末→AI→测试部署
