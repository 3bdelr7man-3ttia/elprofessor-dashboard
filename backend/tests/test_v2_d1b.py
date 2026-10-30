# -*- coding: utf-8 -*-
"""الهيكل الجديد (D1-B) — ١٢ قسمًا بتبويبات بدل القائمة القديمة، ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2_d1b.py

⛔ صفر شبكة: المنطق النقي (خريطة الأقسام) بيتشغّل في node على v2-logic.js، والباقي نصوص الملفات. اللقطات (المتصفح الحقيقي على
المنصة الوهمية) في `uiharness/v2_shots.py d1b` — هي اللي بتثبّت إن مفيش أثر للقائمة القديمة والمفتاح مفتوح، وإن شارات القائمة
نفس أعداد مربّعات اللوحة، وإن الرابط القديم بيهبط على قسمه.

اللي بيثبّته:
  ١. كل مفتاح قديم (MODULES + REDIRECTS + اللوحة) بيقع في قسم وتبويب، وكل تبويب بيعرّف نفسه بالعكس (بلا يتيم ولا تبويب ميت).
  ٢. العنوان `#s/<قسم>[/<تبويب>]` بيروح ويرجع، وكل رابط قديم بيهبط على قسمه بتبويبه الصحيح.
  ٣. المفتاح مقفول = `MODULES` و`renderNav` و`go` زي ما هي بالحرف (خط واحد حارس في كل واحدة).
  ٤. الشارات من `V2.tiles()` نفسها (مفيش عدّ ثانٍ) · نصوص الأقسام بالفصحى بلا مصطلحات تقنية ولا «ذكاء/AI» في أول عنوان.
  ٥. القائمة القديمة وكتلة الشركة مخفيّتان بالـCSS تحت صنف الغلاف بس، والغلاف مش في الـHTML الثابت.
"""
import hashlib
import json
import os
import re
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
NODE = __import__('shutil').which('node')
needs_node = pytest.mark.skipif(not NODE, reason='needs node')
PSEUDO_MODS = {'v2files', 'v2disputes', 'v2person',                       # D2: موديولات وهمية يرسمها V2D2 تحت الغلاف الجديد فقط
               'v2m_overview', 'v2m_payouts', 'v2m_receipts', 'v2m_prices', 'v2m_shares', 'v2m_ads', 'v2b_offers', 'v2b_requests',   # D3: يرسمها V2D3
               'v2s_brain'}   # الجولة الأخيرة: قسم العقل يرسمه V2SEC.brain


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


HTML = _read('dashboard-cloud', 'index.html')


def _node(js):
    script = "const L=require(%s);\n%s" % (json.dumps(os.path.join(DC, 'v2-logic.js')), js)
    p = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


def _modules_block():
    return HTML[HTML.index('const MODULES={'):HTML.index('// موديولات الأدوار غير-الأدمن')]


def _module_keys():
    keys = re.findall(r'^  ([a-z_]+):\{label:', _modules_block(), flags=re.M)
    assert len(keys) >= 20, keys
    return keys


def _redirects():
    body = HTML[HTML.index('const REDIRECTS={'):HTML.index('// موديولات الأدوار غير-الأدمن')]
    out = {}
    for k, mod, fn in re.findall(r"^  ([a-z]+):\['([a-z]+)',(null|function\(\)\{.*?\})\]", body, flags=re.M):
        out[k] = (mod, fn)
    assert set(out) == {'overview', 'messages', 'packages', 'tutorials', 'partners', 'foundation'}, out
    return out


# ---------------------------------------------------------------- ١) الخريطة

@needs_node
def test_twelve_sections_in_the_boards_order_each_with_its_photo():
    secs = _node("console.log(JSON.stringify({s:L.SECTIONS.map(s=>[s.key,s.label,s.img]),t:L.TILE_DEFS.map(t=>[t.key,t.label,t.img])}))")
    assert secs['s'][0] == ['home', 'اللوحة', None]
    assert secs['s'][1:] == secs['t'], 'ترتيب الأقسام وأسماؤها وصورها = مربّعات اللوحة'
    assert [s[0] for s in secs['s'][1:]] == ['files', 'disputes', 'courses', 'market', 'books', 'people', 'money', 'content', 'marketing', 'reports', 'brain', 'company']


