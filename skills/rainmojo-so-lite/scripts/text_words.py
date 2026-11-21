#!/usr/bin/env python3
"""
text_words.py - count words in text that may be Thai (LITE-015).

Thai has no spaces between words, so str.split() returns a whole Thai sentence as one
"word". scope_gate.py needs a fair count to tell a near-empty site from a short Thai one.

    count_words(text)   str.split() tokens; a token holding Thai script is segmented with
                        pythainlp (newmm) when it is installed, and otherwise counted as
                        ceil(Thai characters / 5)

Why the estimate: lite does not require pythainlp, and one word per Thai run made two real
Thai sites in the so-audit-lite eval look empty (case-06 33 words, case-10 48, against 78 and
85 with pythainlp; the gate cut is 50). One word per 5 Thai characters gives 96, 192 and 89 on
the three Thai cases against 78, 181 and 85: close, and on the side of auditing the site.
"""

import math
import re
import sys

THAI_RE = re.compile(r"[฀-๿]")
_ALNUM_RE = re.compile(r"[^\W_]", re.U)
CHARS_PER_THAI_WORD = 5

_tokenize = None  # resolved lazily: a pythainlp callable, or False when unavailable


def _load_tokenizer():
    global _tokenize
    if _tokenize is None:
        try:
            from pythainlp.tokenize import word_tokenize  # type: ignore
            _tokenize = lambda run: word_tokenize(run, engine="newmm", keep_whitespace=False)  # noqa: E731
        except Exception:  # ImportError, or a broken install: never take the caller down
            _tokenize = False
    return _tokenize


def thai_available():
    """True when pythainlp can segment Thai."""
    return bool(_load_tokenizer())


def _thai_words(token):
    tok = _load_tokenizer()
    if tok:
        try:
            parts = [p for p in tok(token) if _ALNUM_RE.search(p)]
            if parts:
                return len(parts)
        except Exception:
            pass
    return max(1, math.ceil(len(THAI_RE.findall(token)) / CHARS_PER_THAI_WORD))


def count_words(text):
    total = 0
    for t in (text or "").split():
        total += _thai_words(t) if THAI_RE.search(t) else 1
    return total


def self_test():
    global _tokenize
    en = "A laser clinic is a medical facility, with 12 doctors and 3 branches."
    th = "คลินิกเลเซอร์เป็นสถานพยาบาล"
    assert count_words(en) == len(en.split())
    assert count_words("") == 0
    saved = _tokenize
    _tokenize = False  # the estimate path, as on a machine without pythainlp
    assert count_words(th) == math.ceil(len(th) / CHARS_PER_THAI_WORD), count_words(th)
    assert count_words(th + " SEO 2026") == count_words(th) + 2
    _tokenize = saved
    n = count_words(th)
    assert n >= 4, n
    print("SELF-TEST PASS: text_words (pythainlp=%s, thai sample %d words)" % (thai_available(), n))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(self_test())
