# -*- coding: utf-8 -*-
"""«الموقع» من اللوحة (SPEC docs/v2/brain2/SPEC-B.md §B6): `site_edit` + منتجا الموقع + المسارات.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_site_edit.py

⛔ صفر شبكة حقيقية: SFTP مزيّف يحاكي واجهة paramiko (ويفشل الاختبار لو نودي `remove`)، و`getter` مزيّف للنداء HTTPS،
و`requests.get/post` ترميان، والناقل `call_anthropic` نصوص مجدولة.
"""
import datetime
import gzip
import json
import os
import re

import pytest

import app as appmod
import site_edit as se
from app import app as flask_app, db, AuditLog
from brain2 import engine, producers_site as ps, registry
from brain2.contract import Ctx, Target

from test_brain2_engine import env, Script   # noqa: F401  (env = fixture)
from test_brain2_routes import api, NON_ADMIN, ADMIN   # noqa: F401  (api = fixture)

NS = appmod.__dict__
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SFTP_ROOT = '/home/u/domains/elprofessor.net/public_html'

PAGE = 'pricing.html'
PRICING = '''<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>الأسعار | البروفيسور</title>
<meta name="description" content="أسعار واضحة لكل خدمة">
<meta property="og:description" content="لا يدخل هنا">
<style>.hero::before{content:"نص داخل ستايل"}</style>
<script>var t = "<h1>نص داخل سكربت</h1>";</script></head>
<body><nav><a href="/pricing.html" title="عنوان سمة" aria-label="تسمية سمة">الأسعار</a><a href="/about.html">من نحن</a></nav>
<h1 data-x="قيمة سمة">باقات تناسب كل خبير</h1>
<p class="lead">اختر الباقة المناسبة ثم ابدأ اليوم.</p>
<ul><li>ملف للخبير</li><li>دورات مسجلة</li></ul>
<img alt="نص بديل" src="a.png"><button>ابدأ الآن</button>
<section><h2>الأسئلة &amp; الأجوبة</h2><p>ابدأ الآن</p></section>
<noscript>نص نو سكربت</noscript><svg><text>نص داخل رسم</text></svg>
<footer><a href="/contact.html">تواصل</a></footer>
<script>document.write("x")</script></body></html>
'''
H1 = 'باقات تناسب كل خبير'
LEAD = 'اختر الباقة المناسبة ثم ابدأ اليوم.'


# ───────────────────────────────────────────────────────────── مزيّفات

class FakeFile(object):
    def __init__(self, sftp, path, mode):
        self.sftp, self.path, self.mode = sftp, path, mode
        self.buf = b''

    def read(self):
        return self.sftp.files[self.path]

    def write(self, data):
        assert 'w' in self.mode
        self.buf += data

    def close(self):
        if 'w' in self.mode:
            self.sftp.files[self.path] = self.buf
            self.sftp.log.append(('write', self.path))


class FakeSftp(object):
    """يحاكي ما نستعمله من paramiko: open · stat · chmod · posix_rename. أي حذف يُسقط الاختبار."""

    def __init__(self, files=None):
        self.files = dict(files or {})
        self.log = []
        self.fail_rename = False

    def open(self, path, mode='rb'):
        if 'r' in mode and path not in self.files:
            raise IOError('no such file')
        return FakeFile(self, path, mode)

    def stat(self, path):
        class St(object):
            st_mode = 0o100644
        if path not in self.files:
            raise IOError('no such file')
        return St()

    def chmod(self, path, mode):
        self.log.append(('chmod', path))

    def posix_rename(self, src, dst):
        if self.fail_rename:
            raise IOError('rename failed')
        self.files[dst] = self.files.pop(src)
        self.log.append(('rename', src, dst))

    def remove(self, path):
        raise AssertionError('حذف ملف ممنوع: ' + path)

    unlink = rmdir = remove


class FakeWeb(object):
    """نداء HTTPS مزيّف: يقدّم ما في SFTP المزيّف (فيرى التعديل بعد الرفع) إلا لو ثُبّتت صفحة بعينها."""

    def __init__(self, sftp):
        self.sftp = sftp
        self.pinned = {}
        self.calls = []
        self.fail = False

    def __call__(self, url):
        self.calls.append(url)
        if self.fail:
            raise IOError('down')
        assert url.startswith('https://elprofessor.net/'), url
        page = url[len('https://elprofessor.net/'):]
        if page in self.pinned:
            return 200, self.pinned[page]
        data = self.sftp.files.get(SFTP_ROOT + '/' + page)
        if data is None:
            return 404, ''
        return 200, data.decode('utf-8')


@pytest.fixture()
def site(monkeypatch, env):   # noqa: F811
    """موقع مزيّف كامل: ملفات على SFTP مزيّف، و`getter` يقرؤها، والخطّافات محقونة. ينظّف جداول الموقع."""
    sftp = FakeSftp({SFTP_ROOT + '/' + p: PRICING.encode('utf-8') for p in se.ALLOWED})
    sftp.files[SFTP_ROOT + '/.htaccess'] = b'RewriteEngine On\n'
    web = FakeWeb(sftp)
    sessions = []

    def factory():
        s = se.Session(sftp, SFTP_ROOT, lambda: sessions.append('closed'))
        return s
    se.set_hooks(getter=web, sftp_factory=factory, sleep=lambda s: None)
    B = se.models(db)
    D = ps.decision_model(db)
    B.query.delete()
    D.query.delete()
    db.session.commit()
    yield type('Site', (), {'sftp': sftp, 'web': web, 'sessions': sessions})
    se.set_hooks()
    B.query.delete()
    D.query.delete()
    db.session.commit()


def live_bytes(site, page=PAGE):
    return site.sftp.files[SFTP_ROOT + '/' + page]


def sha_of(page_html):
    return se.blocks_sha(se.extract_blocks(page_html))


# ───────────────────────────────────────────────────────────── قائمة الصفحات المسموحة

def test_allow_list_is_the_twelve_pages_and_rejects_everything_else():
    assert len(se.ALLOWED) == 12 and se.ALLOWED[0] == 'Company-Site.html'
    for p in se.ALLOWED:
        assert se.page_allowed(p), p
    for bad in ('.htaccess', 'haq-masr/.htaccess', 'index.html', 'haq-masr/other.html', '../pricing.html', 'pricing.html/..',
                '/pricing.html', 'pricing.html ', 'PRICING.HTML', 'blog.html', 'article.html', 'feed.xml', '', None, 5, ['pricing.html']):
        assert not se.page_allowed(bad), bad
        with pytest.raises(se.SiteError):
            se.require_page(bad)


def test_nothing_outside_the_allow_list_is_read_written_or_touched(site):
    for bad in ('.htaccess', 'blog.html', 'haq-masr/.htaccess'):
        with pytest.raises(se.SiteError):
            se.fetch_live(bad)
        with pytest.raises(se.SiteError):
            se.remote_read(se.Session(site.sftp, SFTP_ROOT), bad)
        with pytest.raises(se.SiteError):
            se.remote_write(se.Session(site.sftp, SFTP_ROOT), bad, b'x')
        r = se.apply_edits(db, bad, '', [{'old': 'a', 'new': 'b'}], 'a@x.test')
        assert r['ok'] is False and r['status'] == 400
        assert se.restore_backup(db, bad, 1)['ok'] is False
    assert site.sftp.log == [] and site.web.calls == []
    assert site.sftp.files[SFTP_ROOT + '/.htaccess'] == b'RewriteEngine On\n'
    assert se.models(db).query.count() == 0


