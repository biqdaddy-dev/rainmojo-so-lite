#!/usr/bin/env python3
"""What every session loads from this plugin, measured, with a ceiling that only goes down (LITE-014).

Blueprint DP-023 C11: the context a plugin adds to every session must be small and measured. For
lite that is the skill listing (name plus description of each of the 43 skills) and the agent
descriptions; there is no SessionStart hook. The count follows agentlint's `context` command:
characters of `name: description`, at about 4 characters a token.

    python -I tooling/context_budget.py            # check against tooling/context-budget.json
    python -I tooling/context_budget.py --update   # lower the ceiling to today's total

A change that grows the total fails. Lower the ceiling with --update in the change that shrinks it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET = Path(__file__).resolve().parent / "context-budget.json"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    head = text[3:text.find("\n---", 3)]
    out: dict = {}
    key = None
    for line in head.splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            out[key] = "" if value in (">", ">-", "|", "|-") else value.strip('"')
        elif key and line.startswith((" ", "\t")):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def measure(root: Path = ROOT) -> dict:
    skills = agents = 0
    for path in sorted(root.glob("skills/*/SKILL.md")):
        fm = frontmatter(path)
        skills += len(f"{fm.get('name', path.parent.name)}: {fm.get('description', '')}")
    for path in sorted(root.glob("agents/*.md")):
        fm = frontmatter(path)
        agents += len(f"{fm.get('name', path.stem)}: {fm.get('description', '')}")
    return {"skill_listing": skills, "agent_descriptions": agents, "total": skills + agents}


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    now = measure()
    if "--update" in argv:
        BUDGET.write_text(json.dumps({"ceiling": now["total"], **now}, indent=2) + "\n", encoding="utf-8")
        print(f"context budget: ceiling set to {now['total']}")
        return 0
    ceiling = json.loads(BUDGET.read_text(encoding="utf-8"))["ceiling"]
    print(f"context budget: {now['total']} characters every session "
          f"(skills {now['skill_listing']}, agents {now['agent_descriptions']}), ceiling {ceiling}")
    if now["total"] > ceiling:
        print("context budget: grew past the ceiling; shorten a description or justify a new ceiling")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
