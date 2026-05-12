FROM python:3.11-slim

WORKDIR /app

# Install deps first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY web/ /app/

# 👇 IMPORTANT: now manage.py is directly in /app
# because we copied contents of web INTO /app

#CMD ["python", "manage.py", "runserver", "0.0.0.0:8085"]
RUN pip install gunicorn

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8085"]
