# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS development
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM development AS builder
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS production
ENV PORT=8080
ENV API_UPSTREAM=http://web:8000
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO- "http://127.0.0.1:${PORT:-8080}/healthz" || exit 1
