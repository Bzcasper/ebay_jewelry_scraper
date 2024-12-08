# Use Python 3.9 slim image as the base
FROM python:3.10-slim

# Set environment variables to optimize the Python environment and prevent interactive prompts
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

# Set the working directory for the application
WORKDIR /app

# Copy and install Python dependencies separately to leverage Docker cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the entire application code into the container
COPY . /app

# Create necessary directories for datasets, logs, and configurations
RUN mkdir -p \
    jewelry_dataset/raw_data \
    jewelry_dataset/processed_data \
    jewelry_dataset/datasets \
    logs \
    config \
    temp

# Set Chrome-related environment variables
ENV CHROME_BIN=/usr/bin/chromium \
    CHROME_PATH=/usr/lib/chromium/ \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Adjust directory permissions for accessibility
RUN chmod -R 777 /app/jewelry_dataset \
    && chmod -R 777 /app/logs \
    && chmod -R 777 /app/config \
    && chmod -R 777 /app/temp

# Expose the Flask application port
EXPOSE 5000

# Set the default command to run the application
CMD ["python", "run.py"]
