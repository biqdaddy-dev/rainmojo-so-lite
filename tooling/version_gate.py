#!/usr/bin/env python3
"""The plugin version lives in one place: .claude-plugin/plugin.json (LITE-008, blueprint RS-6).

Ported from rainmojo-so's version_gate.py (RSO-017). Checks, exit 1 on any finding:
1. every other manifest (root Antigravity plugin.json, Gemini, Codex, Copilot, Cursor and the
   marketplace entry) carries the same name and version. The root plugin.json read 2.2.0 from
   2.3.0 to 2.8.3 because nothing compared it;
2. no SKILL.md or agent frontmatter carries a version of its own;
3. README.md names no plugin version: it points to CHANGELOG.md instead, so it cannot go stale;
4. the newest numbered CHANGELOG.md section is that version, so a bump never ships without notes
   (an `## Unreleased` section above it is allowed).

Standard library only. Run from anywhere: python -I tooling/version_gate.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ".claude-plugin/plugin.json"
COPIES = [
    "plugin.json",
    "gemini-extension.json",
    ".codex-plugin/plugin.json",
    "platforms/codex/.codex-plugin/plugin.json",
    "platforms/copilot/plugin.json",
    "platforms/cursor/.cursor-plugin/plugin.json",
    "platforms/gemini/gemini-extension.json",
]
MARKETPLACE = ".claude-plugin/marketplace.json"
# A version key anywhere in the YAML frontmatter, top level or nested under metadata:.
FRONTMATTER_VERSION = re.compile(r"^\s*version\s*:", re.M)
README_VERSION = re.compile(r"(?:\bVersion|เวอร์ชัน)\s+v?\d+\.\d+\.\d+")


def frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def check(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    source = json.loads((root / SOURCE).read_text(encoding="utf-8"))
    name, version = source.get("name"), source.get("version")
    for rel in COPIES:
        path = root / rel
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != version:
            problems.append(f"{rel}: version {data.get('version')} != {SOURCE} {version}")
        if data.get("name") != name:
            problems.append(f"{rel}: name {data.get('name')} != {SOURCE} {name}")
    market = root / MARKETPLACE
    if market.exists():
        entries = [p for p in json.loads(market.read_text(encoding="utf-8")).get("plugins", [])
                   if p.get("name") == name]
        if not entries:
            problems.append(f"{MARKETPLACE}: no plugins[] entry named {name}")
        for entry in entries:
            if entry.get("version") != version:
                problems.append(f"{MARKETPLACE}: version {entry.get('version')} != {SOURCE} {version}")
    for path in sorted([*root.glob("skills/*/SKILL.md"), *root.glob("agents/*.md")]):
        if FRONTMATTER_VERSION.search(frontmatter(path.read_text(encoding="utf-8"))):
            problems.append(f"{path.relative_to(root).as_posix()}: frontmatter carries a version; "
                            f"the plugin version comes from {SOURCE} only")
    readme = root / "README.md"
    if readme.exists():
        for match in README_VERSION.finditer(readme.read_text(encoding="utf-8")):
            problems.append(f"README.md: names a version ({match.group(0)}); point to CHANGELOG.md")
    changelog = root / "CHANGELOG.md"
    if changelog.exists():
        heading = re.search(r"^## \[?v?([0-9][^\]\s]*)", changelog.read_text(encoding="utf-8"), re.M)
        if not heading or heading.group(1) != version:
            found = heading.group(1) if heading else "none"
            problems.append(f"CHANGELOG.md: newest section is {found}, {SOURCE} is {version}")
    return problems


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    problems = check()
    for line in problems:
        print(line)
    if problems:
        print(f"version gate: {len(problems)} finding(s)")
        return 1
    print("version gate: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