# ───────────────────────────────────────────────────────────── المستخرِج

def test_extraction_gives_only_text_blocks_never_scripts_styles_or_attributes():
    blocks = se.extract_blocks(PRICING)
    texts = [b['text'] for b in blocks]
    assert 'الأسعار | البروفيسور' in texts and 'أسعار واضحة لكل خدمة' in texts, 'title + وصف meta'
    assert H1 in texts and LEAD in texts and 'ملف للخبير' in texts and 'دورات مسجلة' in texts
    assert 'الأسئلة & الأجوبة' in texts, 'الكيانات تُفكّ'
    assert 'تواصل' in texts and 'من نحن' in texts
    blob = ' '.join(texts)
    for forbidden in ('نص داخل ستايل', 'نص داخل سكربت', 'قيمة سمة', 'عنوان سمة', 'تسمية سمة', 'نص بديل', 'لا يدخل هنا', 'نص نو سكربت',
                      'نص داخل رسم', 'document.write', 'pricing.html', 'lead'):
        assert forbidden not in blob, forbidden
    tags = {b['tag'] for b in blocks}
    assert tags <= {'title', 'meta', 'h1', 'h2', 'h3', 'p', 'li', 'a', 'button'}
    paths = [b['path'] for b in blocks]
    assert len(paths) == len(set(paths)), 'المسارات فريدة'
    assert se.extract_blocks(PRICING) == blocks, 'ثابتة بين قراءتين'


def test_repeated_text_is_listed_but_not_editable_and_mixed_paragraphs_split_into_parts():
    by = {b['path']: b for b in se.extract_blocks(PRICING)}
    dup = [b for b in by.values() if b['text'] == 'ابدأ الآن']
    assert len(dup) == 2 and all(not b['editable'] and b['note'] for b in dup)
    mixed = se.extract_blocks('<body><p>مرحبا <b>بكم</b> في <a href="#">موقعنا</a></p></body>')
    assert [b['text'] for b in mixed] == ['مرحبا', 'بكم', 'في', 'موقعنا']
    assert [b['path'] for b in mixed][0].endswith('p[1]#1') and mixed[3]['path'].endswith('a[1]')


def test_implied_list_item_closes_and_html_comments_split_text():
    b = se.extract_blocks('<ul><li>أول<li>ثان</ul><p>س<!-- ملاحظة -->ص</p>')
    assert [x['text'] for x in b] == ['أول', 'ثان', 'س', 'ص']
    assert b[0]['path'].endswith('li[1]') and b[1]['path'].endswith('li[2]')


# ───────────────────────────────────────────────────────────── الاستبدال: تطابق مرة واحدة بالضبط

def test_replace_changes_only_the_text_node_and_keeps_every_other_byte():
    out = se.replace_edits(PRICING, [{'path': None, 'old': H1, 'new': 'باقات بسيطة & واضحة'}])
    assert out.count('باقات بسيطة &amp; واضحة') == 1
    assert out.replace('باقات بسيطة &amp; واضحة', H1) == PRICING, 'لا بايت آخر تغيّر'
    spaced = '<p>\n   قديم  هنا \n</p>'
    assert se.replace_edits(spaced, [{'old': 'قديم هنا', 'new': 'جديد'}]) == '<p>\n   جديد \n</p>', 'الفراغات الحدّية تبقى'


def test_meta_description_is_replaced_inside_its_attribute_only():
    out = se.replace_edits(PRICING, [{'old': 'أسعار واضحة لكل خدمة', 'new': 'أسعار "بسيطة"'}])
    assert 'content="أسعار &quot;بسيطة&quot;"' in out and 'og:description" content="لا يدخل هنا"' in out
    assert out.count('<meta') == PRICING.count('<meta')


def test_zero_matches_and_two_or_more_matches_are_errors_and_path_must_agree():
    with pytest.raises(se.SiteError) as e:
        se.replace_edits(PRICING, [{'old': 'نص غير موجود', 'new': 'جديد'}])
    assert e.value.code == 'no_match' and e.value.status == 422
    with pytest.raises(se.SiteError) as e:
        se.replace_edits(PRICING, [{'old': 'ابدأ الآن', 'new': 'جديد'}])
    assert e.value.code == 'multi_match' and e.value.status == 422
    with pytest.raises(se.SiteError) as e:
        se.replace_edits(PRICING, [{'path': 'html[1]>body[1]>p[9]', 'old': H1, 'new': 'جديد'}])
    assert e.value.code == 'path_mismatch'
    ok = se.replace_edits(PRICING, [{'path': [b for b in se.extract_blocks(PRICING) if b['text'] == H1][0]['path'], 'old': H1, 'new': 'جديد'}])
    assert 'جديد' in ok
    # الاستبدال لا يخلق تطابقًا ثانيًا للنص الجديد في نفس الحزمة ولا يقبل قديمًا مطابقًا للجديد
    with pytest.raises(se.SiteError):
        se.replace_edits(PRICING, [{'old': H1, 'new': H1}])


def test_new_text_is_one_clean_line_without_tags_or_control_characters():
    for bad in ('', '   ', 'x' * (se.NEW_MAX + 1), '<b>غامق</b>', 'a > b', None, 5):
        with pytest.raises(se.SiteError):
            se.clean_new_text(bad)
    assert se.clean_new_text('سطر \n  واحد‏ ') == 'سطر واحد'
    with pytest.raises(se.SiteError):
        se.replace_edits(PRICING, [])
    with pytest.raises(se.SiteError):
        se.replace_edits(PRICING, [{'old': H1, 'new': 'ا'}] * (se.MAX_EDITS + 1))
    with pytest.raises(se.SiteError):
        se.replace_edits(PRICING, [{'old': H1, 'new': 'أ'}, {'old': H1, 'new': 'ب'}])


# ───────────────────────────────────────────────────────────── الجلب الحي

def test_fetch_live_uses_the_getter_and_never_the_network(site, monkeypatch):
    def boom(*a, **k):
        raise AssertionError('نداء شبكة حقيقي ممنوع')
    monkeypatch.setattr(appmod.requests, 'get', boom)
    live = se.fetch_live(PAGE)
    assert live['page'] == PAGE and live['sha'] == sha_of(PRICING) and len(live['blocks']) >= 8
    assert site.web.calls == ['https://elprofessor.net/pricing.html']
    site.web.fail = True
    with pytest.raises(se.SiteError) as e:
        se.fetch_live(PAGE)
    assert e.value.status == 502 and e.value.message == se.ERR_FETCH
    site.web.fail = False
    site.web.pinned[PAGE] = '   '
    with pytest.raises(se.SiteError):
        se.fetch_live(PAGE)
    assert se.page_url('haq-masr/sign.html') == 'https://elprofessor.net/haq-masr/sign.html'


