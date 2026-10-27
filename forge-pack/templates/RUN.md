# Running {{App name}}

{{App name}} runs in Docker containers, on your own computer or on a server you control.
Everything it needs is in this folder: `Dockerfile`, `docker-compose.yml`, `.env.example`.
Lines marked Laravel, Django, Next.js or Static apply only to that kind of app.

## What you need

- Docker Engine with the Compose plugin: `docker compose version` must work.
- `openssl` to make passwords (Linux and macOS have it).

## First start

1. Copy the settings file: `cp .env.example .env`. Never commit `.env`: it holds your secrets.
2. Open `.env` and give every `change-me` a new value. Make each one with `openssl rand -hex 24`.
   - Laravel: also `APP_KEY`, made with `echo "base64:$(openssl rand -base64 32)"`.
   - Fill in your SMTP server (the `MAIL_` or `SMTP_` lines) and your Stripe test keys.
3. Build and start: `docker compose up -d --build --wait`. The first build takes a few minutes.
   The command returns once every service is `healthy`; `docker compose ps` shows them.
4. Open http://localhost:8080.

The database is created on the first start. New migrations run by themselves each time the app
starts. Django: make your admin account with `docker compose exec app python manage.py createsuperuser`.

## Day to day

| what | command |
| --- | --- |
| what is running | `docker compose ps` |
| logs | `docker compose logs -f app` (Laravel also `web` and `worker`; Static: `web`) |
| stop / start again | `docker compose stop` / `docker compose start` |
| remove the containers, keep the data | `docker compose down` |
| run migrations by hand | Laravel: `docker compose exec app php artisan migrate --force` |
| | Django: `docker compose exec app python manage.py migrate` |
| | Next.js: `docker compose restart app` (migrations run on start) |

`docker compose down -v` deletes the database and the uploads. Only use it when you mean that.

## Backups

The data lives in Docker volumes: the database in `db-data`, uploads in `storage` (Laravel) or
`media` (Django). Back up with these commands while the app runs. The passwords are read inside
the container, so they never show up in your shell history. Static sites have no data: back up
the code.

Database, Laravel (MariaDB):

```sh
docker compose exec -T db sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb-dump --single-transaction -u "$MARIADB_USER" "$MARIADB_DATABASE"' | gzip > db-$(date +%F).sql.gz
```

Database, Django and Next.js (PostgreSQL):

```sh
docker compose exec -T db sh -c 'pg_dump --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > db-$(date +%F).sql.gz
```

Uploads:

```sh
docker compose exec -T app tar czf - -C /var/www/html/storage app > uploads-$(date +%F).tgz   # Laravel
docker compose exec -T app tar czf - -C /app media > uploads-$(date +%F).tgz                  # Django
```

Check a database backup: `gunzip -c db-2026-01-31.sql.gz | grep -c 'CREATE TABLE'` shows how many
tables it holds. 0 means the dump failed, even though the file exists. Copy the backups to another
machine, and try a restore now and then: a backup you never restored is a hope, not a backup.

## Restore

The database: stop the app first, so nothing writes while you restore (Laravel:
`docker compose stop web app worker`; Django and Next.js: `docker compose stop app`). Then:

```sh
# Laravel (MariaDB)
gunzip -c db-2026-01-31.sql.gz | docker compose exec -T db sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -u "$MARIADB_USER" "$MARIADB_DATABASE"'
# Django and Next.js (PostgreSQL)
gunzip -c db-2026-01-31.sql.gz | docker compose exec -T db sh -c 'psql -q -v ON_ERROR_STOP=1 -o /dev/null -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Then `docker compose start` and check the app. Uploads go back while the app runs:

```sh
docker compose exec -T app tar xzf - -C /var/www/html/storage < uploads-2026-01-31.tgz   # Laravel
docker compose exec -T app tar xzf - -C /app < uploads-2026-01-31.tgz                    # Django
```

## Updates

1. Make a backup (above).
2. Get the new code, for example with `git pull`.
3. `docker compose up -d --build --wait`. It rebuilds, restarts and runs new migrations.

Security fixes for the base images (PHP, Python, Node, nginx, the databases): once a month run
`docker compose build --pull && docker compose pull --ignore-buildable && docker compose up -d --wait`.
The database stays on its major version (`mariadb:11.8`, `postgres:18-alpine`). Moving to a new
major version takes a backup, the new image in `docker-compose.yml`, a fresh volume and a restore.

## Your own domain with HTTPS

The app listens on `127.0.0.1:8080`, so only this machine can reach it. To put it online, run a
reverse proxy on the same machine that handles HTTPS and passes requests to `127.0.0.1:8080`. Any
proxy you know works (Caddy, nginx, Traefik). With Caddy, which gets and renews the certificate by
itself:

1. Point your domain's DNS (an A record, and AAAA for IPv6) to the server. Open ports 80 and 443.
2. Install Caddy (see caddyserver.com/docs/install) and put this in `/etc/caddy/Caddyfile`:

   ```
   app.example.com {
       reverse_proxy 127.0.0.1:8080
       header Strict-Transport-Security "max-age=31536000"
   }
   ```

3. `sudo systemctl reload caddy`, then open https://app.example.com.
4. Tell the app its address in `.env`, then run `docker compose up -d`:
   - Laravel: `APP_URL=https://app.example.com` and `SESSION_SECURE_COOKIE=true`. The app must
     trust the proxy: `$middleware->trustProxies(at: '*');` in `bootstrap/app.php`.
   - Django: add `app.example.com` to `DJANGO_ALLOWED_HOSTS` and set
     `DJANGO_CSRF_TRUSTED_ORIGINS=https://app.example.com`. The app must trust the proxy:
     `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` in `settings.py`.
   - Next.js: `BETTER_AUTH_URL=https://app.example.com`.
   - Stripe: point the webhook in the Stripe dashboard to your domain.

## Before other people use it

- [ ] Every `change-me` in `.env` has a new value; `APP_DEBUG=false` (Laravel) or `DJANGO_DEBUG=false` (Django).
- [ ] `COMPOSE_PROFILES=dev` is gone from `.env` and your real SMTP server is set.
- [ ] HTTPS works and the app knows its https:// address (above).
- [ ] A backup ran, and a restore of it worked.
- [ ] Stripe still uses test keys. Switching to live keys is your own decision and your own step.

## When something is wrong

- A service is not `healthy`: `docker compose logs app --tail 100` (or `web`, `db`) says why.
- "set DB_PASSWORD in .env": `.env` is missing or its `DB_PASSWORD` is empty.
- You changed `DB_PASSWORD` after the first start and the app cannot log in: the database keeps the
  password it was created with. Put the old one back, or change it inside the database.
- Port 8080 is taken: change the first `8080` under `ports:` in `docker-compose.yml`.
- You cannot stay logged in over plain http (some browsers drop secure cookies there): until HTTPS
  works, set `SESSION_SECURE_COOKIE=false` (Laravel) or `DJANGO_DEBUG=true` (Django, only on your
  own computer).
