# 本机采用原生 Worker 验收；此文件交由具备 Docker/NVIDIA Container Toolkit 的主机构建。
ARG WORKER_BASE_IMAGE=pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime
FROM ${WORKER_BASE_IMAGE}
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
COPY requirements-llm.txt /app/requirements-llm.txt
RUN python -m pip install --no-cache-dir -r /app/requirements-llm.txt && python -m pip check
COPY src /app/src
RUN python -c "import zipapp; zipapp.create_archive('/app/src', '/app/worker.pyz', main='training_worker.cli:main')"
ENTRYPOINT ["python", "-B", "/app/worker.pyz"]