# ───────────────────────────────────────────────────────────── التنفيذ

EDIT = [{'old': H1, 'new': 'باقات بسيطة لكل خبير'}]


def test_apply_backs_up_replaces_via_temp_then_rename_and_verifies(site):
    r = se.apply_edits(db, PAGE, sha_of(PRICING), EDIT, 'admin@x.test')
    assert r['ok'] is True and r['status'] == 200 and r['edits'] == 1
    now = live_bytes(site).decode('utf-8')
    assert 'باقات بسيطة لكل خبير' in now and H1 not in now
    assert now.replace('باقات بسيطة لكل خبير', H1) == PRICING
    path = SFTP_ROOT + '/' + PAGE
    writes = [e for e in site.sftp.log if e[0] in ('write', 'rename')]
    assert writes == [('write', path + se.TMP_SUFFIX), ('rename', path + se.TMP_SUFFIX, path)], 'مؤقت ثم إعادة تسمية، وبلا كتابة مباشرة على الأصل'
    assert not any(k.endswith(se.TMP_SUFFIX) for k in site.sftp.files), 'المؤقت أُعيدت تسميته'
    # كل ما كُتب على الاستضافة صفحة مسموحة (أو مؤقتها)
    for entry in site.sftp.log:
        for p in entry[1:]:
            rel = p[len(SFTP_ROOT) + 1:]
            assert se.page_allowed(rel[:-len(se.TMP_SUFFIX)] if rel.endswith(se.TMP_SUFFIX) else rel), p
    assert site.sftp.files[SFTP_ROOT + '/.htaccess'] == b'RewriteEngine On\n'
    bk = se.list_backups(db, PAGE)
    assert len(bk) == 1 and bk[0]['id'] == r['backup_id'] and bk[0]['created_by'] == 'admin@x.test'
    row = se.get_backup(db, PAGE, bk[0]['id'])
    assert gzip.decompress(row.html_gz) == PRICING.encode('utf-8') and row.sha256 == se.sha_bytes(PRICING.encode('utf-8'))
    assert site.sessions == ['closed']
    assert site.web.calls and all(u == 'https://elprofessor.net/pricing.html' for u in site.web.calls)


def test_stale_proposal_is_409_and_the_page_is_not_touched(site):
    r = se.apply_edits(db, PAGE, 'f' * 64, EDIT, 'a@x.test')
    assert r['ok'] is False and r['status'] == 409 and r['error'] == 'تغيّرت الصفحة منذ الاقتراح؛ أعد التوليد'
    assert live_bytes(site) == PRICING.encode('utf-8') and not any(e[0] == 'write' for e in site.sftp.log)
    # محاولات فاشلة متكررة على نفس المحتوى لا تُخرج النسخ القديمة
    for _ in range(5):
        se.apply_edits(db, PAGE, 'f' * 64, EDIT, 'a@x.test')
    assert len(se.list_backups(db, PAGE)) == 1


def test_changed_page_after_proposal_is_409_even_when_the_edit_would_still_match(site):
    sha = sha_of(PRICING)
    site.sftp.files[SFTP_ROOT + '/' + PAGE] = PRICING.replace('ملف للخبير', 'ملف جديد للخبير').encode('utf-8')
    r = se.apply_edits(db, PAGE, sha, EDIT, 'a@x.test')
    assert r['status'] == 409 and 'تغيّرت الصفحة' in r['error']


def test_a_text_that_is_not_there_or_repeated_is_a_422_with_nothing_written(site):
    for edits, code in (([{'old': 'غير موجود', 'new': 'جديد'}], 'no_match'), ([{'old': 'ابدأ الآن', 'new': 'جديد'}], 'multi_match')):
        r = se.apply_edits(db, PAGE, sha_of(PRICING), edits, 'a@x.test')
        assert r['ok'] is False and r['status'] == 422 and r['code'] == code
    assert live_bytes(site) == PRICING.encode('utf-8') and not any(e[0] == 'write' for e in site.sftp.log)


def test_verify_failure_restores_the_backup_and_says_so(site):
    site.web.pinned[PAGE] = PRICING          # الـCDN يقدّم القديم دائمًا ⇒ التعديل لا يظهر
    r = se.apply_edits(db, PAGE, sha_of(PRICING), EDIT, 'a@x.test', verify_attempts=3)
    assert r['ok'] is False and r['restored'] is True and r['error'] == 'لم يظهر التعديل؛ أعدنا الصفحة كما كانت'
    assert live_bytes(site) == PRICING.encode('utf-8'), 'الصفحة كما كانت بالبايت'
    assert len(site.web.calls) == 3, 'ثلاث محاولات تحقق'
    assert len([e for e in site.sftp.log if e[0] == 'rename']) == 2, 'رفع ثم إرجاع'
    assert len(se.list_backups(db, PAGE)) == 1


def test_verify_when_the_site_is_unreachable_also_restores(site):
    site.web.fail = True
    r = se.apply_edits(db, PAGE, sha_of(PRICING), EDIT, 'a@x.test', verify_attempts=2)
    assert r['restored'] is True and live_bytes(site) == PRICING.encode('utf-8')


def test_a_failed_restore_after_failed_verify_is_reported_as_unknown(site):
    site.web.pinned[PAGE] = PRICING
    orig = site.sftp.posix_rename
    calls = {'n': 0}

    def flaky(src, dst):
        calls['n'] += 1
        if calls['n'] == 2:
            raise IOError('rename failed')
        return orig(src, dst)
    site.sftp.posix_rename = flaky
    r = se.apply_edits(db, PAGE, sha_of(PRICING), EDIT, 'a@x.test', verify_attempts=1)
    assert r['ok'] is False and r['unknown'] is True and r['code'] == 'restore_failed'
    assert 'النسخ السابقة' in r['error']


def test_rename_failure_changes_nothing_and_never_deletes(site):
    site.sftp.fail_rename = True
    r = se.apply_edits(db, PAGE, sha_of(PRICING), EDIT, 'a@x.test')
    assert r['ok'] is False and r['status'] == 502 and r['error'] == se.ERR_REMOTE
    assert live_bytes(site) == PRICING.encode('utf-8'), 'الأصل كما هو؛ المؤقت وحده بقي'


def test_unconfigured_hosting_is_a_clear_503_and_makes_no_connection(monkeypatch):
    se.set_hooks()
    for k in ('PRERENDER_SSH_HOST', 'PRERENDER_SSH_USER', 'PRERENDER_SSH_PASSWORD'):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(se.SiteError) as e:
        se.default_sftp_factory()
    assert e.value.status == 503 and e.value.message == se.ERR_NOT_CONFIGURED
    r = se.apply_edits(db, PAGE, '', EDIT, 'a@x.test', getter=lambda u: (200, PRICING))
    assert r['ok'] is False and r['status'] == 503


def test_concurrent_apply_is_refused_with_a_clear_409(site, monkeypatch):
    monkeypatch.setattr(se, '_LOCK', type('L', (), {'acquire': lambda self, timeout=None: False, 'release': lambda self: None})())
    r = se.apply_edits(db, PAGE, '', EDIT, 'a@x.test')
    assert r['status'] == 409 and r['error'] == se.ERR_BUSY
    assert se.restore_backup(db, PAGE, 1)['ok'] is False


