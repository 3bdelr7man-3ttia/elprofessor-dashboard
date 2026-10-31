FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY v2_*_routes.py ./
COPY brain2 ./brain2
# وحدات المستوى الأعلى التي يستوردها app.py عند الإقلاع (غيابها = الحاوية لا تقوم) — تطابق Dockerfile الجذر.
COPY mcp_server.py site_edit.py prerender.py refresh_rules.py ./
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "app:app", "-b", "0.0.0.0:5000", "-w", "2", "--timeout", "120"]
