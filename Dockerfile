# Dashboard = Flask (API at /api/*) serving the NEW cloud-design frontend from /app/dist.
# We drop the old React build and serve the cloud design (dashboard-cloud/) as the frontend,
# so dashboard.elprofessor.net shows the new design AND keeps the Flask backend alive (the
# site's CMS/contact + SSO + the upcoming data-wiring all need /api/*). Design-first: the
# new design ships with its built-in data for now; real-data wiring is the next phase.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    FLASK_DEBUG=false

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && mkdir -p /data

COPY backend/app.py /app/app.py
# The new cloud-design dashboard becomes the served frontend (Flask serves /app/dist).
COPY dashboard-cloud/index.html dashboard-cloud/dashboard-api.js dashboard-cloud/site-content.js dashboard-cloud/Dashboard-Outputs.html dashboard-cloud/Dashboard-State.html /app/dist/

EXPOSE 8080

CMD ["sh", "-c", "gunicorn app:app -b 0.0.0.0:${PORT:-8080} -w 1 --timeout 120"]
