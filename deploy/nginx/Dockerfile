# Production web image: build the Vite app, then serve it with Nginx.
# docker-compose.prod.yml builds this with the repository root as context.
# Local development does not use this image; run the Vite dev server on the host.

FROM node:22-bookworm-slim AS frontend

WORKDIR /src

# Match CI (pnpm 10). Dev dependencies are required for `tsc` and `vite build`.
RUN npm install -g pnpm@10

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm run build

FROM nginx:1.25-alpine

RUN apk add --no-cache wget

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend /src/dist /usr/share/nginx/html

EXPOSE 80
