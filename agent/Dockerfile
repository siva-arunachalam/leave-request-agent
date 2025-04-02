# agent/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN addgroup --system app && adduser --system --group app

# Install system dependencies if needed (e.g., build tools if a library requires them)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
# Consider using virtual environment steps if preferred
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code into the image
# Assuming agent code is in agent/src or similar relative to this Dockerfile
COPY . . 

# Ensure correct ownership
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Command to run the agent application
# Adjust 'main.py' if your entrypoint script is named differently
# CMD ["python", "main.py"]
CMD ["/bin/bash"]

