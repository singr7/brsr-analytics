# Public edge: the built frontend bundle plus the reverse proxy, in one image.
# Build from the repository root:
#   docker build -f infra/deploy/web.Dockerfile \
#     --build-arg VITE_API_URL=https://brsrlens.example.com -t <registry>/brsrlens/web:<tag> .

# --- build ------------------------------------------------------------------
FROM node:20-alpine AS build

RUN corepack enable
WORKDIR /build

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend ./

# Baked into the bundle at build time. Point it at the public origin; nginx
# serves the API on the same origin, so no CORS preflight is involved.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

# `build` runs tsc, vite build and the prerender pass that writes the indexable
# public route snapshots.
RUN pnpm run build

# --- runtime ----------------------------------------------------------------
FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY --from=build /build/dist /usr/share/nginx/html
COPY infra/deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY infra/deploy/nginx/proxy-common.conf /etc/nginx/proxy-common.conf
COPY infra/deploy/nginx/security-headers.conf /etc/nginx/security-headers.conf
COPY infra/deploy/nginx/entrypoint.sh /docker-entrypoint.d/05-bootstrap-tls.sh

RUN chmod +x /docker-entrypoint.d/05-bootstrap-tls.sh

EXPOSE 80 443