@needs_node
def test_the_tabs_match_the_approved_table():
    got = _node("console.log(JSON.stringify(L.SECTIONS.map(s=>[s.key,s.tabs.map(t=>[t.key,t.label,t.mod])])))")
    want = {
        'home': [['board', 'اللوحة والقرارات', 'home'], ['inbox', 'كل الوارد', 'inbox']],
        # D2: «الملفات» و«النزاعات» لوحتا تذاكر (موديولان وهميان ورا الغلاف)، والوارد القديم في تبويب «كل …» (لا شاشة اتفقدت)
        'files': [['files', 'الملفات', 'v2files'], ['experts', 'الخبراء', 'team'], ['all', 'كل الملفات', 'inbox']],
        'disputes': [['disputes', 'النزاعات', 'v2disputes'], ['escrow', 'الضمان', 'escrow'], ['all', 'كل النزاعات', 'inbox']],
        'courses': [['courses', 'الدورات', 'courses'], ['trainers', 'المدرّبون', 'team']],
        'market': [['requests', 'الطلبات', 'market']],
        # D3: مراجعة العروض وطلبات القرّاء أولًا (موديولان وهميان ورا الغلاف)، والشاشة القديمة آخرًا
        'books': [['offers', 'مراجعة العروض', 'v2b_offers'], ['requests', 'طلبات القرّاء', 'v2b_requests'], ['books', 'الكتب والأعمال', 'knowledge']],
        'people': [['users', 'المستخدمون', 'users'], ['invites', 'الدعوات', 'invites'], ['messages', 'الرسائل', 'inbox'],
                   ['person', 'صفحة الشخص', 'v2person']],
        # D3: «الفلوس» بهيكلها الجديد، والشاشتان القديمتان (المالية والباقات) في آخر تبويب «كل السجلات» + تبويب مخفي للإيصالات القديمة
        'money': [['overview', 'نظرة', 'v2m_overview'], ['payouts', 'التحويلات', 'v2m_payouts'], ['receipts', 'الإيصالات والمدفوعات العالقة', 'v2m_receipts'],
                  ['prices', 'الأسعار', 'v2m_prices'], ['shares', 'النسب والإعدادات', 'v2m_shares'], ['ads', 'إعلانات الأعمال', 'v2m_ads'],
                  ['all', 'كل السجلات', 'finance'], ['manual', 'الإيصالات (الشاشة القديمة)', 'escrow']],
        'content': [['topics', 'المحتوى', 'topics'], ['tutorials', 'دليل الاستخدام', 'topics']],
        'marketing': [['campaigns', 'الحملات', 'marketing']],
        'reports': [['demand', 'تحليل الطلب', 'analysis']],
        'brain': [['log', 'القواعد وسجل اليوم', 'v2s_brain'], ['helpers', 'المساعدون', 'ai']],   # الجولة الأخيرة: تبويب القواعد وسجل اليوم موديول وهمي
        'company': [['invest', 'الاستثمار والشركاء', 'investment'], ['targets', 'الأهداف والتأسيس', 'targets'], ['settings', 'الإعدادات', 'settings']],
    }
    assert {k: t for k, t in got} == want


@needs_node
def test_every_old_module_key_lands_on_a_section_and_a_tab():
    keys = set(_module_keys()) | set(_redirects()) | {'home'}
    res = _node("const ks=%s;console.log(JSON.stringify(ks.map(k=>[k,L.sectionFor(k)])))" % json.dumps(sorted(keys)))
    for k, m in res:
        assert m and m['section'] and m['tab'], 'مفتاح قديم بلا قسم: ' + k
    landed = {k: (m['section'], m['tab']) for k, m in res}
    assert landed['inbox'] == ('home', 'inbox') and landed['overview'] == ('home', 'inbox')
    assert landed['team'] == ('files', 'experts') and landed['escrow'] == ('disputes', 'escrow')
    assert landed['finance'] == ('money', 'all') and landed['packages'] == ('money', 'all')
    assert landed['messages'] == ('people', 'messages') and landed['tutorials'] == ('content', 'tutorials')
    assert landed['partners'] == ('company', 'invest') and landed['foundation'] == ('company', 'targets')
    assert landed['knowledge'] == ('books', 'books') and landed['ai'] == ('brain', 'helpers') and landed['home'] == ('home', 'board')
    assert landed['analysis'] == ('reports', 'demand') and landed['market'] == ('market', 'requests')


