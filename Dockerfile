# Dockerfile for the FastAPI API service

FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN addgroup --system app && adduser --system --group app

# Install system dependencies (if any needed beyond python)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and script code into the image
# Ensure correct ownership for the non-root user
COPY ./app /app/app
COPY ./scripts /app/scripts
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Expose the port the app runs on
EXPOSE 8000

# Command to run the FastAPI application using Uvicorn
# This will be the default command when starting the container with 'docker-compose up api'
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