# ───────────────────────────────────────────────────────────── النسخ الاحتياطية: حد ٢٠ والإرجاع

def test_backups_keep_only_the_last_twenty_per_page_and_dedupe_same_content(site):
    ids = []
    for i in range(25):
        ids.append(se.save_backup(db, PAGE, ('<p>نسخة %d</p>' % i).encode('utf-8'), 'a@x.test').id)
    se.save_backup(db, 'contact.html', '<p>أخرى</p>'.encode('utf-8'), 'a@x.test')
    kept = se.list_backups(db, PAGE)
    assert len(kept) == 20
    assert [b['id'] for b in kept] == list(reversed(ids[5:])), 'الأحدث أولًا وأقدم خمس حُذفت'
    assert len(se.list_backups(db, 'contact.html')) == 1, 'الحد لكل صفحة'
    same = se.save_backup(db, PAGE, ('<p>نسخة 24</p>').encode('utf-8'), 'a@x.test')
    assert same.id == ids[-1] and len(se.list_backups(db, PAGE)) == 20, 'نفس محتوى الأحدث لا يُخزَّن ثانية'
    with pytest.raises(se.SiteError):
        se.get_backup(db, PAGE, ids[0])


def test_restore_returns_any_backup_saves_the_current_page_first_and_verifies_readback(site):
    first = se.apply_edits(db, PAGE, sha_of(PRICING), EDIT, 'a@x.test')
    assert first['ok']
    edited = live_bytes(site)
    r = se.restore_backup(db, PAGE, first['backup_id'], 'admin@x.test')
    assert r['ok'] is True and live_bytes(site) == PRICING.encode('utf-8')
    notes = [b['note'] for b in se.list_backups(db, PAGE)]
    assert notes[0] == 'before_restore' and 'apply' in notes, 'الإرجاع نفسه قابل للتراجع'
    back = [b for b in se.list_backups(db, PAGE) if b['note'] == 'before_restore'][0]
    assert gzip.decompress(se.get_backup(db, PAGE, back['id']).html_gz) == edited
    r2 = se.restore_backup(db, PAGE, back['id'], 'admin@x.test')
    assert r2['ok'] and live_bytes(site) == edited, 'يمكن التراجع عن الإرجاع'
    assert site.sftp.files[SFTP_ROOT + '/.htaccess'] == b'RewriteEngine On\n'


def test_restore_rejects_unknown_other_page_and_bad_ids(site):
    bk = se.save_backup(db, 'contact.html', b'<p>x</p>', 'a@x.test')
    for pg, bid in ((PAGE, bk.id), (PAGE, 999999), (PAGE, 'abc'), (PAGE, None)):
        r = se.restore_backup(db, pg, bid)
        assert r['ok'] is False and r['status'] == 404, (pg, bid)
    assert not any(e[0] == 'write' for e in site.sftp.log)


# ───────────────────────────────────────────────────────────── القرارات

def test_seed_is_written_once_has_fifteen_cited_public_rules_and_no_internal_numbers(site):
    assert ps.ensure_seed(db) is True and ps.ensure_seed(db) is False
    rows = ps.list_decisions(db)
    assert 10 <= len(rows) == len(ps.SEED_DECISIONS) <= 15 and all(r.created_by == 'seed' for r in rows)
    texts = [r.text for r in rows]
    assert all(3 <= len(t) <= ps.DECISION_MAX for t in texts) and len(set(texts)) == len(texts)
    for must in ('عنوان بعبارة «الذكاء الاصطناعي»', 'يقوّم', 'تواصل', 'نفي', 'خصم الطالب', 'دولي', 'تقني'):
        assert any(must in t for t in texts), must
    assert not any(('35' in t or '٣٥' in t or 'نصيب المنصة' in t) for t in texts), 'القرار الداخلي لا يدخل النص العام'
    # كل بذرة تسبقها سطر تعليق بمصدرها (ملف:سطر)
    src = open(os.path.join(ROOT, 'backend', 'brain2', 'producers_site.py'), encoding='utf-8').read()
    block = src[src.index('SEED_DECISIONS = ('):src.index('DECISION_MAX = ')]
    lines = [l.strip() for l in block.split('\n')]
    cites = [l for l in lines if l.startswith('#') and re.search(r'\.md:\d+', l)]
    seeds = [l for l in lines if l.startswith("'") and l.endswith("',")]
    assert len(cites) >= len(seeds) == len(ps.SEED_DECISIONS)
    for i, l in enumerate(lines):
        if l.startswith("'") and l.endswith("',"):
            assert lines[i - 1].startswith('#') and re.search(r'\.md:\d+', lines[i - 1]), l
    # حذف الكل لا يعيد البذرة
    for r in rows:
        assert ps.remove_decision(db, r.id)
    assert ps.list_decisions(db) == [] and ps.ensure_seed(db) is False


def test_decisions_add_remove_rules(site):
    ps.ensure_seed(db)
    row, err = ps.add_decision(db, '  قاعدة   جديدة  للاختبار ', 'a@x.test')
    assert err is None and row.text == 'قاعدة جديدة للاختبار' and row.created_by == 'a@x.test' and row.active
    assert ps.add_decision(db, 'قاعدة جديدة للاختبار', 'a@x.test')[0] is None, 'لا تكرار'
    for bad in ('', 'اب', 'ك' * 301, None, 7):
        assert ps.add_decision(db, bad, 'a@x.test')[0] is None
    assert ps.list_decisions(db)[-1].id == row.id
    assert ps.remove_decision(db, row.id) is True and ps.remove_decision(db, row.id) is False
    assert row.id not in [r.id for r in ps.list_decisions(db)]
    for i in range(ps.DECISIONS_MAX_ACTIVE):
        ps.add_decision(db, 'قاعدة رقم %d' % i, 'a@x.test')
    assert ps.add_decision(db, 'قاعدة زائدة', 'a@x.test')[1].startswith('بلغت الحد')


# ───────────────────────────────────────────────────────────── منتج المراجعة

def _target(site_, page=PAGE, decisions=('لا يبدأ أي عنوان بعبارة «الذكاء الاصطناعي».',)):
    return ps.build_target(page, se.fetch_live(page), list(decisions))


