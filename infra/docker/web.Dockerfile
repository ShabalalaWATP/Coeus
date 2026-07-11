FROM node:26-alpine@sha256:e88a35be04478413b7c71c455cd9865de9b9360e1f43456be5951032d7ac1a66 AS runtime

WORKDIR /app

RUN npm install --global --ignore-scripts npm@12.0.1 pnpm@11.11.0

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @coeus/web...

COPY apps/web ./apps/web

RUN chown -R node:node /app

USER node

EXPOSE 5173
CMD ["pnpm", "--filter", "@coeus/web", "dev", "--host", "0.0.0.0"]
