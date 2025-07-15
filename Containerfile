# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

# Set workdir
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY app ./app

# Install dependencies
RUN uv pip install --system .

# Copy entrypoint (if any) and .env (optional, for local dev only)
# COPY .env .

# Expose FastAPI port
EXPOSE 8000

# Use a non-root user for security (optional)
# RUN useradd -m appuser && chown -R appuser /app
# USER appuser

# Start FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 