@needs_node
def test_no_orphan_tab_each_tab_names_a_real_module_and_recognises_itself():
    keys = set(_module_keys()) | {'home'} | PSEUDO_MODS
    res = _node("""const out=[];L.SECTIONS.forEach(s=>s.tabs.forEach(t=>{const m=L.sectionFor(t.mod,t.st);
      out.push([s.key,t.key,t.mod,m&&m.section,m&&m.tab]);}));console.log(JSON.stringify(out))""")
    for sec, tab, mod, gs, gt in res:
        assert mod in keys, (sec, tab, mod)
        assert (gs, gt) == (sec, tab), 'التبويب ما بيتعرّفش بحالته: %s/%s ⇒ %s/%s' % (sec, tab, gs, gt)


@needs_node
def test_every_old_module_has_a_tab_that_shows_it_so_nothing_is_lost():
    keys = set(_module_keys()) | {'home'}
    hosted = _node("console.log(JSON.stringify([...new Set(L.SECTIONS.flatMap(s=>s.tabs.map(t=>t.mod)))]))")
    absorbed = set(_redirects()) | {'users_tag'}
    for k in keys - absorbed:
        assert k in hosted, 'شاشة قديمة بلا تبويب يستضيفها: ' + k


@needs_node
def test_the_redirect_aliases_carry_the_same_inner_state_as_REDIRECTS():
    red = _redirects()
    al = _node("console.log(JSON.stringify(L.ALIASES))")
    assert set(al) == set(red)
    for k, (mod, fn) in red.items():
        assert al[k]['mod'] == mod, k
        want = dict(re.findall(r"([a-zA-Z]+)='([a-z:_]+)'", fn))
        assert al[k]['state'] == want, (k, al[k], want)


@needs_node
def test_inner_screen_state_picks_the_right_tab_and_unknown_state_stays_put():
    cases = [
        ('inbox', {'activeFilter': 't:files'}, 'files', 'all'), ('inbox', {'activeFilter': 'attn'}, 'files', 'all'),
        ('inbox', {'activeFilter': 'review'}, 'files', 'all'), ('inbox', {'activeFilter': 'nocand'}, 'files', 'all'),
        ('inbox', {'activeFilter': 't:disputes'}, 'disputes', 'all'), ('inbox', {'activeFilter': 't:legacy'}, 'disputes', 'all'),
        ('inbox', {'activeFilter': 't:messages'}, 'people', 'messages'), ('inbox', {'activeFilter': 'all'}, 'home', 'inbox'),
        ('inbox', {'activeFilter': 'human'}, 'home', 'inbox'), ('inbox', {'activeFilter': 't:money'}, 'home', 'inbox'),
        ('team', {'teamTab': 'trainers'}, 'courses', 'trainers'), ('team', {'teamTab': 'experts'}, 'files', 'experts'),
        ('escrow', {'escTab': 'manual'}, 'money', 'manual'), ('escrow', {'escTab': 'disputes'}, 'disputes', 'escrow'),
        ('finance', {'finTab': 'packages'}, 'money', 'all'), ('finance', {'finTab': 'withdrawals'}, 'money', 'all'),
        ('topics', {'topicsTab': 'tutorials'}, 'content', 'tutorials'), ('topics', {'topicsTab': 'news'}, 'content', 'topics'),
        ('courses', {'courseTab': 'demand'}, 'courses', 'courses'), ('home', {'v2mode': 'brain'}, 'home', 'board'),   # سجل العقل القديم لم يعد وضعًا للوحة (صار تبويب v2s_brain)
        
        ('home', {'v2mode': 'focus'}, 'home', 'board'), ('targets', {'tgTab': 'foundation'}, 'company', 'targets'),
        ('investment', {'invTab': 'opps'}, 'company', 'invest'),
    ]
    got = _node("console.log(JSON.stringify(%s.map(c=>{const m=L.sectionFor(c[0],c[1]);return [m.section,m.tab];})))" % json.dumps(cases))
    for c, g in zip(cases, got):
        assert g == [c[2], c[3]], c
    # «الفريق الإداري» (تبويب داخلي بلا تبويب قسم): يفضل حيث المؤسس.
    stay = _node("""console.log(JSON.stringify([
      L.sectionFor('team',{teamTab:'admins'},{section:'courses',tab:'trainers'}),
      L.sectionFor('team',{teamTab:'admins'},{section:'files',tab:'experts'}),
      L.sectionFor('team',{teamTab:'admins'})].map(m=>[m.section,m.tab])))""")
    assert stay == [['courses', 'trainers'], ['files', 'experts'], ['files', 'experts']]


