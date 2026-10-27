# Running {{App name}}

{{App name}} runs in a Docker container (nginx with the built site), on your own computer or on a
server you control. Everything it needs is in this folder: `Dockerfile`, `docker-compose.yml`,
`nginx.conf`.

## What you need

- Docker Engine with the Compose plugin: `docker compose version` must work.

## First start

1. Build and start: `docker compose up -d --build --wait`. The first build takes a minute or two.
   The command returns once the site is `healthy`; `docker compose ps` shows it.
2. Open http://localhost:8080. Another port: put `APP_PORT=8081` in a `.env` file in this folder.

The site has no secrets, so it needs no `.env` to run. Public build settings (`VITE_` values) are
in `.env.production`, which every visitor can read: never put a secret there.

## Day to day

| what | command |
| --- | --- |
| what is running | `docker compose ps` |
| logs | `docker compose logs -f web` |
| stop / start again | `docker compose stop` / `docker compose start` |
| remove the container | `docker compose down` |

## Backups

The site keeps no data of its own: everything is in this folder. Back up the code, for example
with git and a copy of the repository on another machine.

## Updates

1. Get the new code, for example with `git pull`.
2. `docker compose up -d --build --wait`. It rebuilds and restarts the site.

Security fixes for the base images (Node, nginx): once a month run
`docker compose build --pull && docker compose up -d --wait`.

## Your own domain with HTTPS

The site listens on `127.0.0.1:8080` (or the `APP_PORT` in `.env`), so only this machine can reach
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

## Before other people use it

- [ ] HTTPS works (above).
- [ ] `.env.production` holds no secret: every visitor can read its values.

## When something is wrong

- The site is not `healthy`: `docker compose logs web --tail 100` says why.
- Port 8080 is taken: put `APP_PORT=8081` (or another free port) in `.env`, then
  `docker compose up -d`.
- A page gives 404 when you reload it: the `try_files` line in `nginx.conf` does not fit how the
  site's pages are made (its comment says which version to use).
