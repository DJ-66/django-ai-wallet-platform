FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY web/ /app/

RUN pip install gunicorn

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8085"]

