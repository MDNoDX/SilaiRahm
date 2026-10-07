# Silai Rahm — production image (Django + gunicorn).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# Translations and static files are built into the image.
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build-only python manage.py compilemessages --ignore=.venv \
    && DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app && mkdir -p /app/media && chown -R app:app /app/media
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
