FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY config config
COPY core core
COPY tenancy tenancy
COPY trading trading
COPY terminal terminal
COPY manage.py ./
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 fx && chown -R fx:fx /app
USER fx
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