@needs_node
def test_an_unknown_module_is_not_mapped():
    assert _node("console.log(JSON.stringify(L.sectionFor('nope')))") is None
    assert _node("console.log(JSON.stringify(L.sectionFor('')))") is None


# ---------------------------------------------------------------- ٢) العنوان

@needs_node
def test_section_addresses_round_trip():
    res = _node("""const out=[];L.SECTIONS.forEach(s=>s.tabs.forEach(t=>{const h=L.sectionHash(s.key,t.key);
      out.push([s.key,t.key,h,L.parseSectionHash(h),L.parseSectionHash(h.slice(1)),L.routeFor(h)]);}));console.log(JSON.stringify(out))""")
    assert len(res) == 35                      # ٢٥ + «كل الملفات» و«كل النزاعات» + صفحة الشخص (مخفية) + D3: الفلوس ٨ (واحد مخفي) بدل ٣، والكتب ٣ بدل ١
    for sec, tab, h, p1, p2, r in res:
        if (sec, tab) in (('people', 'person'), ('money', 'manual')):
            continue                           # تبويب مخفي بلا بريد: يرجع لأول تبويب (يُختبر في test_v2_d2)
        assert h == '#s/%s/%s' % (sec, tab)
        assert p1 == {'section': sec, 'tab': tab, 'exact': True} == p2
        assert (r['section'], r['tab']) == (sec, tab)


@needs_node
def test_addresses_without_a_tab_or_with_garbage_fall_back_safely():
    res = _node("""console.log(JSON.stringify([L.parseSectionHash('#s/money'),L.parseSectionHash('#s/money/zzz'),L.parseSectionHash('#s/zzz/x'),
      L.parseSectionHash('#money'),L.parseSectionHash(''),L.parseSectionHash(null),L.sectionHash('files')]))""")
    assert res[0] == {'section': 'money', 'tab': 'overview', 'exact': True}
    assert res[1] == {'section': 'money', 'tab': 'overview', 'exact': False}
    assert res[2] is None and res[3] is None and res[4] is None and res[5] is None
    assert res[6] == '#s/files'


@needs_node
def test_old_links_land_on_their_section_with_the_right_tab():
    links = {'#finance': ('money', 'all'), '#packages': ('money', 'all'), '#messages': ('people', 'messages'),
             '#invites': ('people', 'invites'), '#users': ('people', 'users'), '#escrow': ('disputes', 'escrow'),
             '#courses': ('courses', 'courses'), '#team': ('files', 'experts'), '#market': ('market', 'requests'),
             '#knowledge': ('books', 'books'), '#topics': ('content', 'topics'), '#tutorials': ('content', 'tutorials'),
             '#marketing': ('marketing', 'campaigns'), '#analysis': ('reports', 'demand'), '#ai': ('brain', 'helpers'),
             '#investment': ('company', 'invest'), '#partners': ('company', 'invest'), '#targets': ('company', 'targets'),
             '#foundation': ('company', 'targets'), '#settings': ('company', 'settings'), '#inbox': ('home', 'inbox'),
             '#overview': ('home', 'inbox'), '#home': ('home', 'board'), '': ('home', 'board')}
    res = _node("const ks=%s;console.log(JSON.stringify(ks.map(k=>L.routeFor(k,{}))))" % json.dumps(list(links)))
    for (k, want), m in zip(links.items(), res):
        assert (m['section'], m['tab']) == want, k
    assert _node("console.log(JSON.stringify(L.routeFor('#zzz',{})))") is None


