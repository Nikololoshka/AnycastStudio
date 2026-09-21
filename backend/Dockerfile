FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SQLITE_PATH=/data/db.sqlite3

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user; /data holds the SQLite database (mounted as a volume).
RUN useradd --system --uid 1000 app && mkdir /data && chown app /data
USER app

EXPOSE 8000

# Apply migrations, then serve. Access log is off: the callback query string carries the OAuth code.
# The port is published only on the host's loopback, so trusting proxy headers from any peer is safe.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --no-access-log --proxy-headers --forwarded-allow-ips '*'"]
