# «كتبنا وأدلّتنا» في الداشبورد (2026-10-31)

طلب المؤسس (عن طريق جلسة الكتب): «ممكن تبعت الداشبورد رفع الكتب والادله وايضا إنشاءها مباشره بالمخ».
القاعدة: «مدار» البساطة. حاجة واحدة واضحة في كل شاشة، والفلوس والعرض بموافقة المؤسس دايمًا.

## عقد المنصة (جاهز في `pillars-books-market@4147444`، مش منشور لسه)
كل نداء بـ`x-elp-metrics-secret` (زي باقي الجسور، عن طريق `_platform_proxy` / `_v2_write`). كل كتابة فيها `by` و`confirmed:true` بالظبط، ولو واحد منهم ناقص ⇒ ٤٢٢ بنص عربي.

- `GET /api/bridge/books/ours` ⇒ `{books:[{id,slug,title,about,type,status:draft|live,file:{name,size,pages,uploaded,uploaded_at}|null,created_by,created_at,updated_at}], types}`
- `POST /api/bridge/books/ours` `{title, about, type: book|guide|research|other, by, confirmed, idem_key?}` ⇒ مسودة
- `PUT /api/bridge/books/ours/{slug}` `{title?, about?, type?, by, confirmed}`
- `POST /api/bridge/books/ours/{slug}/file` multipart: `file` (PDF بس) + `by` ⇒ ٤١٣ لو أكبر من `BOOKS_UPLOAD_MAX_MB`. الرفع الجديد بيبدّل القديم.
- `PUT /api/bridge/books/ours/{slug}/status` `{live, by, confirmed}`. من غير PDF ⇒ ٤٠٩ «ارفع ملف الـPDF الأول».
- السعر: `PUT /api/bridge/prices/book/{slug}` (موجود في الداشبورد: `v2_prices_put` في app.py). ينفع وهو مسودة. البلاد: eg sa ae qa kw om + default.
- الأدلّة: سعر واحد `PUT /api/bridge/prices/book/_guides`، وده ظاهر بالفعل في قايمة الأسعار.
- أكواد الأدلّة: `GET /api/bridge/guides/codes` ⇒ `{codes:[{code,note,max_uses|null,active,uses}],version,updated_at,updated_by}`. و`PUT /api/bridge/guides/codes` `{codes:[{code,note?,max_uses?,active?}], by, confirmed}` بيبعت القايمة كلها مرة واحدة. الكود من ٣ لـ٤٠ حرف `[a-z0-9_-]`.
- كتابنا مالوش صاحب، والبيعة كلها للمنصة.

## المطلوب
### أ) مسارات الداشبورد: `backend/v2_books_ours_routes.py`
- على نمط `v2_courses2_routes.py` بالظبط:
  - `register(app, g)`؛
  - أدمن + `DASH_V2_ENABLED`؛
  - `no-store`؛
  - قايمة حقول بيضا؛
  - `by` من التوكن بس؛
  - `confirmed:true` من المتصفح لكل كتابة؛
  - نداء واحد من غير إعادة محاولة؛
  - رد ضايع ⇒ ٥٠٢ و`no_reply`؛
  - `detail` العربي بيعدّي زي ما هو؛
  - التدقيق عند النجاح بس.
- `GET/POST /api/v2/books/ours`، و`PUT /api/v2/books/ours/<slug>`، و`POST /api/v2/books/ours/<slug>/file` (يعدّي الـmultipart ويتأكد من `%PDF-` والامتداد قبل ما يبعت)، و`PUT /api/v2/books/ours/<slug>/status`.
- `GET/PUT /api/v2/books/guide-codes`.
- ⛔ مفيش سعر من المسارات دي. السعر من مسار الأسعار الموجود بس.

