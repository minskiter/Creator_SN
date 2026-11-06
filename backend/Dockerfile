# Build the Vue application first, then package it with the FastAPI service.
FROM node:22-alpine AS frontend-build

WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
# Match the PostgreSQL 18 local baseline; PGDG packages avoid older Debian clients.
ARG PG_MAJOR=18
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gpg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl --fail --silent --show-error --location https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && gpg --batch --show-keys --with-colons /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        | grep -q 'fpr:::::::::B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8:' \
    && . /etc/os-release \
    && printf 'deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt %s-pgdg main\n' "$VERSION_CODENAME" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends "postgresql-client-$PG_MAJOR" \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend/ ./
COPY --from=frontend-build /ui/dist ./static/

ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
