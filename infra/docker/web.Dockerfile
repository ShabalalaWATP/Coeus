FROM node:26-alpine AS runtime

WORKDIR /app

RUN npm install --global pnpm@11.7.0

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @coeus/web...

COPY apps/web ./apps/web

RUN chown -R node:node /app

USER node

EXPOSE 5173
CMD ["pnpm", "--filter", "@coeus/web", "dev", "--host", "0.0.0.0"]
