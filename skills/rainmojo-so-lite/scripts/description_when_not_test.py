#!/usr/bin/env python3
"""Every skill description says when not to use it, names the other skill, and fits.

Rule (2026-11-05, LITE-004): the dispatch plan of 2026-11-02, approved by the owner on
2026-11-05, asks every skill description to say what it does, when to use it and when
not, naming the other skill, in words the team types in Thai and English. 41 of 43
lite descriptions had no when-not clause, so the model could not tell siblings such as
technical-audit-lite and aiso-crawlers-lite apart. That dispatch is newer than the
2026-10-31 decision recorded in agentlint SK-WHEN-NOT (when-not on colliding pairs only).

Checks, per skills/*/SKILL.md:
  W1  the description has a when-not clause agentlint recognises
      (`Not for`, `Do not use`, `ไม่ใช้เมื่อ`, `ไม่ใช้สำหรับ`, `ไม่ใช่สำหรับ`)
  W2  after that clause it names another skill of this plugin that exists
  W3  the description is at most 600 characters, because the Daddy Dock catalog
      shows 600 (agentlint SK-DESC allows 1,024; this is the tighter limit)

No dependencies: the frontmatter is read with a small parser for the two forms the
plugin uses (one quoted line, or a `>` folded block).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WHEN_NOT = re.compile(r"\bnot for\b|\bdo not use\b|ไม่ใช้เมื่อ|ไม่ใช้สำหรับ|ไม่ใช่สำหรับ", re.I)
LIMIT = 600


def description(text: str) -> tuple[str, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter")
    fm = text[4:text.index("\n---", 4)].split("\n")
    name = next(l.split(":", 1)[1].strip() for l in fm if l.startswith("name:"))
    for i, line in enumerate(fm):
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value in (">", "|", ">-", "|-"):
            body = []
            for nxt in fm[i + 1:]:
                if not nxt.startswith(" "):
                    break
                body.append(nxt.strip())
            return name, " ".join(body)
        if value.startswith('"') and value.endswith('"'):
            return name, value[1:-1].replace('\\"', '"')
        return name, value
    raise ValueError("no description")


def main() -> int:
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    names = {p.parent.name for p in skills}
    failures = []
    for path in skills:
        name, desc = description(path.read_text(encoding="utf-8"))
        m = WHEN_NOT.search(desc)
        if not m:
            failures.append(f"W1 {name}: no when-not clause")
            continue
        named = {x for x in re.findall(r"[a-z0-9][a-z0-9-]*-lite", desc[m.start():])} - {name}
        if not named & names:
            failures.append(f"W2 {name}: the when-not clause names no other skill of this plugin")
        if named - names:
            failures.append(f"W2 {name}: names a skill that does not exist: {sorted(named - names)}")
        if len(desc) > LIMIT:
            failures.append(f"W3 {name}: description is {len(desc)} characters (limit {LIMIT})")
    for f in failures:
        print(f)
    if failures:
        print(f"DESCRIPTION_WHEN_NOT_TEST_FAIL {len(failures)} of {len(skills)} skills")
        return 1
    print(f"DESCRIPTION_WHEN_NOT_TEST_OK skills={len(skills)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
