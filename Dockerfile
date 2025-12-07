# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for file processing
# lxml needs libxml2-dev and libxslt1-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better layer caching
COPY pyproject.toml ./

# Create minimal app structure for package installation
RUN mkdir -p app && touch app/__init__.py

# Install dependencies using pip
# This layer will be cached unless pyproject.toml changes
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application code (overwrites the minimal structure)
# This layer will be rebuilt when app code changes
COPY app/ ./app/

# Create logs directory
RUN mkdir -p logs

# Copy and set up entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run uvicorn with the FastAPI app
# Cloud Run sets PORT env var dynamically, defaulting to 8080
# Using JSON array format for proper signal handling
CMD ["/app/entrypoint.sh"]