# ---------------------------------------------------------------- ٣) المفتاح مقفول = نفس الصفحة

def test_the_closed_switch_keeps_the_menu_declaration_byte_for_byte():
    mods = _modules_block()
    assert hashlib.sha256(mods.encode('utf-8')).hexdigest().startswith('2318da89b37901d6'), \
        'MODULES/CO_PINNED/REDIRECTS اتغيّرت — لو التغيير مقصود حدّث البصمة هنا، ولو لأ فالمفتاح المقفول اتأثّر'
    assert 'home:' not in mods


def test_render_nav_differs_only_by_the_single_guard_line():
    rn = HTML[HTML.index('function renderNav(){'):HTML.index('// قائمة موديولات الدور غير-الأدمن')]
    guard = ("  // D1-B: الهيكل الجديد (مفتاح مفتوح) يرسم قائمته بنفسه ولا يلمس القائمة القديمة.\n"
             "  if(window.V2_ON&&window.V2SHELL&&V2SHELL.on&&role==='admin'){V2SHELL.nav();return;}\n")
    assert rn.startswith('function renderNav(){\n' + guard)
    rest = rn.replace(guard, '')
    assert hashlib.sha256(rest.encode('utf-8')).hexdigest().startswith('b6fdd6c7bff45603')


def test_go_differs_only_by_the_guard_and_the_extracted_reset():
    go = HTML[HTML.index('function go(mod){'):HTML.index('function renderView(){')]
    assert go.startswith("function go(mod){\n  // D1-B: الهيكل الجديد يحوّل أي موديول قديم إلى قسمه وتبويبه (مفتاح مقفول = السطر ده مش بيتنفّذ).\n"
                         "  if(window.V2_ON&&window.V2SHELL&&V2SHELL.on&&role==='admin')return v2GoShell(mod);\n")
    reset = HTML[HTML.index('function resetViewState(){'):HTML.index('function go(mod){')]
    for v in ("selected=null", "activeFilter='all'", "escTab='sessions'", "finTab='summary'", "teamTab='experts'", "topicsTab='ideas'",
              "courseTab='platform'", "invTab='owners'", "tgTab='goals'", "foundationTab='assets'", "contentTab='pending'",
              "mkLane='all'", "mkSel=null", "invSel=null", "invGroupBy=false"):
        assert v in reset, v
    assert "current=mod;resetViewState();" in go


def test_go_ops_and_render_view_hooks_do_nothing_when_the_shell_is_off():
    assert "if(typeof land==='function')land();if(window.V2SHELL&&V2SHELL.on)v2Reconcile();}" in HTML
    rv = HTML[HTML.index('function renderView(){'):HTML.index("if(current==='home'&&window.V2_ON&&window.V2)return V2.render(v);")]
    assert "const sh=!!(window.V2SHELL&&V2SHELL.on);" in rv
    assert "ap.classList.toggle('v2-home',current==='home'&&!!window.V2_ON&&!sh)" in rv
    assert "if(ap&&sh){" in rv


def test_the_shell_is_not_in_the_static_markup_and_files_are_wired():
    body = HTML[HTML.index('<body>'):HTML.index('<script src="site-content.js">')]
    for needle in ('v2Side', 'v2Sheet', 'v2sec', 'v2-shell', 'v2c-tab'):
        assert needle not in body, needle
    assert '<link rel="stylesheet" href="v2-shell.css">' in HTML
    assert '<script src="v2-shell.js"></script>' in HTML
    assert HTML.index('v2-logic.js') < HTML.index('v2-home.js') < HTML.index('v2-shell.js')
    boot = HTML[HTML.index('window.EP_BOOT=function(){'):HTML.index('function epBootCore(){')]
    assert boot.index('epBootCore();') < boot.index('v2LoadFlag(') and 'v2ShellBoot()' in boot
    assert "EP.role==='admin'" in boot


