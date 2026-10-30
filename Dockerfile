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
# nodejs: مطلوب لتوليد صفحات المقالات المُسبقة العرض (prerender.py يشغّل مُصيِّر
# article.html نفسه داخل node:vm بدل إعادة كتابته — فلا تتفرّع نسختان من المُصيِّر).
# لو فشل تثبيته لأي سبب، الميزة بتتعطّل لوحدها والداشبورد بيقوم عادي (فحص وقت التشغيل
# في _prerender_push) — الداشبورد بيخدّم فيد مقالات الموقع الحيّ فما ينفعش يقع علشانها.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && mkdir -p /data

COPY backend/app.py /app/app.py
COPY backend/v2_courses_routes.py /app/v2_courses_routes.py
COPY backend/prerender.py /app/prerender.py
# refresh_rules.py: المُتحقِّق المشترك مع المنصّة — app.py يستورده عند الإقلاع (غيابه = الحاوية لا تقوم)
COPY backend/refresh_rules.py /app/refresh_rules.py
# v2_<قسم>_routes.py: مسارات أقسام الجولة النهائية — app.py يستوردها عند الإقلاع (غيابها = الحاوية لا تقوم)
COPY backend/v2_market_routes.py /app/v2_market_routes.py
COPY backend/v2_books_routes.py /app/v2_books_routes.py
# The new cloud-design dashboard becomes the served frontend (Flask serves /app/dist).
# Only the live app files are shipped — the standalone prototype HTMLs
# (Dashboard-Outputs.html / Dashboard-State.html) are unreferenced and not deployed.
COPY dashboard-cloud/index.html dashboard-cloud/dashboard-api.js dashboard-cloud/site-content.js /app/dist/
# D1 · اللوحة الجديدة (ورا مفتاح DASH_V2_ENABLED): منطقها النقي + رسمها + تنسيقها + صور المربّعات.
# D1-B · الهيكل الجديد (قوائم الأقسام والتبويبات).
COPY dashboard-cloud/v2-logic.js dashboard-cloud/v2-home.js dashboard-cloud/v2-home.css dashboard-cloud/v2-shell.js dashboard-cloud/v2-shell.css dashboard-cloud/v2-d2.js dashboard-cloud/v2-d2.css dashboard-cloud/v2-d3.js dashboard-cloud/v2-d3.css /app/dist/
COPY dashboard-cloud/v2/img /app/dist/v2/img
# الجولة الأخيرة · أقسام v2s (المحتوى…): واجهة كل قسم في ملفاته + مسارات الخادم في وحدة مستقلة (app.py يستوردها عند الإقلاع — غيابها = الحاوية لا تقوم).
COPY backend/v2_content_routes.py /app/v2_content_routes.py
COPY backend/v2_marketing_routes.py /app/v2_marketing_routes.py
COPY dashboard-cloud/v2s /app/dist/v2s

EXPOSE 8080

CMD ["sh", "-c", "gunicorn app:app -b 0.0.0.0:${PORT:-8080} -w 1 --timeout 120"]
