# -*- coding: utf-8 -*-
"""منصة «ناقشها في الساحة» بديل في الذاكرة لصور وفحوص محرّر المقال (docs/v2/saha-link/SPEC.md).

ترث `content_fixtures.ContentPlatform` وتزيد عليها سلوك جسر النقاشات كما في المنصة: الإنشاء مسودة، و`/publish` يفتحه، والقراءة تحمل
`source_article_slug`. أعطال تُضبط من السكربت: `lost_after_create` (النقاش اتعمل والرد ضاع) و`publish_fails`.
"""
import copy
import re

import content_fixtures as cfx

TID_PREFIX = 'c0ffee00-1111-4222-8333-'


class SahaLinkPlatform(cfx.ContentPlatform):
    def __init__(self, **kw):
        super(SahaLinkPlatform, self).__init__(**kw)
        self.lost_after_create = False
        self.publish_fails = False
        self.made = 0

    def _extra(self, method, path, params, body):
        m = method.upper()
        if path == '/api/bridge/topics' and m == 'POST':
            self.made += 1
            row = {'id': TID_PREFIX + '%012d' % self.made, 'title': body.get('title', ''), 'question': body.get('question', ''), 'status': 'draft',
                   'source': body.get('source') or 'human', 'source_article_slug': body.get('source_article_slug'), 'cover_url': body.get('cover_url', ''),
                   'category': 'عام', 'specialty': 'عام', 'engagement': {'comments': 0, 'reactions': 0}, 'opinions_count': 0, 'created_at': '2026-11-01T09:00:00Z'}
            self.topics.insert(0, row)
            self._rec(m, path, body)
            if self.lost_after_create:
                return 504, {'detail': 'timeout'}
            return 200, copy.deepcopy(row)
        mm = re.match(r'^/api/bridge/topics/([^/]+)/publish$', path)
        if mm and m == 'POST':
            self._rec(m, path, body)
            if self.publish_fails:
                return 404, {'detail': 'Topic not found'}
            row = self._find(self.topics, mm.group(1))
            if not row:
                return 404, {'detail': 'Topic not found'}
            row['status'] = 'published'
            return 200, copy.deepcopy(row)
        return super(SahaLinkPlatform, self)._extra(method, path, params, body)