def test_target_facts_fit_four_kilobytes_hide_real_paths_and_skip_repeated_or_long_blocks(site):
    t = _target(site)
    assert isinstance(t, Target) and t.ref == 'site:pricing.html' and t.label == 'صفحة الأسعار'
    assert len(json.dumps(t.facts, ensure_ascii=False, sort_keys=True).encode('utf-8')) <= engine.FACTS_MAX_BYTES
    assert set(t.facts) == {'page', 'decisions', 'blocks'}
    aliases = [b['path'] for b in t.facts['blocks']]
    assert aliases == ['b%d' % i for i in range(1, len(aliases) + 1)]
    assert 'html[1]' not in json.dumps(t.facts) and all(a in t.meta['paths'] for a in aliases)
    texts = [b['text'] for b in t.facts['blocks']]
    assert 'ابدأ الآن' not in texts, 'المكرر لا يراه الذكاء'
    assert H1 in texts and t.meta['sha'] == sha_of(PRICING) and t.meta['page'] == PAGE
    # صفحة كبيرة: الحقائق تبقى ضمن الحد
    big = '<body>' + ''.join('<h2>عنوان رقم %d من القسم الطويل جدًا للاختبار</h2><p>%s</p>' % (i, 'كلمة ' * 20 + str(i)) for i in range(200)) + '</body>'
    live = {'blocks': se.extract_blocks(big), 'sha': 'x'}
    t2 = ps.build_target(PAGE, live, ['قاعدة ' * 40] * 30)
    assert _size(t2.facts) <= engine.FACTS_MAX_BYTES and len(t2.facts['blocks']) > 5
    assert ps.build_target(PAGE, {'blocks': [], 'sha': 'x'}, []) is None


def _size(o):
    return len(json.dumps(o, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def test_rotation_covers_all_twelve_pages_two_at_a_time():
    seen = []
    day0 = datetime.datetime(2026, 11, 1)
    for d in range(6):
        pages = ps.pages_for_today(day0 + datetime.timedelta(days=d))
        assert len(pages) == ps.PAGES_PER_RUN == 2
        seen += pages
    assert sorted(seen) == sorted(se.ALLOWED)
    assert ps.pages_for_today(day0) == ps.pages_for_today(day0), 'نفس اليوم نفس الصفحتين'


def _reply(site_target, edits, text='ملخص قصير'):
    return {'edits': edits, 'text': text}


def _alias(t, text):
    return [b['path'] for b in t.facts['blocks'] if b['text'] == text][0]


def test_validate_drops_edits_whose_old_differs_from_the_live_block_and_other_rule_breakers(site):
    t = _target(site)
    a_h1, a_lead = _alias(t, H1), _alias(t, LEAD)
    raw = {'edits': [
        {'path': a_h1, 'old': H1, 'new': 'باقات بسيطة لكل خبير', 'why': 'صياغة أوضح'},                 # صالح
        {'path': a_lead, 'old': LEAD + ' ', 'new': 'جملة جديدة', 'why': 'x'},                           # old ≠ الحي بفراغ
        {'path': 'b99', 'old': H1, 'new': 'مسار غريب', 'why': ''},                                      # مسار مجهول
        {'path': a_lead, 'old': 'نص مخترع', 'new': 'جملة', 'why': ''},                                   # old مخترع
        {'path': a_lead, 'old': LEAD, 'new': 'تقوّم الجودة وتقوّم المحتوى 2026', 'why': ''},               # رقم من عندها
    ], 'text': 'ملخص'}
    body = ps._validate_site_review(raw, t)
    assert [e['old'] for e in body['edits']] == [H1], 'الصالح وحده يبقى'
    assert body['edits'][0]['path'] == t.meta['paths'][a_h1], 'المسار الحقيقي لا المختصر'
    assert body['page'] == PAGE and body['page_label'] == 'صفحة الأسعار' and body['text'].startswith('تعديلات مقترحة على «صفحة الأسعار»')
    assert 'من «%s» إلى «باقات بسيطة لكل خبير»' % H1 in body['text']
    assert engine.check_body(body, t.facts, 'draft') is None, 'فحوص الصدق في المحرّك تمرّ'
    # القواعد: كلمة ممنوعة · عنوان يبدأ بالذكاء · لاتينية من عندها · HTML · مطابق للقديم
    lead_edit = lambda new: ps._validate_site_review({'edits': [{'path': a_lead, 'old': LEAD, 'new': new, 'why': ''}]}, t)['edits']
    assert lead_edit('نص ليقوّم الأداء') == [] and lead_edit('<b>غامق</b>') == [] and lead_edit('Hello world') == []
    assert lead_edit(LEAD) == [] and lead_edit('') == [] and lead_edit(None) == []
    h1_edit = lambda new: ps._validate_site_review({'edits': [{'path': a_h1, 'old': H1, 'new': new, 'why': ''}]}, t)['edits']
    assert h1_edit('الذكاء الاصطناعي يخدم الخبير') == [] and h1_edit('«الذكاء» أولًا') == []
    assert lead_edit('الذكاء يساعد على الفهم') != [], 'القاعدة على العناوين فقط'
    # أكثر من خمسة تعديلات ⇒ الخمسة الأولى
    many = [{'path': _alias(t, b['text']), 'old': b['text'], 'new': 'جديد %s' % i, 'why': ''}
            for i, b in enumerate([x for x in t.facts['blocks']][:7])]
    got = ps._validate_site_review({'edits': many}, t)
    assert len(got['edits']) <= ps.EDITS_MAX


def test_no_valid_edits_is_stored_without_a_card(site):
    t = _target(site)
    b = ps._validate_site_review({'edits': [{'path': 'b1', 'old': 'مخترع', 'new': 'جديد', 'why': ''}], 'text': 'x'}, t)
    assert b['edits'] == [] and b['course_id'] is None and b['text'] == ps.NO_EDITS_TEXT
    assert ps._validate_site_review({'edits': []}, t)['edits'] == []
    assert ps._validate_site_review({'edits': 'bad'}, t) is None and ps._validate_site_review([], t) is None


def test_producer_is_locked_asks_always_and_has_the_spec_texts():
    p = registry.by_id('site_review')
    assert p.kind == 'draft' and p.section == 'content' and p.may_run_alone is False and p.default_mode == 'ask'
    assert p.lock_reason == 'يسألك دائمًا لأن التعديل يظهر على الموقع للناس.'
    assert p.per_run_cap == 2 and p.listed is True and p.apply is not None
    m = registry.by_id('site_edit_manual')
    assert m.listed is False and m.may_run_alone is False and m.gather(None) == [] and m.apply is not None


def run_review(site_, monkeypatch, env_, reply, pages=(PAGE,)):
    monkeypatch.setattr(ps, 'pages_for_today', lambda now=None: list(pages))
    env_.replies = [reply]
    st, pl = engine.start_run(NS, 'admin', 'admin@x.test', only='site_review')
    assert st == 202, pl
    return pl['run_id']


def ai_reply(edits_by_text, text='نقترح تعديل العنوان'):
    """ردّ مجدول يبني الأسماء المختصرة من الحقائق الواصلة فعلًا في الطلب."""
    def fn(system, user):
        facts = json.loads(user.split('الحقائق:\n', 1)[1])
        by = {b['text']: b['path'] for b in facts['blocks']}
        return {'edits': [{'path': by.get(o, 'b99'), 'old': o, 'new': n, 'why': 'يوافق القرارات'} for o, n in edits_by_text], 'text': text}
    return fn


def test_review_run_makes_a_locked_proposal_even_if_the_switch_says_alone(site, env, monkeypatch):   # noqa: F811
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='site_review', mode='alone', updated_by='tamper'))
    db.session.commit()
    run_review(site, monkeypatch, env, ai_reply([(H1, 'باقات بسيطة لكل خبير')]))
    Item = engine._models(db)[0]
    (row,) = Item.query.filter_by(producer='site_review').all()
    assert row.status == 'proposed' and row.mode == 'ask' and row.source == 'ai' and row.section == 'content'
    body = json.loads(row.body_json)
    assert body['edits'][0]['old'] == H1 and body['approve_label'] == ps.APPROVE_LABEL
    meta = json.loads(row.meta_json)
    assert meta['page'] == PAGE and meta['sha'] == sha_of(PRICING)
    assert not any(e[0] == 'write' for e in site.sftp.log), 'لا يُكتب شيء في الموقع قبل الاعتماد'
    assert len(env.calls) == 1
    facts_sent = json.loads(env.calls[0]['user'].split('الحقائق:\n', 1)[1])
    assert any('يقوّم' in d for d in facts_sent['decisions']), 'القرارات المعتمدة تصل مع الحقائق'
    # تكرار الجولة على نفس الصفحة بلا تغيير ⇒ صفر نداء
    env.replies = []
    engine.start_run(NS, 'admin', 'admin@x.test', only='site_review')
    assert len(env.calls) == 1


