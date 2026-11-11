FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS build

WORKDIR /app

# Install system dependencies needed for compiling ChromaDB or other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /install /usr/local

# Copy backend source code
COPY src/ /app/healer/src/

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "healer.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
