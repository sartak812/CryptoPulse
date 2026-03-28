FROM python:3.12-slim AS builder

# Keep logs unbuffered and disable .pyc generation inside container.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv

WORKDIR /app

# Build dependencies in isolated virtual environment.
COPY requirements.txt ./
RUN python -m venv ${VENV_PATH} \
    && ${VENV_PATH}/bin/pip install --no-cache-dir --upgrade pip \
    && ${VENV_PATH}/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv
ENV PATH="${VENV_PATH}/bin:${PATH}"

WORKDIR /app

# Copy prebuilt environment from builder stage.
COPY --from=builder ${VENV_PATH} ${VENV_PATH}

# Copy project files into runtime image.
COPY . .

# Expose Flask port.
EXPOSE 5000

# Start the Flask app for local development/demo usage.
CMD ["python", "app.py"]
