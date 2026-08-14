FROM node:20-alpine

RUN corepack enable
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
CMD ["pnpm", "dev"]

