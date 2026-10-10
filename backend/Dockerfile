FROM python:3.12-slim

# System dependencies for asyncpg, PyNaCl, Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY . .

# Non-root user for least privilege
RUN useradd -m -u 1001 pramaan && chown -R pramaan:pramaan /app
USER pramaan

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