def test_review_with_no_valid_edit_stores_a_discarded_row_and_shows_no_card(site, env, monkeypatch):   # noqa: F811
    run_review(site, monkeypatch, env, ai_reply([('نص مخترع', 'جديد')]))
    Item = engine._models(db)[0]
    (row,) = Item.query.filter_by(producer='site_review').all()
    assert row.status == 'discarded'
    assert Item.query.filter_by(producer='site_review', status='proposed').count() == 0


def test_review_caps_pages_per_run_and_reports_source_down_only_when_all_fail(site, env, monkeypatch):   # noqa: F811
    monkeypatch.setattr(ps, 'pages_for_today', lambda now=None: ['pricing.html', 'terms.html'])
    ctx = Ctx(ns=NS, now=None, actor='cron')
    ts = ps._gather_site_review(ctx)
    assert [t.ref for t in ts] == ['site:pricing.html', 'site:terms.html']
    assert set(c.rsplit('/', 1)[1] for c in site.web.calls) == {'pricing.html', 'terms.html'}, 'صفحتان فقط من الاثنتي عشرة'
    site.web.pinned['terms.html'] = ''
    assert [t.ref for t in ps._gather_site_review(ctx)] == ['site:pricing.html']
    site.web.fail = True
    with pytest.raises(Exception) as e:
        ps._gather_site_review(ctx)
    assert e.value.__class__.__name__ == 'SourceDown'


def test_approving_the_review_applies_it_to_the_site_once(site, env, monkeypatch):   # noqa: F811
    run_review(site, monkeypatch, env, ai_reply([(H1, 'باقات بسيطة لكل خبير')]))
    Item = engine._models(db)[0]
    row = Item.query.filter_by(producer='site_review').one()
    st, pl = engine.apply_item(NS, row.id, 'admin@x.test')
    assert st == 200 and pl['status'] == 'approved' and pl['info']['page'] == PAGE
    assert 'باقات بسيطة لكل خبير' in live_bytes(site).decode('utf-8')
    assert engine.apply_item(NS, row.id, 'admin@x.test')[0] == 409
    a = AuditLog.query.filter_by(action='v2_site.apply').order_by(AuditLog.id.desc()).first()
    assert a.target == PAGE and a.actor_email == 'admin@x.test' and json.loads(a.meta_json)['ok'] is True


def test_approving_after_the_page_changed_is_refused_and_the_card_stays_open(site, env, monkeypatch):   # noqa: F811
    run_review(site, monkeypatch, env, ai_reply([(H1, 'باقات بسيطة لكل خبير')]))
    site.sftp.files[SFTP_ROOT + '/' + PAGE] = PRICING.replace('دورات مسجلة', 'دورات مباشرة').encode('utf-8')
    changed = live_bytes(site)
    row = engine._models(db)[0].query.filter_by(producer='site_review').one()
    st, pl = engine.apply_item(NS, row.id, 'admin@x.test')
    assert st == 422 and pl['error'] == 'تغيّرت الصفحة منذ الاقتراح؛ أعد التوليد'
    assert live_bytes(site) == changed
    db.session.expire_all()
    assert engine._models(db)[0].query.get(row.id).status == 'proposed'


def test_verify_failure_on_approve_is_reported_and_the_page_is_unchanged(site, env, monkeypatch):   # noqa: F811
    run_review(site, monkeypatch, env, ai_reply([(H1, 'باقات بسيطة لكل خبير')]))
    site.web.pinned[PAGE] = PRICING
    row = engine._models(db)[0].query.filter_by(producer='site_review').one()
    st, pl = engine.apply_item(NS, row.id, 'admin@x.test')
    assert st == 422 and pl['error'] == 'لم يظهر التعديل؛ أعدنا الصفحة كما كانت'
    assert live_bytes(site) == PRICING.encode('utf-8')


# ───────────────────────────────────────────────────────────── المسارات

def blocks_of(api_):
    return api_.get('/api/v2/site/blocks?page=' + PAGE).get_json()


def edit_body(sha, path, old, new, **kw):
    d = {'page': PAGE, 'path': path, 'old': old, 'new': new, 'sha': sha, 'confirmed': True}
    d.update(kw)
    return d


ENDPOINTS = [
    ('GET', '/api/v2/site/pages', None),
    ('GET', '/api/v2/site/blocks?page=pricing.html', None),
    ('POST', '/api/v2/site/edit', {'page': PAGE, 'path': 'x', 'old': 'a', 'new': 'b', 'sha': 's', 'confirmed': True}),
    ('GET', '/api/v2/site/decisions', None),
    ('POST', '/api/v2/site/decisions', {'text': 'قاعدة جديدة', 'confirmed': True}),
    ('DELETE', '/api/v2/site/decisions/' + 'a' * 32, {'confirmed': True}),
    ('GET', '/api/v2/site/backups?page=pricing.html', None),
    ('POST', '/api/v2/site/restore', {'page': PAGE, 'backup_id': 1, 'confirmed': True}),
]


