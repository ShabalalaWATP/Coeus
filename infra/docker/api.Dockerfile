FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md apps/api/alembic.ini ./apps/api/
COPY apps/api/src ./apps/api/src

WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev

RUN addgroup --system coeus \
    && adduser --system --ingroup coeus coeus \
    && install -d -o coeus -g coeus /var/lib/coeus

USER coeus

EXPOSE 8000
CMD ["sh", "-c", "exec /app/apps/api/.venv/bin/uvicorn coeus.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1"]
