FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY publisher/frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY publisher/frontend/ ./
ARG PUBLISHER_BASE_PATH=/
RUN npm run build -- --base="$PUBLISHER_BASE_PATH"

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PUBLISHER_DATA_DIR=/app/data
WORKDIR /app
COPY publisher/requirements.txt /app/requirements.txt
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.txt && useradd --uid 10001 --create-home publisher
COPY publisher/__init__.py /app/publisher/__init__.py
COPY publisher/backend /app/publisher/backend
COPY publisher/config /app/publisher/config
COPY publisher/templates /app/publisher/templates
COPY --from=frontend /build/dist /app/publisher/frontend/dist
RUN mkdir -p /app/data && chown publisher:publisher /app/data
USER publisher
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)"
CMD ["uvicorn", "publisher.backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
