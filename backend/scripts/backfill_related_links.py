#!/usr/bin/env python3
"""ردم «اقرأ أيضًا» لمرّةٍ واحدة على كل مقالٍ منشور بلا روابط داخلية (إصلاح ٢٠٢٦-١٠-٠١).

قاعدة المدوّنة SQLite داخل حاوية الداشبورد، فالسكربت يكلّم المسار المحروس بسرّ المزامنة بدل
أن يفتح القاعدة: نفس الدالة التي تستعملها المزامنة لكل مقالٍ جديد (`_with_related`) — تعريفٌ واحد
لـ«ذو صلة» لا تعريفان.

تجربة جافّة افتراضيًّا (تعدّ ولا تكتب):
    METRICS_SECRET=… python3 backend/scripts/backfill_related_links.py
التطبيق (يكتب ثم يدفع صفحات الـprerender للزواحف):
    METRICS_SECRET=… python3 backend/scripts/backfill_related_links.py --apply
"""
import argparse
import json
import os
import sys
import urllib.request

DEFAULT_URL = "https://dashboard.elprofessor.net/api/content/backfill-related"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apply", action="store_true", help="اكتب فعلًا (الافتراضي: تجربة جافّة)")
    p.add_argument("--refresh", action="store_true",
                   help="أعد بناء أقسام «اقرأ أيضًا» الموجودة من المنشور حاليًا (بعد سحب أو دمج مقالات)")
    p.add_argument("--url", default=os.environ.get("BACKFILL_URL", DEFAULT_URL))
    args = p.parse_args(argv)
    secret = os.environ.get("METRICS_SECRET", "").strip()
    if not secret:
        print("METRICS_SECRET غير مضبوط", file=sys.stderr)
        return 2
    q = [k for k, on in (("apply=1", args.apply), ("refresh=1", args.refresh)) if on]
    url = args.url + ("?" + "&".join(q) if q else "")
    req = urllib.request.Request(url, method="POST", data=b"",
                                 headers={"X-ELP-Metrics-Secret": secret, "User-Agent": "elp-backfill/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode("utf-8"))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    mode = "طُبِّق" if out.get("applied") else "تجربة جافّة — لم يُكتب شيء"
    print(f"\n{mode}: {out.get('would_link')} مقالًا يأخذ روابط ({out.get('links_added')} رابطًا) · "
          f"{out.get('already_linked')} فيه القسم سلفًا · {out.get('too_few_related')} بلا مقالين قريبين "
          f"· {out.get('refreshed', 0)} اتحدّث · من {out.get('published')} منشورًا.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