@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_routes_are_admin_only_closed_when_the_flag_is_off_and_never_touch_the_site(api, site, monkeypatch, method, path, body):
    for role in NON_ADMIN:
        assert api.call(method, path, body, role=role).status_code == 403, (role, path)
    assert api.anon(method, path, body).status_code in (401, 403)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = api.call(method, path, body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert site.web.calls == [] and site.sftp.log == [] and se.models(db).query.count() == 0
    assert ps.decision_model(db).query.count() == 0


def test_routes_send_no_store_on_every_answer(api, site):
    for method, path, body in ENDPOINTS:
        if method == 'GET':
            r = api.call(method, path, body)
            assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store', path
    assert api.call('GET', '/api/v2/site/blocks?page=.htaccess').headers.get('Cache-Control') == 'no-store'
    assert api.post('/api/v2/site/decisions', {}).headers.get('Cache-Control') == 'no-store'


def test_pages_route_lists_the_twelve_with_labels(api, site):
    d = api.get('/api/v2/site/pages').get_json()['pages']
    assert [p['page'] for p in d] == list(se.ALLOWED) and d[0] == {'page': 'Company-Site.html', 'label': 'الصفحة الرئيسية'}


def test_blocks_route_reads_live_only_for_allowed_pages(api, site):
    d = blocks_of(api)
    assert d['page'] == PAGE and d['label'] == 'صفحة الأسعار' and d['sha'] == sha_of(PRICING)
    assert H1 in [b['text'] for b in d['blocks']] and set(d['blocks'][0]) == {'path', 'tag', 'text', 'editable', 'note'}
    assert site.web.calls == ['https://elprofessor.net/pricing.html']
    for bad in ('.htaccess', 'blog.html', '', '../x'):
        assert api.get('/api/v2/site/blocks?page=' + bad).status_code == 400
    assert api.get('/api/v2/site/blocks').status_code == 400
    assert len(site.web.calls) == 1, 'المرفوض لا يستدعي الموقع'
    site.web.fail = True
    r = api.get('/api/v2/site/blocks?page=' + PAGE)
    assert r.status_code == 502 and r.get_json()['error'] == se.ERR_FETCH


def test_founder_edit_creates_a_proposal_that_the_normal_approve_route_publishes(api, site):
    d = blocks_of(api)
    h1 = [b for b in d['blocks'] if b['text'] == H1][0]
    r = api.post('/api/v2/site/edit', edit_body(d['sha'], h1['path'], H1, 'باقات بسيطة لكل خبير', by='evil@x.test'))
    assert r.status_code == 200, r.get_json()
    iid = r.get_json()['item_id']
    assert not any(e[0] == 'write' for e in site.sftp.log), 'الاقتراح لا يلمس الموقع'
    items = api.get('/api/v2/brain/items?section=content').get_json()['items']
    it = [i for i in items if i['id'] == iid][0]
    assert it['producer'] == 'site_edit_manual' and it['source'] == 'founder' and it['status'] == 'proposed' and it['kind'] == 'draft'
    assert it['approve_label'] == ps.APPROVE_LABEL and it['tag'] == 'تعديل الموقع'
    assert it['body']['edits'][0]['new'] == 'باقات بسيطة لكل خبير' and 'من «%s» إلى' % H1 in it['body']['text']
    assert 'meta' not in it and 'facts' not in it and 'sha' not in json.dumps(it)
    a = AuditLog.query.filter_by(action='v2_site.propose').order_by(AuditLog.id.desc()).first()
    assert a.actor_email == ADMIN and a.target == iid, 'الفاعل من التوكن لا من الجسم'
    r = api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True})
    assert r.status_code == 200 and r.get_json()['status'] == 'approved'
    assert 'باقات بسيطة لكل خبير' in live_bytes(site).decode('utf-8')
    assert len(se.list_backups(db, PAGE)) == 1
    assert api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True}).status_code == 409


def test_second_founder_edit_on_the_same_page_joins_the_open_proposal(api, site):
    d = blocks_of(api)
    path = lambda t: [b for b in d['blocks'] if b['text'] == t][0]['path']
    i1 = api.post('/api/v2/site/edit', edit_body(d['sha'], path(H1), H1, 'عنوان جديد')).get_json()['item_id']
    i2 = api.post('/api/v2/site/edit', edit_body(d['sha'], path(LEAD), LEAD, 'جملة جديدة بعد التعديل.')).get_json()['item_id']
    assert i1 == i2
    items = api.get('/api/v2/brain/items?section=content').get_json()['items']
    assert len([i for i in items if i['producer'] == 'site_edit_manual']) == 1
    assert [e['new'] for e in items[0]['body']['edits']] == ['عنوان جديد', 'جملة جديدة بعد التعديل.']
    # تعديل نفس الكتلة ثانية يستبدل ولا يكرّر
    api.post('/api/v2/site/edit', edit_body(d['sha'], path(H1), H1, 'عنوان أحدث'))
    items = api.get('/api/v2/brain/items?section=content').get_json()['items']
    assert [e['new'] for e in items[0]['body']['edits']] == ['جملة جديدة بعد التعديل.', 'عنوان أحدث']
    assert api.post('/api/v2/brain/items/%s/approve' % i1, {'confirmed': True}).status_code == 200
    now = live_bytes(site).decode('utf-8')
    assert 'عنوان أحدث' in now and 'جملة جديدة بعد التعديل.' in now


def test_founder_edit_validations(api, site):
    d = blocks_of(api)
    h1 = [b for b in d['blocks'] if b['text'] == H1][0]
    dup = [b for b in d['blocks'] if b['text'] == 'ابدأ الآن'][0]
    def post(**kw):
        b = edit_body(d['sha'], h1['path'], H1, kw.pop('new', 'نص جديد'))
        b.update(kw)
        return api.post('/api/v2/site/edit', b)
    assert api.post('/api/v2/site/edit', {k: v for k, v in edit_body(d['sha'], h1['path'], H1, 'x').items() if k != 'confirmed'}).status_code == 400
    assert post(confirmed='true').status_code == 400
    assert post(page='.htaccess').status_code == 400 and post(page='blog.html').status_code == 400
    assert post(sha=5).status_code == 400 and post(new=7).status_code == 400
    assert post(sha='0' * 64).status_code == 409, 'الصفحة تغيّرت منذ فتحها'
    assert post(old='نص قديم غير موجود').status_code == 422
    assert post(path='html[1]>nope').status_code == 422
    r = api.post('/api/v2/site/edit', edit_body(d['sha'], dup['path'], 'ابدأ الآن', 'يلا')); assert r.status_code == 422, 'المكرر غير قابل للتعديل'
    assert post(new='<b>x</b>').status_code == 400 and post(new='   ').status_code == 400
    assert post(new='نص ليقوّم الأداء').status_code == 400, 'القاعدة الآلية على الكلمة الممنوعة'
    assert post(new=H1).status_code == 400
    r = api.post('/api/v2/site/edit', edit_body(d['sha'], h1['path'], H1, 'الذكاء الاصطناعي يخدم الخبير'))
    assert r.status_code == 400, 'عنوان يبدأ بالذكاء'
    assert engine._models(db)[0].query.count() == 0 and not any(e[0] == 'write' for e in site.sftp.log)


def test_stale_manual_proposal_is_refused_at_approval_with_the_spec_message(api, site):
    d = blocks_of(api)
    h1 = [b for b in d['blocks'] if b['text'] == H1][0]
    iid = api.post('/api/v2/site/edit', edit_body(d['sha'], h1['path'], H1, 'جديد')).get_json()['item_id']
    site.sftp.files[SFTP_ROOT + '/' + PAGE] = PRICING.replace('دورات مسجلة', 'دورات أخرى').encode('utf-8')
    r = api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True})
    assert r.status_code == 422 and r.get_json()['error'] == 'تغيّرت الصفحة منذ الاقتراح؛ أعد التوليد'
    assert 'جديد' not in live_bytes(site).decode('utf-8')
    assert api.post('/api/v2/brain/items/%s/reject' % iid, {'confirmed': True}).status_code == 200


