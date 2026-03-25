FROM python:3.12-slim

# Keep logs unbuffered and disable .pyc generation inside container.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first to leverage Docker layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files into container image.
COPY . .

# Ensure directory for sqlite file exists in the container filesystem.
RUN mkdir -p /app/data

# Expose Flask port.
EXPOSE 5000

# Start the Flask app for local development/demo usage.
CMD ["python", "app.py"]
