# Django served by gunicorn. WhiteNoise serves the static files, so there is no nginx.
# Base images are pinned to major.minor. `docker compose build --pull` picks up their security fixes.

# Python packages, installed into a virtualenv that the app image copies.
FROM python:3.14-slim AS build
# MariaDB instead of Postgres: mysqlclient needs a compiler and the client headers.
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev
ENV PATH="/opt/venv/bin:$PATH" PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY requirements.txt .
RUN pip install -r requirements.txt

# The app image. The code belongs to root; the app may write only to media/ (uploads).
FROM python:3.14-slim
# MariaDB instead of Postgres: the client library mysqlclient uses.
# RUN apt-get update && apt-get install -y --no-install-recommends libmariadb3 && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY . .
# Static files are collected now. The throwaway key only lets settings.py load; the real one is in .env.
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
    && mkdir -p media && chown app:app media
USER app
EXPOSE 8000
# On every start: run new migrations, then serve. config.wsgi belongs to a project made with
# `django-admin startproject config .`: change it if yours has another name.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