def test_decisions_routes_crud_confirmed_actor_and_audit(api, site):
    d = api.get('/api/v2/site/decisions').get_json()['decisions']
    assert len(d) == len(ps.SEED_DECISIONS) and set(d[0]) == {'id', 'text', 'created_by', 'created_at', 'seed'} and d[0]['seed'] is True
    assert api.post('/api/v2/site/decisions', {'text': 'قاعدة جديدة'}).status_code == 400, 'بلا تأكيد'
    assert api.post('/api/v2/site/decisions', {'text': 'ا', 'confirmed': True}).status_code == 400
    r = api.post('/api/v2/site/decisions', {'text': 'قاعدة جديدة من المؤسس', 'confirmed': True, 'created_by': 'evil@x.test'})
    assert r.status_code == 200
    new = r.get_json()['decision']
    assert new['created_by'] == ADMIN and new['seed'] is False
    assert api.post('/api/v2/site/decisions', {'text': 'قاعدة جديدة من المؤسس', 'confirmed': True}).status_code == 400, 'مكررة'
    assert new['id'] in [x['id'] for x in api.get('/api/v2/site/decisions').get_json()['decisions']]
    url = '/api/v2/site/decisions/' + new['id']
    assert api.call('DELETE', url, {}).status_code == 400, 'بلا تأكيد'
    assert api.call('DELETE', '/api/v2/site/decisions/not-an-id', {'confirmed': True}).status_code == 400
    assert api.call('DELETE', '/api/v2/site/decisions/' + 'b' * 32, {'confirmed': True}).status_code == 404
    assert api.call('DELETE', url, {'confirmed': True}).status_code == 200
    assert api.call('DELETE', url, {'confirmed': True}).status_code == 404
    assert new['id'] not in [x['id'] for x in api.get('/api/v2/site/decisions').get_json()['decisions']]
    acts = [a.action for a in AuditLog.query.filter(AuditLog.action.like('v2_site.decision%')).all()]
    assert acts.count('v2_site.decision_add') == 1 and acts.count('v2_site.decision_remove') == 1
    # حذف قاعدة مبذورة جائز، ولا تعود البذرة
    seed_id = d[0]['id']
    assert api.call('DELETE', '/api/v2/site/decisions/' + seed_id, {'confirmed': True}).status_code == 200
    assert seed_id not in [x['id'] for x in api.get('/api/v2/site/decisions').get_json()['decisions']]


def test_new_decision_changes_what_the_brain_sees_on_the_next_review(api, site, env, monkeypatch):   # noqa: F811
    api.post('/api/v2/site/decisions', {'text': 'قاعدة فريدة للاختبار', 'confirmed': True})
    run_review(site, monkeypatch, env, ai_reply([]))
    sent = env.calls[0]['user']
    assert 'قاعدة فريدة للاختبار' in sent


def test_backups_and_restore_routes(api, site):
    assert api.get('/api/v2/site/backups?page=' + PAGE).get_json() == {'page': PAGE, 'backups': []}
    assert api.get('/api/v2/site/backups?page=.htaccess').status_code == 400
    d = blocks_of(api)
    h1 = [b for b in d['blocks'] if b['text'] == H1][0]
    iid = api.post('/api/v2/site/edit', edit_body(d['sha'], h1['path'], H1, 'عنوان جديد')).get_json()['item_id']
    assert api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True}).status_code == 200
    bk = api.get('/api/v2/site/backups?page=' + PAGE).get_json()['backups']
    assert len(bk) == 1 and set(bk[0]) == {'id', 'sha256', 'created_at', 'created_by', 'note', 'size'}
    assert bk[0]['created_by'] == ADMIN and len(bk[0]['sha256']) == 12 and 'html' not in json.dumps(bk).lower().replace('html_gz', '')
    body = {'page': PAGE, 'backup_id': bk[0]['id'], 'confirmed': True}
    assert api.post('/api/v2/site/restore', dict(body, confirmed=False)).status_code == 400
    assert api.post('/api/v2/site/restore', {k: v for k, v in body.items() if k != 'confirmed'}).status_code == 400
    assert api.post('/api/v2/site/restore', dict(body, page='.htaccess')).status_code == 400
    assert api.post('/api/v2/site/restore', dict(body, backup_id='1')).status_code == 400
    assert api.post('/api/v2/site/restore', dict(body, backup_id=True)).status_code == 400
    assert api.post('/api/v2/site/restore', dict(body, backup_id=424242)).status_code == 404
    assert 'عنوان جديد' in live_bytes(site).decode('utf-8')
    r = api.post('/api/v2/site/restore', body)
    assert r.status_code == 200 and live_bytes(site) == PRICING.encode('utf-8')
    a = AuditLog.query.filter_by(action='v2_site.restore').order_by(AuditLog.id.desc()).first()
    assert a.actor_email == ADMIN and json.loads(a.meta_json)['ok'] is True
    assert site.sftp.files[SFTP_ROOT + '/.htaccess'] == b'RewriteEngine On\n'
    assert len(api.get('/api/v2/site/backups?page=' + PAGE).get_json()['backups']) == 2, 'نسخة ما قبل الإرجاع'


def test_restore_failure_is_reported_with_its_status(api, site):
    bk = se.save_backup(db, PAGE, PRICING.encode('utf-8'), 'a@x.test')
    site.sftp.fail_rename = True
    r = api.post('/api/v2/site/restore', {'page': PAGE, 'backup_id': bk.id, 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['error'] == se.ERR_REMOTE


# ───────────────────────────────────────────────────────────── ربط التسليم

def test_wiring_registry_dockerfile_and_guarded_registration():
    assert [p.id for p in registry.PRODUCERS][-2:] == ['site_review', 'site_edit_manual']
    d = open(os.path.join(ROOT, 'Dockerfile'), encoding='utf-8').read()
    for line in ('COPY backend/site_edit.py /app/site_edit.py', 'COPY backend/v2_site_routes.py /app/v2_site_routes.py', 'COPY backend/brain2 /app/brain2'):
        assert line in d, line
    a = open(os.path.join(ROOT, 'backend', 'app.py'), encoding='utf-8').read()
    i = a.index('import v2_brain2_routes as _v2_brain2')
    j = a.index('import v2_site_routes as _v2_site')
    assert 0 < j - i < 400 and 'v2 site routes not loaded' in a[j:j + 300]


def test_site_edit_never_deletes_and_never_names_htaccess_as_a_target():
    src = open(os.path.join(ROOT, 'backend', 'site_edit.py'), encoding='utf-8').read()
    code = re.sub(r'""".*?"""', '', src, flags=re.S)
    code = re.sub(r'#.*', '', code)
    for forbidden in ('.remove(', '.unlink(', '.rmdir(', 'os.remove', 'shutil', '.mkdir('):
        assert forbidden not in code, forbidden
    assert '.htaccess' not in code


def test_no_real_network_or_credentials_in_the_new_modules():
    for f in ('backend/site_edit.py', 'backend/v2_site_routes.py', 'backend/brain2/producers_site.py'):
        s = open(os.path.join(ROOT, f), encoding='utf-8').read()
        assert not re.search(r'sk-[A-Za-z0-9]{10,}|password\s*=\s*[\'"][^\'"]+[\'"]', s), f