### ب) العقل يكتب الكتاب: `POST /api/v2/books/ours/<slug>/brain/draft` و`POST /api/v2/books/ours/<slug>/brain/pdf`
- **draft:** `{instruction, outline?}` ⇒ الكاتب الحالي (`brain2.engine.writer_of(ns)`: Claude لو المفتاح موجود، وإلا DeepSeek «الكاتب الاحتياطي») بيكتب مسودة منظمة `{title, about, chapters:[{title, body}]}`.
  - تتحفظ في SQLite الداشبورد (جدول جديد صغير، أو نفس مكان مسودات العقل) عشان المؤسس يعدّلها.
  - مفيش كتابة على المنصة هنا.
  - قواعد الكتابة: عربي فصيح بسيط، محايد للجنس، دولي، من غير «يقوّم»، من غير ما يبدأ بالذكاء الاصطناعي، ومن غير ادعاء مصادر أو أرقام مش موجودة في التعليمات.
- **pdf:** يحوّل المسودة المحفوظة لـPDF عربي RTL بهوية البروفيسور: ورق `#FBFAF7`، حبر `#21262E`، عنّابي `#9E2B4E`، صفحة غلاف بالعنوان، وفهرس، وفصول.
  - المكتبة weasyprint. ضيفها في `backend/requirements.txt`، وضيف في `Dockerfile` `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0` وخط عربي (حط ملفات TTF للخط في الريبو، Cairo أو Amiri بالرخصة المفتوحة، أو `fonts-noto-core`).
  - weasyprint بيتحمّل كسول جوه الدالة، ولو مش موجودة ⇒ رسالة عربي واضحة، والسيرفر ما يقعش.
  - بعدين يرفع الـPDF بنفس مسار الرفع (`/file`)، وده محتاج `confirmed:true`.
- سقف النداءات: نداء كاتب واحد لكل طلب، ويحترم سقوف المخ اليومية الموجودة.

### ج) الشاشة: تبويب «كتبنا» جوه قسم «الكتب» (`dashboard-cloud/v2s/books.js` + `books.css`)
- القايمة: كارت لكل كتاب (العنوان، النوع، «مسودة» أو «في المتجر»، الملف موجود ولا لأ) + زرار «كتاب جديد».
- «كتاب جديد»: العنوان، ونبذة، والنوع (كتاب / دليل / بحث / أخرى، ولازم «أخرى» تبقى موجودة).
- صفحة الكتاب، خطوات بالترتيب وكل خطوة واضحة إذا خلصت ولا لأ:
  1. **المحتوى:** «ارفع PDF»، أو «اكتبه مع العقل» (خانة تعليمات ⇒ المسودة تظهر بفصولها وتتعدّل ⇒ «اعمل PDF وارفعه»).
  2. **السعر:** يعرض الأسعار الحالية من `GET /api/v2/prices/book/<slug>`، وزرار يفتح نفس فورم الأسعار الموجود. ومن غير أي فورم سعر جديد.
  3. **اعرض في المتجر / اسحب من المتجر:** بتأكيد جوه الصفحة. ⛔ مفيش `confirm()`.
- كارت صغير «الأدلّة»: «سعر الأدلّة» (بيفتح سعر `_guides`)، و«أكواد الفتح» (جدول: الكود، الملاحظة، أقصى عدد، مفعّل، عدد الاستعمال، وإضافة سطر، وزرار «احفظ الأكواد» بتأكيد).
- الستايل: نفس نظام الزراير الموحّد (b2-btn) والكروت الموجودة في الداشبورد، وزراير على قد الكلام.
- ⛔ مفيش شرح تقني في النص المرئي.

### د) الاختبارات والصور
- اختبارات backend للمسارات: الحرّاس، والقايمة البيضا، وشيل السعر، وإن الـmultipart بيرفض أي حاجة مش PDF، والـ٥٠٢ لما الرد يضيع، وإن مسودة العقل بتتحفظ من غير أي نداء للمنصة، وإن الـPDF بيطلع (لو weasyprint مش موجودة في البيئة، `importorskip`).
- اختبار UI على نمط `backend/tests/uiharness/*` الموجود.
- صور الشاشات (بستب ثابت ومن غير شبكة) في `docs/v2/books-ours/shots/`: القايمة، كتاب جديد، صفحة الكتاب بالخطوات، مسودة العقل، وأكواد الأدلّة.
- الطقم كله لازم يفضل ناجح: قارن بـ`3b5b799` قبل التعديل، والفاشل قبل كده بس هو المسموح.
