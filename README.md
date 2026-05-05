# ElProfessor Management Dashboard

Dashboard داخلية للإدارة المالية والتسويق والدورات ومساعد قرار AI لمنصة البروفيسور.

## التشغيل المحلي

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

الـ API يعمل افتراضياً على:

```text
http://127.0.0.1:5000/api
```

### Frontend

```bash
cd frontend
npm install
VITE_API_URL=http://127.0.0.1:5000/api npm run dev
```

الواجهة تعمل افتراضياً على:

```text
http://127.0.0.1:5173
```

بيانات الدخول الأولية:

```text
admin@elprofessor.com
admin123
```

## النشر على Coolify

المشروع جاهز للنشر كـ Docker Compose من الملف:

```text
docker-compose.yml
```

في Coolify:

1. أنشئ مشروع جديد باسم `dashboard`.
2. اختر Docker Compose / Git Repository أو ارفع الملفات للمشروع.
3. اجعل الـ domain أو subdomain يشير إلى خدمة `frontend` على port `80`.
4. أضف Environment Variables التالية على الأقل:

```env
SECRET_KEY=ضع-قيمة-طويلة-عشوائية
ADMIN_EMAIL=admin@elprofessor.com
ADMIN_PASSWORD=غيّرها-قبل-الإنتاج
DATABASE_URL=sqlite:////data/elprofessor.db
CORS_ORIGINS=*
```

لتفعيل AI Assistant أضف أي مفاتيح متاحة:

```env
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_MODEL=gpt-4.1-mini
DEEPSEEK_MODEL=deepseek-chat
```

الواجهة تمرر `/api` إلى خدمة الباك إند داخلياً، لذلك يكفي subdomain واحد مثل:

```text
dashboard.elprofessor.com
```

## المكونات

- `backend/app.py`: Flask API + SQLAlchemy + Auth + Seed data + AI proxy.
- `frontend/src/App.jsx`: React dashboard RTL.
- `frontend/nginx/default.conf`: static frontend + reverse proxy للـ API.
- `docker-compose.yml`: تشغيل كامل للباك إند والفرونت إند مع volume لقاعدة SQLite.
