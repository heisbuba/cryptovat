# Use the official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# CONFIGURE PLAYWRIGHT
# Set a global path for browsers so both Root (builder) and User (runner) can find them
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH

# Install the necessary system dependencies and the Chromium browser
RUN playwright install-deps chromium
RUN playwright install chromium

# Copy Application Code
COPY . .

# Create and Switch to Non-Root User
RUN useradd -m -u 1000 user

# Ensure the user has permissions to access the browsers
RUN chmod -R 755 $PLAYWRIGHT_BROWSERS_PATH

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# 6. Run the App
EXPOSE 7860
# Single worker
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
