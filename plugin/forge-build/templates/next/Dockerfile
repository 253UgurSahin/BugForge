# Next.js on Node, from the standalone build (next.config: output: "standalone"). No nginx:
# the Node server serves everything. Base images are pinned to major.minor (Node LTS).
# `docker compose build --pull` picks up their security fixes.

# Packages, exactly as package-lock.json says.
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# The production build. NEXT_PUBLIC_ values are baked into the JavaScript here: put them in
# .env.production (public values only, never a secret).
FROM node:24-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# The app image: the standalone server, its static files and the database migrations.
# The code belongs to root; the server may write only to .next/cache.
FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
# Drizzle's SQL migrations. instrumentation.ts runs them when the server starts.
COPY --from=build /app/drizzle ./drizzle
RUN mkdir -p .next/cache && chown node:node .next/cache
USER node
EXPOSE 3000
CMD ["node", "server.js"]
