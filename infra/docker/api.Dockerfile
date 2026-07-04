FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md ./apps/api/
COPY apps/api/src ./apps/api/src

WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev

RUN addgroup --system coeus && adduser --system --ingroup coeus coeus && chown -R coeus:coeus /app

USER coeus

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "coeus.main:app", "--host", "0.0.0.0", "--port", "8000"]
