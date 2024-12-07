# Dockerfile
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxss1 \
    libappindicator3-1 \
    libindicator7 \
    fonts-liberation \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN wget -O /tmp/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver_linux64.zip chromedriver -d /usr/local/bin/ \
    && rm /tmp/chromedriver_linux64.zip \
    && chmod +x /usr/local/bin/chromedriver

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Expose port
EXPOSE 5000

# Set environment variable for Flask
ENV FLASK_APP=app.py

# Run the application
CMD ["python", "app.py"]
