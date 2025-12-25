# Use the official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# 1. Install system dependencies
TunRUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. CONFIGURE PLAYWRIGHT (The Critical Fix)
# Set a global path for browsers so both Root (builder) and User (runner) can find them
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH

# Install the necessary system dependencies and the Chromium browser
RUN playwright install-deps chromium
RUN playwright install chromium

# 4. Copy Application Code
COPY . .

# 5. Create and Switch to Non-Root User
RUN useradd -m -u 1000 user

# Ensure the user has permissions to access the browsers
RUN chmod -R 755 $PLAYWRIGHT_BROWSERS_PATH

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# 6. Run the App
EXPOSE 7860
CMD ["python", "app.py"]
