FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000", "-w", "2", "--timeout", "120"]