@pytest.mark.parametrize('dockerfile', ['Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')])
def test_dockerfiles_ship_the_shell_files(dockerfile):
    txt = _read(dockerfile)
    assert 'dashboard-cloud/v2-shell.js' in txt and 'dashboard-cloud/v2-shell.css' in txt
    for f in ('v2-shell.js', 'v2-shell.css'):
        assert os.path.getsize(os.path.join(DC, f)) > 1000


# ---------------------------------------------------------------- ٤) الشارات والنصوص

def test_badges_come_from_the_same_tiles_and_nothing_is_counted_twice():
    js = _read('dashboard-cloud', 'v2-shell.js')
    assert 'V2.tiles()' in js and 'tileLoading' in js
    code = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
    for bad in ('opsQueue', 'INBOX', 'EP.data', 'EP.state', 'walletPayouts', 'oldest_hours'):
        assert bad not in code, 'الغلاف ما بيعدّش بنفسه: ' + bad
    home = _read('dashboard-cloud', 'v2-home.js')
    assert 'V2.tiles = function () { var g = gather(); return L.v2Tiles(g.Q, g.extras); };' in home
    # اللوحة نفسها بتبني مربّعاتها من نفس gather()
    assert 'var tiles = L.v2Tiles(Q, g.extras);' in home


@needs_node
def test_section_texts_are_plain_standard_arabic_without_tech_words():
    secs = _node("console.log(JSON.stringify(L.SECTIONS))")
    banned = ('AI', 'ai', 'ذكاء', 'API', 'JSON', 'داشبورد', 'الدرج', 'مودال', 'بعدين', 'كاش')
    texts = []
    for s in secs:
        texts += [s['label'], s['desc']]
        for t in s['tabs']:
            texts.append(t['label'])
    for t in texts:
        assert re.search('[؀-ۿ]', t), t
        assert not re.search('[A-Za-z]', t), t
        for b in banned:
            assert b not in t, (t, b)
    for s in secs:
        for head in (s['label'], s['desc']) + tuple(t['label'] for t in s['tabs']):
            assert not head.startswith(('ذكاء', 'الذكاء', 'AI')), head


def test_shell_script_visible_strings_are_clean():
    js = _read('dashboard-cloud', 'v2-shell.js')
    code = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
    strings = re.findall(r"'([^']*[؀-ۿ][^']*)'", code)
    assert strings
    for s in strings:
        for b in ('ذكاء', 'AI', 'بعدين', 'الدرج', 'داشبورد'):
            assert b not in s, (s, b)


def test_the_old_rail_and_company_block_are_hidden_only_under_the_shell_class():
    css = _read('dashboard-cloud', 'v2-shell.css')
    assert '.app.v2-shell .rail,.app.v2-shell #coPin,.app.v2-shell .railscrim{display:none!important}' in css
    # كل قاعدة ظاهرة للقائمة الجديدة تحت أصنافها هي أو تحت `.app.v2-shell` — مفيش قاعدة تلمس `.rail` من غير الصنف.
    for sel in re.findall(r'([^{}]+)\{', re.sub(r'/\*.*?\*/', '', css, flags=re.S)):
        for part in sel.split(','):
            part = part.strip()
            if re.search(r'(^|\s)\.rail\b|#coPin', part):
                assert part.startswith(('.app.v2-shell', '.app.v2-pre')), part
    # الشاشات الأضيق: القائمة الجانبية مخفية وورقة الأقسام بدلها، وفوق ١١٨٠ العكس
    assert '@media(min-width:1180px){\n  .v2-side{display:flex' in css
    assert '@media(max-width:1179px)' in css and 'grid-template-columns:repeat(3,minmax(0,1fr))' in css
    assert '.v2c-tab{flex:none;min-height:48px' in css and 'overflow-x:auto' in css


