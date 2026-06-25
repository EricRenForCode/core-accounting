# Core Accounting — Backend

Enterprise-grade Chinese accounting system API built with FastAPI.

## Tech Stack

- **Framework:** FastAPI 0.111 + Uvicorn (ASGI)
- **Language:** Python 3.11+
- **Database:** PostgreSQL 15 (asyncpg driver, SQLAlchemy 2.0 async ORM)
- **Cache / Queue:** Redis 7, Celery 5
- **Auth:** JWT (access + refresh tokens), RBAC with 3 roles
- **AI:** DeepSeek API via LangChain/OpenAI-compatible client (voucher generation, NL query, report interpretation)
- **Migrations:** Alembic (async)

## Prerequisites

- Python 3.11+
- PostgreSQL 15
- Redis 7
- (Optional) Docker & Docker Compose

## Quick Start

### 1. Start infrastructure with Docker Compose

From the project root (`core-accounting/`):

```bash
docker compose up -d db redis
```

This starts PostgreSQL on `:5432` and Redis on `:6379`.

### 2. Set up environment variables

```bash
cd backend
cp .env.example .env
```

Edit `.env` and update the key values:

| Variable | What to set |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://accounting:accounting@localhost:5432/core_accounting` |
| `AI_READONLY_DATABASE_URL` | `postgresql+asyncpg://accounting:accounting@localhost:5432/core_accounting` |
| `JWT_SECRET` | Run `openssl rand -hex 32` and paste the output |
| `DEEPSEEK_API_KEY` | Your DeepSeek API key (for AI features) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` |
| `DEEPSEEK_FALLBACK_MODEL` | `deepseek-v4-pro` |

### 3. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the development server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now live at [http://localhost:8000](http://localhost:8000).

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

## Running with Docker (full stack)

To run backend, frontend, DB, Redis, and Celery worker together:

```bash
docker compose up -d --profile full
```

The backend will be at `:8000` and frontend at `:5173`.

## Project Structure

```
backend/
├── alembic/              # Database migrations
├── app/
│   ├── ai/               # AI/LLM modules (voucher gen, NL query, reports)
│   ├── api/v1/           # API route handlers (auth, vouchers, accounts, etc.)
│   ├── core/             # Database, middleware, security, errors, audit
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── config.py         # App settings (pydantic-settings)
│   └── main.py           # FastAPI app entry point
├── .env.example          # Environment variable template
├── alembic.ini           # Alembic config
├── Dockerfile            # Multi-stage Docker build
├── requirements.txt      # Pinned Python dependencies
└── pyproject.toml        # Project metadata & flexible deps
```

## API Endpoints (Overview)

| Group | Prefix | Description |
|---|---|---|
| Auth | `/api/v1/auth` | Login, refresh, logout, current user |
| Vouchers | `/api/v1/vouchers` | CRUD, audit, post, reverse, import/export |
| Accounts | `/api/v1/accounts` | Chart of accounts tree |
| Reports | `/api/v1/reports` | Trial balance, general ledger, statements |
| Periods | `/api/v1/periods` | Period open/close, carry-forward |
| AI | `/api/v1/ai` | Smart voucher, NL query, report interpretation |
| Admin | `/api/v1/admin` | Users, roles, audit logs |
| Health | `/api/v1/health` | DB + Redis connectivity check |

## Creating the initial admin user

After migrations, seed an admin user manually via SQL:

```sql
-- Generate password hash first:
-- python -c "from passlib.context import CryptContext; pwd = CryptContext(schemes=['bcrypt'], bcrypt__rounds=12); print(pwd.hash('your_password'))"

INSERT INTO users (id, username, password_hash, display_name, role_id, is_enabled)
VALUES (gen_random_uuid(), 'admin', '$2b$12$...', '系统管理员', '<admin_role_uuid>', true);
```

## Useful Commands

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Run tests
pytest

# Run with coverage
pytest --cov=app
```
