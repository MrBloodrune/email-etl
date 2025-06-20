# Multi-stage Dockerfile for Email ETL Pipeline

# Base stage with common dependencies
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt requirements-api.txt ./

# Install base Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY main.py ./
COPY docker-entrypoint.sh ./

# Create necessary directories
RUN mkdir -p /app/emails /app/logs /app/tokens && \
    chmod +x /app/docker-entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ETL stage - for CLI and worker
FROM base as etl

# Copy scripts for database operations
COPY scripts/ ./scripts/

# Create a non-root user for security
RUN useradd -m -u 1000 etluser && \
    chown -R etluser:etluser /app

USER etluser

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Set default command for interactive CLI
CMD ["cli"]

# API stage - for REST API server
FROM base as api

# Install API-specific dependencies
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy API server
COPY api_server.py ./

# Create a non-root user for security
RUN useradd -m -u 1000 apiuser && \
    chown -R apiuser:apiuser /app

USER apiuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command
CMD ["api"]

# Development stage with additional tools
FROM etl as development

USER root

# Install development tools
RUN apt-get update && apt-get install -y \
    vim \
    less \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install development Python packages
RUN pip install --no-cache-dir \
    ipython \
    ipdb \
    pytest \
    black \
    flake8

USER etluser

# Set development environment
ENV ENVIRONMENT=development

CMD ["/bin/bash"]