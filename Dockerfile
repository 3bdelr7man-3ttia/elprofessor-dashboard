FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    FLASK_DEBUG=false

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && mkdir -p /data

COPY backend/app.py /app/app.py
COPY --from=frontend-build /app/frontend/dist /app/dist

EXPOSE 8080

CMD ["sh", "-c", "gunicorn app:app -b 0.0.0.0:${PORT:-8080} -w 1 --timeout 120"]
