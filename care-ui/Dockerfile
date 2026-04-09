# ——————————————————————————
# 1. Builder
# ——————————————————————————
FROM node:20-slim AS builder

WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy manifest files
COPY package.json pnpm-lock.yaml ./

# Install dependencies (including devDependencies)
RUN pnpm install

# Copy the rest of the app files
COPY . .

RUN pnpm exec next telemetry disable

# Build Next.js
RUN pnpm build


# ——————————————————————————
# 2. Runner (production)
# ——————————————————————————
FROM node:20-slim AS runner

WORKDIR /app

ENV NODE_ENV=production

# Install pnpm
RUN npm install -g pnpm

# Install only production deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --prod

# Copy build artifacts from builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.ts ./next.config.ts
COPY --from=builder /app/package.json ./package.json

# Port that Next.js listens on
EXPOSE 13000

# Start production server
CMD ["pnpm", "start", "--hostname", "0.0.0.0", "--port", "13000"]
