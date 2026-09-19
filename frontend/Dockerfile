# ---- build -------------------------------------------------------------------
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---- serve -------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime
# Upstream for /api/ requests; override at runtime, e.g. -e API_UPSTREAM=backend:8000
ENV API_UPSTREAM=api:8000 \
    NGINX_ENVSUBST_FILTER=^API_UPSTREAM$
# Run as the unprivileged "nginx" user: move the pid file and make runtime dirs writable.
RUN sed -i -e '/^user /d' -e 's,^pid .*;,pid /tmp/nginx.pid;,' /etc/nginx/nginx.conf \
 && rm -f /etc/nginx/conf.d/default.conf \
 && chown -R nginx:nginx /var/cache/nginx /etc/nginx/conf.d
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
