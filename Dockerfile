# ModelSmith — production container
# CPU-only torch keeps the image lean; everything runs in one service.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODELSMITH_DATA=/data

WORKDIR /app

# CPU wheels first (torch/torchvision), then the rest
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu \
        torch torchvision && \
    pip install -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY README.md run.sh ./

RUN mkdir -p /data/uploads /data/artifacts /data/tmp \
    && chmod +x run.sh

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8100/api/health', timeout=4)"

CMD sh -c "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port \"\${PORT:-8100}\""
