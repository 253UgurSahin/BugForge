# Laravel: one Dockerfile, two images. docker compose builds both:
#   app  PHP-FPM running the Laravel code
#   web  nginx serving public/ and passing PHP requests to app
# Base images are pinned to major.minor. `docker compose build --pull` picks up their security fixes.

# PHP with what Laravel needs for MariaDB. OPcache is built into PHP 8.5.
FROM php:8.5-fpm-alpine AS base
RUN docker-php-ext-install pdo_mysql \
    && mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini"
WORKDIR /var/www/html

# PHP packages, without the dev tools.
FROM base AS vendor
COPY --from=composer:2.10 /usr/bin/composer /usr/bin/composer
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-interaction --prefer-dist --no-scripts --no-autoloader
COPY . .
RUN mkdir -p bootstrap/cache && composer dump-autoload --no-dev --optimize

# CSS and JavaScript, built by Vite into public/build. .dockerignore keeps .env out of the build, so
# each VITE_ value comes in as a build arg that docker-compose.yml sets: VITE_APP_NAME, the app's
# name, from APP_NAME in .env. Vite writes them into the JavaScript, for every visitor to read:
# public values only, never a secret. Another one: an ARG line here and the arg in docker-compose.yml.
FROM node:24-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY --from=vendor /var/www/html ./
ARG VITE_APP_NAME
RUN npm run build

# The app image. The code belongs to root; the app may write only to storage/ and bootstrap/cache.
# mkdir makes Laravel's folders, which .dockerignore may have left out.
FROM base AS app
COPY --from=vendor /var/www/html ./
COPY --from=assets /app/public/build ./public/build
RUN mkdir -p storage/app/public storage/framework/cache/data storage/framework/sessions \
        storage/framework/views storage/logs bootstrap/cache \
    && chown -R www-data:www-data storage bootstrap/cache \
    && php artisan storage:link
USER www-data
EXPOSE 9000
# On every start: cache config, routes and views, run new migrations, then serve.
CMD ["sh", "-c", "php artisan config:cache && php artisan route:cache && php artisan view:cache && php artisan migrate --force && exec php-fpm"]

# The web image: nginx with the public files, as the unprivileged nginx user, on port 8080.
FROM nginxinc/nginx-unprivileged:1.30-alpine AS web
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=app /var/www/html/public /var/www/html/public
USER nginx
EXPOSE 8080
