FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# 서버 RAM 2GB 제약 — Node 힙 상한을 낮춰 OOM/데몬 멈춤 방지 (2026-07-12)
ENV NODE_OPTIONS=--max-old-space-size=1280
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# 배포 신선도 마커 — 커밋 SHA 를 이미지에 새겨 스테일 web 이미지를 감지 (2026-07-12)
ARG GIT_SHA=dev
RUN echo "$GIT_SHA" > /app/BUILD_SHA
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
