ARG NODE_IMAGE=node:22-alpine
ARG PYTHON_IMAGE=python:3.12-slim-bookworm

FROM ${NODE_IMAGE} AS web-builder
WORKDIR /src/frontend/web
COPY frontend/web/package.json frontend/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend /src/frontend
RUN npm run build

FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src \
    MT_RUNTIME_DIR=/runtime \
    MT_ALLOW_BROWSER_SETUP=0 \
    MT_ENABLE_LOCAL_WORKER=0 \
    TMPDIR=/runtime/temp

WORKDIR /app
COPY backend/requirements.lock.txt /app/backend/requirements.lock.txt
COPY deploy/server/wheels /wheels
RUN if [ -n "$(find /wheels -name '*.whl' -print -quit)" ]; then \
        python -m pip install --no-cache-dir --no-index --find-links=/wheels -r /app/backend/requirements.lock.txt; \
    else \
        python -m pip install --no-cache-dir -r /app/backend/requirements.lock.txt; \
    fi \
    && python -m pip check \
    && rm -rf /wheels \
    && groupadd --gid 10001 platform \
    && useradd --uid 10001 --gid platform --no-create-home platform

COPY backend /app/backend
COPY frontend/live /app/frontend/live
COPY frontend/styles /app/frontend/styles
COPY frontend/js /app/frontend/js
COPY --from=web-builder /src/frontend/web/dist /app/frontend/web/dist
COPY worker/src /app/worker/src
COPY deploy/server/entrypoint.py /app/deploy/server/entrypoint.py
COPY scripts/seed_application_presets.py /app/scripts/seed_application_presets.py

# Windows/SCP来源可能保留仅属主可读的模式；公开源码统一可读，运行数据另行挂载。
RUN find /app -type d -exec chmod 755 {} + \
    && find /app -type f -exec chmod 644 {} +

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "-B", "/app/deploy/server/entrypoint.py"]
CMD ["serve"]
