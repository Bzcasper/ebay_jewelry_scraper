# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Chrome and required libraries
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p jewelry_dataset/images \
    jewelry_dataset/metadata \
    jewelry_dataset/raw_html \
    jewelry_dataset/processed_images \
    jewelry_dataset/training_dataset

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CHROMIUM_PATH=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Expose port for Flask
EXPOSE 5000

# Run the Flask application
CMD ["python", "app.py"]