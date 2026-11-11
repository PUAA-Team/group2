ARG CONTROL_IMAGE=model-platform-control:20261031-13b4
FROM ${CONTROL_IMAGE}
USER 0:0
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1+cpu \
    && python -m pip install --no-cache-dir safetensors==0.8.0 \
    && python -m pip check
RUN python -m pip install --no-cache-dir numpy==2.2.6 && python -m pip check
ENV OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
USER 10001:10001
