# Stage 1 — build the admin-panel SPA.
# VITE_API_BASE is left empty so the SPA calls the API on the same origin
# (Caddy proxies /api, /webhooks, /health, /docs to the backend).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2 — Caddy image that serves the built SPA. The Caddyfile is mounted at
# runtime by docker-compose.prod.yml.
FROM caddy:2-alpine
COPY --from=build /app/dist /srv
