# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    chromium \
    chromium-driver \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p \
    jewelry_dataset/raw_data \
    jewelry_dataset/processed_data \
    jewelry_dataset/datasets \
    logs \
    config \
    temp

# Set Chrome environment variables
ENV CHROME_BIN=/usr/bin/chromium \
    CHROME_PATH=/usr/lib/chromium/ \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Set permissions
RUN chmod -R 777 /app/jewelry_dataset \
    && chmod -R 777 /app/logs \
    && chmod -R 777 /app/config \
    && chmod -R 777 /app/temp

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "run.py"]