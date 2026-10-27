FROM python:3.11-slim

# Prevent Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 스레드마다 힙을 따로 늘리지 않게 묶는다. 사진 처리를 run_in_threadpool 로 돌리기
# 때문에, 이것이 없으면 쓰고 버린 공간이 스레드별 arena 에 흩어져 남아 RSS 가
# 톱니처럼 올라가기만 한다(2026-10-27 OOM, exit 137). app/services/memory_guard.py 참고.
ENV MALLOC_ARENA_MAX=2

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
# 부팅은 boot.sh 가 맡는다 — 같은 버전으로 다시 뜰 때는 스키마 맞추기를 건너뛴다.
CMD ["sh", "/app/boot.sh"]
