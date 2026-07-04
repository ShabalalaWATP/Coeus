FROM node:22-alpine AS runtime

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @coeus/web...

COPY apps/web ./apps/web

EXPOSE 5173
CMD ["pnpm", "--filter", "@coeus/web", "dev", "--host", "0.0.0.0"]

