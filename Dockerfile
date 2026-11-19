# Single-service image: Next.js website + FastAPI backend + background worker in one container.
# Used by the one-click Render deployment (render.yaml). docker-compose.yml remains for multi-service setups.

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ENV API_INTERNAL_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
        tesseract-ocr tesseract-ocr-eng poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node
RUN python3 -m venv /venv
ENV PATH=/venv/bin:$PATH
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /web/.next frontend/.next
COPY --from=web /web/node_modules frontend/node_modules
COPY --from=web /web/public frontend/public
COPY --from=web /web/package.json /web/next.config.ts frontend/
COPY start.sh .
RUN useradd -m app && mkdir -p /app/data && chown -R app /app/data /app/frontend/.next
USER app
ENV RUN_EMBEDDED_WORKER=1 STORAGE_BACKEND=database NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=http://127.0.0.1:8000
EXPOSE 10000
CMD ["sh", "start.sh"]