def test_tabs_scroll_sideways_inside_their_strip_not_the_page():
    css = _read('dashboard-cloud', 'v2-shell.css')
    assert re.search(r'\.v2c-tabs\{[^}]*overflow-x:auto[^}]*max-width:100%', css)
    assert re.search(r'\.app\.v2-shell\.v2-focus \.v2-sec\{display:none\}', css)


def test_no_flash_of_the_old_rail_hint_is_admin_only_and_never_cleared_by_a_failure():
    boot = HTML[HTML.index('window.EP_BOOT=function(){'):HTML.index('function epBootCore(){')]
    assert "EP.role==='admin'&&window.V2&&localStorage.getItem('ep_v2_shell')==='1'" in boot
    assert "classList.add('v2-pre')" in boot and "classList.remove('v2-pre')" in boot
    flag = HTML[HTML.index('function v2LoadFlag'):HTML.index('window.EP_BOOT=function(){')]
    # الذاكرة بتتكتب/تتمسح من رد حاسم بس (then) — الفشل والتأخير (catch / مهلة الثلاث ثواني) ما بيلمسوهاش.
    then, _, catch = flag.partition('.catch(')
    assert "localStorage.setItem('ep_v2_shell','1')" in then and "localStorage.removeItem('ep_v2_shell')" in then
    assert 'localStorage' not in catch
    css = _read('dashboard-cloud', 'v2-shell.css')
    assert '.app.v2-pre .main{visibility:hidden}' in css


# ---------------------------------------------------------------- ٥) الملفات الجديدة بلا أثر على القديم

def test_old_screen_files_were_not_touched_beyond_the_hooks():
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert 'V2SHELL' not in api and 'v2Reconcile' not in api


# ---------------------------------------------------------------- ٦) إصلاحات مراجعة D1-B

@needs_node
def test_old_foundation_link_keeps_its_inner_tab_state():
    r = _node("console.log(JSON.stringify(['foundation','packages','messages','tutorials','partners','overview'].map(h=>L.routeFor(h))))")
    f = r[0]
    assert (f['section'], f['tab']) == ('company', 'targets') and f['st']['tgTab'] == 'foundation'
    assert r[1]['st']['finTab'] == 'packages' and r[2]['st']['activeFilter'] == 't:messages' and r[3]['st']['topicsTab'] == 'tutorials'
    # الحالة المدموجة لا تلوّث تبويبات الخريطة نفسها
    assert _node("L.routeFor('foundation');console.log(JSON.stringify(L.tabByKey('company','targets').st))") == {}
    assert "V2_SETTERS" in HTML and "opts.st" in HTML and "st:rt.st" in HTML


@needs_node
def test_inbox_chips_do_not_move_the_user_out_of_files():
    res = _node("""const h={section:'files',tab:'all'};
      console.log(JSON.stringify(['all','late','human','fyi','t:money','t:verify'].map(f=>{const m=L.sectionFor('inbox',{activeFilter:f},h);return [m.section,m.tab];})
        .concat([L.sectionFor('inbox',{activeFilter:'all'},null)].map(m=>[m.section,m.tab]))
        .concat([L.sectionFor('inbox',{activeFilter:'t:disputes'},h)].map(m=>[m.section,m.tab]))))""")
    assert res[:6] == [['files', 'all']] * 6
    assert res[6] == ['home', 'inbox'] and res[7] == ['disputes', 'all']


def test_inbox_search_stays_until_the_phone_width_and_copy_is_neutral():
    css = _read('dashboard-cloud', 'v2-shell.css')
    i = css.index('.app.v2-shell.v2-inbox .topbar .search{display:none}')
    assert css.rfind('@media', 0, i) == css.rindex('@media(max-width:760px)', 0, i)
    js = _read('dashboard-cloud', 'v2-shell.js')
    assert 'المؤسس' not in js
    assert 'الحاجة الجاية' not in _read('dashboard-cloud', 'v2-logic.js').split('var SECTIONS')[1]


def test_header_and_sheet_do_not_steal_scroll_or_focus():
    js = _read('dashboard-cloud', 'v2-shell.js')
    assert 'scrollIntoView' not in js
    assert 'sheetDirty' in js and "e.key !== 'Tab'" in js
