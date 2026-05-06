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
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /install

# Create non-root user
RUN useradd -m vibarr && \
    mkdir -p /app/logs /app/data && \
    chown -R vibarr:vibarr /app

# Copy project files
COPY --chown=vibarr:vibarr . /app/

# Switch to non-root user
USER vibarr

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
