# Dockerfile

# Use the official Python image as the base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Chrome dependencies
RUN apt-get update && apt-get install -y wget unzip xvfb libxi6 libgconf-2-4

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' && \
    apt-get update && apt-get install -y google-chrome-stable

# Clean up APT when done
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Define the default command to run the app
CMD ["python", "app.py"]
