FROM python:3.11-slim

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Remove any .pyc files and __pycache__ directories
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Create directory for SQLite database and set permissions
RUN mkdir -p /data && chmod 777 /data

# Expose port (Fly.io uses internal port)
EXPOSE 8080

# Initialize database and run the application
CMD ["sh", "-c", "python init_db.py && alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8080"]
