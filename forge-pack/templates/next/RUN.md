# Running {{App name}}

{{App name}} runs in Docker containers, on your own computer or on a server you control.
Everything it needs is in this folder: `Dockerfile`, `docker-compose.yml`, `.env.example`.

## What you need

- Docker Engine with the Compose plugin: `docker compose version` must work.
- `openssl` to make passwords (Linux and macOS have it).

## First start

1. Copy the settings file: `cp .env.example .env`. Never commit `.env`: it holds your secrets.
2. Open `.env` and give every `change-me` a new value. Make each one with `openssl rand -hex 24`.
   Fill in your SMTP server (the `SMTP_` lines) and your Stripe test keys.
3. Build and start: `docker compose up -d --build --wait`. The first build takes a few minutes.
   The command returns once every service is `healthy`; `docker compose ps` shows them.
4. Open http://localhost:8080. Another port: set `APP_PORT` in `.env`, and `BETTER_AUTH_URL` with
   it, or sign-up and login fail.
5. {{First account}}

The database is created on the first start. New migrations run by themselves each time the app
starts.

## Day to day

| what | command |
| --- | --- |
| what is running | `docker compose ps` |
| logs | `docker compose logs -f app` |
| stop / start again | `docker compose stop` / `docker compose start` |
| remove the containers, keep the data | `docker compose down` |
| run migrations by hand | `docker compose restart app` (they run when it starts) |

`docker compose down -v` deletes the database. Only use it when you mean that.

## Backups

The data lives in a Docker volume: the database in `db-data`. Back up with these commands while
the app runs. They write to `~/backups/{{app}}`, outside this folder, so a backup never ends up in
git or in an image. The password is read inside the container, so it never shows up in your shell
history.

```sh
mkdir -p ~/backups/{{app}}
docker compose exec -T db sh -c 'pg_dump --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > ~/backups/{{app}}/db-$(date +%F).sql.gz
```

Check a backup: `gunzip -c ~/backups/{{app}}/db-2026-01-31.sql.gz | grep -c 'CREATE TABLE'` shows
how many tables it holds. 0 means the dump failed, even though the file exists. Copy the backups
to another machine, and try a restore now and then: a backup you never restored is a hope, not a
backup.

## Restore

Stop the app first, so nothing writes while you restore: `docker compose stop app` (and any other
service but `db`). Then:

```sh
gunzip -c ~/backups/{{app}}/db-2026-01-31.sql.gz | docker compose exec -T db sh -c 'psql -q -v ON_ERROR_STOP=1 -o /dev/null -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Then `docker compose start` and check the app.

## Updates

1. Make a backup (above).
2. Get the new code, for example with `git pull`.
3. `docker compose up -d --build --wait`. It rebuilds, restarts and runs new migrations.

Security fixes for the base images (Node, PostgreSQL): once a month run
`docker compose build --pull && docker compose pull --ignore-buildable && docker compose up -d --wait`.
The database stays on its major version (`postgres:18-alpine`). Moving to a new major version
takes a backup, the new image in `docker-compose.yml`, a fresh volume and a restore.

## Your own domain with HTTPS

The app listens on `127.0.0.1:8080` (or the `APP_PORT` in `.env`), so only this machine can reach
it. To put it online, run a reverse proxy on the same machine that handles HTTPS and passes
requests to that address. Any proxy you know works (Caddy, nginx, Traefik). With Caddy, which gets
and renews the certificate by itself:

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
   - `BETTER_AUTH_URL=https://app.example.com`.
   - Stripe: in the Stripe dashboard, add a webhook endpoint on your domain:
     {{Stripe webhook events}}. Put its signing secret in `STRIPE_WEBHOOK_SECRET`.

## Before other people use it

- [ ] Every `change-me` in `.env` has a new value.
- [ ] `COMPOSE_PROFILES=dev` is gone from `.env` and your real SMTP server is set.
- [ ] HTTPS works and `BETTER_AUTH_URL` is the https:// address (above).
- [ ] A backup ran, and a restore of it worked.
- [ ] Stripe still uses test keys. Switching to live keys is your own decision and your own step.

## When something is wrong

- A service is not `healthy`: `docker compose logs app --tail 100` (or `db`) says why.
- "set DB_PASSWORD in .env": `.env` is missing or its `DB_PASSWORD` is empty.
- You changed `DB_PASSWORD` after the first start and the app cannot log in: the database keeps the
  password it was created with. Put the old one back, or change it inside the database.
- Port 8080 (or mailpit's 8025) is taken: set `APP_PORT` and `BETTER_AUTH_URL` (or `MAILPIT_PORT`)
  in `.env`, then `docker compose up -d`.
- Sign-up or login fails with "Invalid origin": `BETTER_AUTH_URL` is not the address in your
  browser's address bar (http or https, the host and the port must all match).
