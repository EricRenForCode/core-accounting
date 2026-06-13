# Core Accounting — Frontend

Chinese accounting system UI built with React 19, Vite 8, and TypeScript.

## Tech Stack

- **Framework:** React 19 + TypeScript 6
- **Build tool:** Vite 8
- **Styling:** Tailwind CSS v4
- **Routing:** TanStack Router
- **Server state:** TanStack Query v5
- **Client state:** Zustand v5
- **Forms:** React Hook Form + Zod validation
- **HTTP:** Axios (with JWT auto-refresh)
- **Testing:** Vitest + Testing Library
- **Charts:** Recharts
- **Icons:** Lucide React

## Prerequisites

- Node.js 18+
- pnpm (recommended)
- Backend running at `http://localhost:8000`

## Quick Start

### 1. Install dependencies

```bash
cd frontend
pnpm install
```

### 2. Start the development server

```bash
pnpm dev
```

The app is now live at [http://localhost:5173](http://localhost:5173).

Vite provides hot module replacement — changes appear instantly without a full reload.

### 3. Build for production

```bash
pnpm build
```

The optimized output goes to `dist/`. Preview it with:

```bash
pnpm preview
```

## Project Structure

```
frontend/
├── public/
│   └── icons.svg              # SVG icon sprite
├── src/
│   ├── components/            # Reusable UI components
│   │   ├── layout/            # AppShell, Header, Sidebar, Breadcrumb
│   │   ├── DataTable/         # Generic sortable/selectable data table
│   │   ├── AccountPicker.tsx  # Tree-select for chart of accounts
│   │   ├── AmountInput.tsx    # Formatted numeric input
│   │   ├── BalanceBar.tsx     # Debit/credit indicator
│   │   ├── ConfirmDialog.tsx  # Confirmation modal
│   │   ├── ErrorCard.tsx      # Error display with retry
│   │   └── Skeleton.tsx       # Loading placeholders
│   ├── hooks/                 # Custom React hooks (auth, permissions, period)
│   ├── lib/                   # API client, utils, constants
│   │   ├── api.ts             # Axios instance with JWT interceptors
│   │   ├── utils.ts           # Amount/date formatting, cn() helper
│   │   └── constants.ts       # Roles, statuses, permissions, error codes
│   ├── stores/                # Zustand stores (app state, user/auth)
│   ├── types/                 # TypeScript type definitions
│   ├── __tests__/             # Vitest tests
│   ├── main.tsx               # App entry point
│   ├── index.css              # Tailwind + custom design tokens
│   └── routeTree.tsx          # All route definitions (~40 routes)
├── index.html                 # Entry HTML (lang="zh-CN")
├── vite.config.ts             # Vite config (React, Tailwind, path aliases)
├── vitest.config.ts           # Vitest config (jsdom environment)
├── tsconfig.json              # TypeScript config
├── eslint.config.js           # ESLint flat config
└── package.json
```

## Available Scripts

| Command | Description |
|---|---|
| `pnpm dev` | Start dev server (port 5173, HMR) |
| `pnpm build` | Type-check and build for production |
| `pnpm preview` | Preview production build locally |
| `pnpm lint` | Run ESLint |
| `pnpm test` | Run tests once |
| `pnpm test:watch` | Run tests in watch mode |
| `pnpm test:coverage` | Run tests with coverage report |
| `pnpm format` | Format source files with Prettier |

## Route Overview

| Section | Path | Status |
|---|---|---|
| Dashboard | `/` | Implemented |
| Login | `/login` | Implemented |
| Vouchers | `/vouchers/*` | Placeholder |
| Ledgers | `/ledgers/*` | Placeholder |
| Reports | `/reports/*` | Placeholder |
| Period | `/period/*` | Placeholder |
| Cashier | `/cashier/*` | Placeholder |
| Assets | `/assets/*` | Placeholder |
| AI | `/ai/*` | Placeholder |
| Admin | `/admin/*` | Placeholder |

## Environment

The frontend connects to the backend API at `http://localhost:8000` by default (configured in the Axios client). Make sure the backend is running before using the app.

To run everything together via Docker Compose:

```bash
# From the project root
docker compose up -d --profile full
```
