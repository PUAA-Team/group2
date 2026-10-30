ARG PYTHON_IMAGE=python:3.12-slim-bookworm
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
COPY worker/src /app/worker/src
COPY deploy/server/entrypoint.py /app/deploy/server/entrypoint.py
COPY scripts/seed_application_presets.py /app/scripts/seed_application_presets.py

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "-B", "/app/deploy/server/entrypoint.py"]
CMD ["serve"]
