# Backend Dockerfile — FastAPI + Geospatial Stack
FROM python:3.11-slim

# Prevent Python from writing bytecode and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system libraries for geospatial packages (GDAL, GEOS, PROJ)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY . .

# Expose port
EXPOSE 8000

# Start Uvicorn application server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
