# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Final image
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/install/bin:${PATH}"
ENV PYTHONPATH="/install/lib/python3.13/site-packages"

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    netcat-openbsd \
    curl \
    gosu \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /install

# Create non-root user
RUN useradd -m vibarr && \
    mkdir -p /app/logs /app/data /app/staticfiles && \
    chown -R vibarr:vibarr /app

# Copy project files
COPY --chown=vibarr:vibarr . /app/

RUN chmod +x /app/entrypoint.sh

USER vibarr

ENTRYPOINT ["/app/entrypoint.sh"]
