#!/usr/bin/env python3
"""5-request invocation test: does a fresh session load the skill it should, and only that one?

Each distinct request in cases.json runs once in a fresh headless Claude Code session
with only this plugin loaded (`--plugin-dir <repo> --setting-sources project`, run from
an empty folder), tools that act on the world disabled, and two turns. The first skill the
session invokes is the result. A request in a skill's "load" list passes when that skill
is the one invoked; a request in its "not" list passes when that skill is not invoked.

    python tooling/invocation-test/run.py --out results.json [--model sonnet] [--only NAME ...]

Needs a logged-in `claude` CLI (`claude /login`). Exit 1 when any check fails.
Written 2026-11-05 for LITE-004 (dispatch plan rule: after a description change, run
3 should-load and 2 should-not requests in new sessions). Run it for every skill whose
description a change touches; add cases to cases.json for a skill that has none.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREFIX = "rainmojo-so-lite:"
BLOCK = "WebFetch Bash WebSearch Write Edit Agent NotebookEdit"


# The request goes in on stdin, not argv: on Windows the `claude` shim runs through
# cmd.exe, which would re-encode Thai text in an argument.
def first_skill(request: str, model: str, cwd: str) -> tuple[str | None, str]:
    cmd = ["claude", "-p", "--plugin-dir", str(REPO), "--setting-sources", "project",
           "--output-format", "stream-json", "--verbose", "--max-turns", "2",
           "--model", model, "--disallowed-tools", BLOCK]
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          input=request, timeout=300, shell=sys.platform == "win32")
    note = ""
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "assistant":
            continue
        for part in event["message"].get("content", []):
            if part.get("type") == "tool_use" and part.get("name") == "Skill":
                name = str(part.get("input", {}).get("skill", ""))
                return (name[len(PREFIX):] if name.startswith(PREFIX) else name), note
            if part.get("type") == "text" and not note:
                note = part["text"][:160]
    return None, note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["skills"]
    if args.only:
        cases = {k: v for k, v in cases.items() if k in args.only}
    requests = sorted({r for c in cases.values() for r in c["load"] + c["not"]})
    seen: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as cwd:
        for i, req in enumerate(requests, 1):
            skill, note = first_skill(req, args.model, cwd)
            seen[req] = {"skill": skill, "note": note}
            print(f"[{i}/{len(requests)}] {skill or '-':32} {req}", flush=True)
    if any(v["note"].startswith(("Failed to authenticate", "Not logged in")) for v in seen.values()):
        print("INVOCATION_TEST_BLOCKED: the claude CLI is not logged in (run claude /login)")
        return 2
    rows, failed = [], 0
    for name, c in cases.items():
        for kind in ("load", "not"):
            for req in c[kind]:
                got = seen[req]["skill"]
                ok = (got == name) if kind == "load" else (got != name)
                failed += not ok
                rows.append({"skill": name, "kind": kind, "request": req, "invoked": got, "pass": ok})
    Path(args.out).write_text(json.dumps({"model": args.model, "rows": rows}, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    for name in cases:
        mine = [r for r in rows if r["skill"] == name]
        print(f"{name:32} {sum(r['pass'] for r in mine)}/{len(mine)}")
    print(f"INVOCATION_TEST {'OK' if not failed else 'FAIL'} checks={len(rows)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
