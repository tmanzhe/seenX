# syntax=docker/dockerfile:1

# Digests pin the multi-platform images; Dependabot proposes updates.
FROM node:24-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS dependencies
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

FROM dependencies AS builder
COPY apps/web ./apps/web
RUN npm run typecheck && npm test && npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine-slim@sha256:5d8bb9437d74a600ec5dbf90c035451c724dc33eac8d3a71078f6f8612c345f6 AS runtime
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=builder /app/apps/web/out /usr/share/nginx/html
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
# Skip the image's configuration-mutating entrypoint so read-only mode works.
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
