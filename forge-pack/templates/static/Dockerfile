# Static site or single-page app: built with Node and Vite, served by nginx.
# Base images are pinned to major.minor. `docker compose build --pull` picks up their security fixes.

# The build. VITE_ values are baked into the JavaScript here: put them in .env.production
# (public values only, never a secret).
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# The web image: nginx with only the built files, as the unprivileged nginx user, on port 8080.
FROM nginxinc/nginx-unprivileged:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
