# Core Accounting

**开源免费的企业财务软件，支持 AI 财务问答与自主部署。**

Core Accounting 面向中小企业，连接票据、记账凭证、账表查询与财务报表。用户可以自行部署，也可以由无限开源科技协助完成企业交付。

[查看源码](https://github.com/EricRenForCode/core-accounting) · [后端文档](backend/README.md) · [前端文档](frontend/README.md) · [MIT 许可证](LICENSE)

## 产品与服务

- **软件免费**：采用 MIT 许可证，允许使用、修改与商业使用，需保留版权及许可声明。没有 Core Accounting 软件订阅费。
- **AI 财务问答**：用自然语言查询财务数据库，支持查询结果、SQL 展示和对话上下文；也提供凭证分录建议、报表解读与期末检查相关功能。
- **自行部署**：在自己的环境运行应用，管理数据、版本和备份。
- **企业交付**：按约定的设备评估、部署配置、模型接入、培训和验收范围，一次性收取交付费用。交付后软件使用继续免费。

服务器运行、所选外部模型或识别服务，以及另行委托的迁移、维护和定制项目，按实际选择或合同约定承担费用。

企业交付咨询：**contact@infiniteopen.cn**。公司官网：[无限开源科技](https://infiniteopen.cn)。

## 功能概览

| 模块 | 内容 |
| --- | --- |
| 凭证与原始票据 | 凭证录入、审核、记账、冲销、导入导出；原始票据上传、识别校对和生成草稿 |
| 账表查询 | 科目余额、总账、明细账、序时账与试算平衡 |
| 财务报表 | 资产负债表、利润表、现金流量表与报表模板 |
| 期间与核算 | 期初余额、期末结转、结账、辅助核算、出纳与固定资产相关模块 |
| AI 助手 | 自然语言查询、凭证分录建议、报表解读与期末检查 |
| 系统管理 | 用户与角色、会计科目、期间、参数及审计日志 |

本项目由 AI Agent 辅助开发。仓库包含实现与测试，但不代表已经针对所有企业场景完成生产验收。采用前请用测试账套验证自己的科目、核算与报表流程；AI 建议需由使用者核对。

## 本地部署与数据边界

**应用自行部署，不等于 AI 已经完全在本地运行。**

当前代码默认通过 `ChatDeepSeek` 接入 DeepSeek API，票据识别提供可选的阿里云 OCR 配置。启用这些外部服务后，相关问题、报表或票据处理请求可能发送到所选服务。财务问答通过独立只读数据库连接执行查询，并设置只读事务及超时。

完整本地方案需要同时落实：本地财务应用与数据库、本地模型服务、模型客户端接入调整，以及本地票据处理。当前仓库未提供已经验证的完整离线模型安装包或通用本地模型端点配置；这部分需根据环境适配并验收。无限开源科技可协助评估交付方案。

## 本地开发启动

以下路线是在本机启动前端和后端，使用 Docker 提供数据库及 Redis。它不是一键生产部署承诺。

### 1. 准备工具并获取代码

需要 Git、Docker 与 Docker Compose、Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node.js 22.13+（或满足项目依赖要求的更新版本）与 pnpm 9+。前端使用 pnpm 锁文件。

```bash
git clone https://github.com/EricRenForCode/core-accounting.git
cd core-accounting
docker compose up -d db redis
cp backend/.env.example backend/.env
```

当前开发 Compose 将 PostgreSQL 映射到宿主机 **5433**，Redis 映射到 **6380**。编辑 `backend/.env`，使本机运行的后端使用以下地址：

```dotenv
DATABASE_URL=postgresql+asyncpg://accounting:accounting@localhost:5433/core_accounting
AI_READONLY_DATABASE_URL=postgresql+asyncpg://accounting_ro:YOUR_READONLY_PASSWORD@localhost:5433/core_accounting
REDIS_URL=redis://localhost:6380/0
CORS_ORIGINS=["http://localhost:5173"]
ENVIRONMENT=development
```

同时替换 `JWT_SECRET`，可用 `openssl rand -hex 32` 生成。以上 `accounting` 数据库密码只对应仓库的本地开发环境，不用于正式部署。按需填写 DeepSeek 和 OCR 配置；未配置有效服务时，不应期待对应 AI / 云端识别功能可用。

### 2. 初始化后端和数据库

```bash
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run python seed.py
```

`seed.py` 初始化角色、管理员与基础会计科目。新建的测试管理员为 `admin / admin123`；正式使用前必须修改默认密码。脚本不会重置已有管理员的密码。

启用财务问答前，还需创建 `.env` 对应的只读数据库账户。在仓库根目录运行：

```bash
docker compose exec db psql -U accounting -d core_accounting
```

在数据库控制台中执行以下示例，将密码占位符替换为你选择的实际密码，并与 `.env` 保持一致：

```sql
CREATE ROLE accounting_ro LOGIN PASSWORD 'YOUR_READONLY_PASSWORD';
GRANT CONNECT ON DATABASE core_accounting TO accounting_ro;
GRANT USAGE ON SCHEMA public TO accounting_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO accounting_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE accounting IN SCHEMA public
  GRANT SELECT ON TABLES TO accounting_ro;
```

这段 SQL 用于首次创建账户；已有该角色时，核对其密码与权限即可。完成后退出数据库控制台。在 `backend/` 启动 API：

```bash
uv run uvicorn app.main:app --reload --port 8000
```

API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)。健康检查：[http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)。需要异步任务时，在 `backend/` 的另一个终端运行：

```bash
uv run celery -A app.tasks worker --loglevel=info
```

### 3. 启动前端

在新的终端进入仓库的 `frontend/`：

```bash
pnpm install
pnpm dev
```

访问 [http://localhost:5173](http://localhost:5173)。默认连接本机 `8000` 端口的后端；如调整端口，请同时核对前端 API 地址与后端 CORS 配置。

## 生产部署

仓库包含 `docker-compose.prod.yml`、后端 Dockerfile、Nginx 配置与备份脚本，但仍需结合目标环境确认前端构建与静态资源服务、数据库账户、密钥、域名、HTTPS、权限和备份恢复。

当前开发 Compose 的完整前端服务引用 `frontend/Dockerfile`，仓库中尚未提供该文件，因此上文采用分别启动前后端的路线。不要直接把 `docker compose --profile full up` 视为可用的完整部署步骤。

生产 Compose 中的 AI 数据库连接也需替换为真正的只读账户；它当前默认复用了主库凭据。将 AI 服务完全本地化，还需完成前文所述的模型与票据处理适配。

## 开发检查

后端，在 `backend/`：

```bash
uv run pytest
```

前端，在 `frontend/`：

```bash
pnpm test
pnpm build
```

后端测试使用模拟与内存数据库覆盖部分业务逻辑，不替代实际 PostgreSQL、模型服务和企业环境验收。

## 仓库结构

```text
backend/                 FastAPI、财务业务、AI、迁移与测试
frontend/                React 财务应用
document/                设计、工程说明与功能规划
backups/                 数据库备份脚本
.github/workflows/       CI 配置
docker-compose.yml       本地开发基础服务
docker-compose.prod.yml  生产部署参考配置
nginx.conf               应用反向代理配置
LICENSE                  MIT 许可证
```

## 参与和反馈

欢迎通过 [Issues](https://github.com/EricRenForCode/core-accounting/issues) 反馈问题或提交 Pull Request。报告问题时请提供复现步骤、版本、预期与实际行为；使用脱敏示例，不上传实际企业账目、密钥或个人信息。

## 许可证

Core Accounting 源码采用 [MIT 许可证](LICENSE)。项目依赖与第三方素材保留各自的许可证，MIT 授权不替代它们的授权条款。
