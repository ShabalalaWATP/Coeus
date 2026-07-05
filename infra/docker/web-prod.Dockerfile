FROM node:26-alpine AS build

WORKDIR /app

RUN npm install --global pnpm@11.7.0

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @coeus/web...

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY apps/web ./apps/web
RUN pnpm --filter @coeus/web build

FROM nginx:1.31-alpine AS runtime

RUN apk upgrade --no-cache

COPY infra/docker/nginx-web.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 8080
