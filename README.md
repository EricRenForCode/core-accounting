# Core Accounting

**开源免费的企业财务软件，支持 AI 财务问答与自主部署。**

Core Accounting 面向中小企业，连接票据、记账凭证、账表查询与财务报表。用户可以自行部署，也可以由无限开源科技协助完成企业交付。

[查看源码](https://github.com/EricRenForCode/core-accounting) · [后端文档](backend/README.md) · [前端文档](frontend/README.md) · [MIT 许可证](LICENSE)

## 生产环境：一条命令

已经装好 Docker 与 Docker Compose v2 时，克隆后执行：

```bash
git clone https://github.com/EricRenForCode/core-accounting.git
cd core-accounting
./scripts/install.sh
```

脚本会生成 `.env`、构建并启动 Web、API、PostgreSQL、Redis、Celery 与 Nginx，然后打印访问地址和初始管理员密码。说明见 [生产部署](#生产部署)。本机开发请走 [本地开发启动](#本地开发启动)，两条路径使用不同的 Compose 项目，数据卷互不影响。

## 产品演示

约 **42 秒中文解说**，快速了解仪表盘、凭证管理、原始票据、财务报表和 AI 财务问答界面。

[![Core Accounting 产品界面动图预览：仪表盘、凭证、票据、报表与 AI 财务问答](docs/media/product-demo.gif)](https://github.com/EricRenForCode/core-accounting/releases/download/product-demo-2026-10-13/core-accounting-promo-narrated.mp4)

[获取完整演示视频（MP4，1080p，含中文解说）](https://github.com/EricRenForCode/core-accounting/releases/download/product-demo-2026-10-13/core-accounting-promo-narrated.mp4) · [视频附件页](https://github.com/EricRenForCode/core-accounting/releases/tag/product-demo-2026-10-13)

上方为加速、无声的动图预览。视频基于真实产品界面，使用虚构演示数据；AI 问答片段采用预设示例响应。

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

以下路线在本机启动前端和后端，只用 Docker 提供数据库和 Redis。生产环境请用 [生产部署](#生产部署)，不要把开发 Compose 当成线上安装。

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

这条路径给已经装好 Docker 的机器用。它启动完整生产栈：Nginx 上的 Web 界面和 API、FastAPI、Celery、PostgreSQL、Redis。数据库和 Redis 不映射到宿主机端口，只在 Compose 网络内可达。默认沿用 Compose 既有的项目名，使升级能够复用原来的数据库与 Redis 卷。

软件本身免费。DeepSeek 与阿里云 OCR 仍是外部服务；不填密钥时应用可以启动，对应的 AI / 云端识别不可用。本仓库不包含已经验收的离线模型安装包。

### 前提

- Docker Engine
- Docker Compose v2（命令是 `docker compose`，不是旧的 `docker-compose`）
- 克隆仓库时需要 Git

不需要在宿主机安装 Python、Node 或 pnpm。

### 安装

在仓库根目录：

```bash
git clone https://github.com/EricRenForCode/core-accounting.git
cd core-accounting
./scripts/install.sh
```

也可以合成一条命令：

```bash
git clone https://github.com/EricRenForCode/core-accounting.git && cd core-accounting && ./scripts/install.sh
```

还没有仓库、又希望由脚本自己克隆时：

```bash
curl -fsSL https://raw.githubusercontent.com/EricRenForCode/core-accounting/master/scripts/install.sh | bash
```

首次运行会写入根目录 `.env`（权限 `600`，已在 `.gitignore` 中），生成数据库密码、JWT 密钥和初始管理员密码，然后执行 `docker compose -f docker-compose.prod.yml up -d --build`，并等待健康检查。结束时打印：

- Web 地址（默认端口 80）
- 健康检查 `/api/v1/health` 与 API 文档 `/docs`
- 首次登录用户 `admin` 和密码（同时记在 `.env` 的 `INITIAL_ADMIN_PASSWORD`）

登录后请立刻修改管理员密码。脚本再次运行不会重置已有管理员。

想指定访问地址或端口时，在第一次运行前加上变量：

```bash
PUBLIC_URL=https://accounting.example.com NGINX_PORT=80 ./scripts/install.sh
```

`PUBLIC_URL` 不要使用 `localhost` 或 `127.0.0.1`，生产启动校验会拒绝。界面和 API 由同一个 Nginx 提供，用脚本打印的地址打开即可。若机器没有局域网地址，脚本会把校验用的 `PUBLIC_URL` 写成 `http://core-accounting.private`，并提示用 `http://127.0.0.1` 打开。

手工安装（不经过脚本）时：

```bash
cp .env.example .env
# 替换 DB_PASSWORD、DB_RO_PASSWORD、JWT_SECRET、PUBLIC_URL、CORS_ORIGINS、INITIAL_ADMIN_PASSWORD
docker compose -f docker-compose.prod.yml up -d --build
```

占位符 `CHANGE_ME` 和默认 JWT 密钥无法通过生产启动校验。密码请用 `openssl rand -hex 32` 生成，避免 `$`、引号和空格。

API 容器启动时会执行迁移、创建只读数据库角色 `accounting_ro`（仅 SELECT，供 AI 查询），并写入基础角色、管理员和会计科目。票据文件保存在名为 `uploads` 的卷里。

升级时沿用原来的目录和 Compose 项目名（包括已有的 `COMPOSE_PROJECT_NAME` 或 `-p` 参数），以便复用原来的数据库与 Redis 卷。安装脚本不会强制更换项目名；使用 `-p` 的已有部署可通过同名的 `COMPOSE_PROJECT_NAME` 运行脚本。若要同时运行独立的开发栈，请为开发栈另指定项目名，例如 `docker compose -p core-accounting-dev up -d db redis`。

开发 Compose 的 `frontend` 服务仍然引用不存在的 `frontend/Dockerfile`，`docker compose --profile full up` 不是生产安装，也不是当前支持的本地开发方式。

### AI 与票据识别

编辑 `.env` 后重新执行安装脚本（已有密钥不会轮换，除非你导出了同名变量）：

```bash
DEEPSEEK_API_KEY=sk-你的密钥 ./scripts/install.sh
```

```bash
ALIYUN_OCR_ACCESS_KEY_ID=你的AccessKeyId \
ALIYUN_OCR_ACCESS_KEY_SECRET=你的AccessKeySecret \
./scripts/install.sh
```

也可以直接改 `.env` 里的 `DEEPSEEK_API_KEY`、`ALIYUN_OCR_ACCESS_KEY_ID`、`ALIYUN_OCR_ACCESS_KEY_SECRET`，再运行 `./scripts/install.sh`。留空或保持 `sk-CHANGE_ME` 时，应用会启动并在日志里警告，对应功能不可用。

### 停止、更新、备份

```bash
docker compose -f docker-compose.prod.yml stop    # 停止，保留数据卷
docker compose -f docker-compose.prod.yml start   # 再次启动
docker compose -f docker-compose.prod.yml logs -f
```

更新代码并重建：

```bash
git pull
./scripts/install.sh
```

备份与恢复（生产栈需在运行）：

```bash
./backups/backup.sh
./backups/backup.sh --restore backups/core_accounting_YYYYMMDD-HHMMSS.sql.gz
```

备份与恢复默认使用数据库容器中的 `POSTGRES_USER` 和 `POSTGRES_DB`，因此也适用于 `.env` 中自定义的 `DB_USER` / `DB_NAME`；需要临时覆盖时，可在运行备份脚本时显式设置这两个变量。使用自定义 Compose 项目名的部署，备份时也要沿用同一个 `COMPOSE_PROJECT_NAME`。

`docker compose -f docker-compose.prod.yml down` 会删掉容器，但保留数据库、Redis 和上传文件卷。`down -v` 会删掉这些卷，账套数据无法从卷里恢复。

这套栈对外是 HTTP。需要 HTTPS 时，在 Nginx 前面加 TLS 代理，并把 `PUBLIC_URL` 和 `CORS_ORIGINS` 改成浏览器里的 `https://` 源，然后重新运行 `./scripts/install.sh`。

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
scripts/install.sh       生产环境一条命令安装
deploy/nginx/Dockerfile  生产前端构建与 Nginx 镜像
.github/workflows/       CI 配置
.env.example             生产环境变量模板（不含真实密钥）
docker-compose.yml       本地开发基础服务
docker-compose.prod.yml  生产部署
nginx.conf               生产反向代理与前端静态文件
LICENSE                  MIT 许可证
```

## 参与和反馈

欢迎通过 [Issues](https://github.com/EricRenForCode/core-accounting/issues) 反馈问题或提交 Pull Request。报告问题时请提供复现步骤、版本、预期与实际行为；使用脱敏示例，不上传实际企业账目、密钥或个人信息。

## 许可证

Core Accounting 源码采用 [MIT 许可证](LICENSE)。项目依赖与第三方素材保留各自的许可证，MIT 授权不替代它们的授权条款。
