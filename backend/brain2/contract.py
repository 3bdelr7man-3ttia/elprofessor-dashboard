# -*- coding: utf-8 -*-
"""عقد «العقل» الجولة ٢ — منسوخ حرفيًا من docs/v2/brain2/SPEC.md §2.2. لا يُعدَّل إلا مع المواصفة."""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

KINDS = ('opinion', 'draft', 'note')
MODES = ('alone', 'ask', 'off')

class SourceDown(Exception):
    """gather could not read its source: the run records it and stores nothing (never an empty result)."""

@dataclass
class Target:
    ref: str                       # stable id, ≤200, e.g. 'pmsg:MSG_ab12', 'course:<id>', 'card:<v2Card id>'
    label: str                     # title the founder sees, ≤120
    facts: Dict[str, Any]          # the ONLY data the prompt may use; JSON, ≤4KB; hashed
    meta: Dict[str, Any] = field(default_factory=dict)  # apply-only (ids, emails); never sent to AI, never hashed

@dataclass
class ApplyResult:
    ok: bool
    error: str = ''                # Arabic, shown as is
    no_reply: bool = False
    copy_text: str = ''            # browser copies this after success
    info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Ctx:
    ns: dict                       # app.py globals()
    now: Any                       # aware UTC datetime
    actor: str                     # 'cron' | admin email

@dataclass(frozen=True)
class Producer:
    id: str
    section: str                   # dashboard section key that shows it
    kind: str                      # KINDS
    label: str                     # rules-screen title (Arabic)
    sentence: str                  # «عندما…» sentence (Arabic)
    lock_reason: str               # Arabic; '' when may_run_alone
    may_run_alone: bool
    default_mode: str
    per_run_cap: int
    gather: Callable[[Ctx], List[Target]]
    prompt: Callable[[Target], tuple]                    # -> (system_ar, user_ar)
    validate: Callable[[dict, Target], Optional[dict]]   # -> body {'text': str, ...} | None
    template: Optional[Callable[[Target], Optional[dict]]] = None
    apply: Optional[Callable[[Ctx, dict, Target], ApplyResult]] = None
    tag: str = ''                  # card tag (Arabic)
    approve_label: str = ''        # main button (Arabic)
    listed: bool = True            # False = hidden hook
    version: int = 1
