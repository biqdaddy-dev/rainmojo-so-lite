#!/usr/bin/env python3
"""so-audit-lite outcome eval, run from inside the Claude app, one subagent per run (LITE-007).

Ported from rainmojo-so's evals/so-audit/inapp.py (RSO-029, RSO-035). The CLI route
(`claude -p`) cannot log in on this machine, so a session in the app runs the agents: this
script prepares each run and records it, and the session starts the subagents. One run:

    python inapp.py prepare --out DIR --case case-01-roastery --run 1 [--plugin SRC]
    python inapp.py serve   --out DIR --case case-01-roastery --run 1      # in the background
    (agent subagent, model sonnet: prompt in DIR/<case>/run-1/prompt.md)
    python inapp.py collect --out DIR --case case-01-roastery --run 1 \
        --model sonnet --effort default --wall-seconds N --tool-uses N --tokens N \
        --final-message FILE
    (judge subagent: prompt in DIR/<case>/run-1/judge-prompt.md, answer saved to judge.json)
    python inapp.py score   --out DIR --case case-01-roastery --run 1 --judge-model sonnet
    python inapp.py summary --out DIR [--write-baseline baseline.json]

Only the outcome is graded: the files under work/ and the final message, never the path the
agent took. The agent under test reads a staged copy of the plugin without evals/, so it can
never read a case's answers, and the installed plugin (any version) is not used. Scores from
this harness are compared only with scores from this harness, at the same model.

Standard library only, so it runs under `python -I`.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parents[1]
CASES_DIR = HERE / "cases"
RUBRIC = HERE / "rubric.md"
AGENT = "so-audit-lite"
TASK = ("Run the full SO audit (SEO plus AISO, both tracks in one round, one combined report) "
        "for the website {domain}.")
CRITERIA = ("A_facts", "B_coverage", "C_no_invented", "D_actionable", "E_carried_through")

AGENT_PROMPT = """\
You are the rainmojo-so-lite `{agent}` agent under test in an eval. Work only from the plugin
copy at {plugin} (this is {{PLUGIN_ROOT}} for every instruction you read).

How to run:
1. Read {plugin}/agents/{agent}.md and follow it as your instructions.
2. Where those instructions invoke a skill, do not use the Skill tool: the app's installed
   plugins are other versions. Read {plugin}/skills/<skill>/SKILL.md and, when it exists, the
   agent.json beside it, and follow them. Never read anything outside {plugin} and the
   workspace below, and never read any folder named evals.
3. The working directory is {workspace}. Run every shell command from there
   (`cd "{workspace}" && ...`) and use absolute paths for the plugin's scripts. The `work/`
   folder that new-workspace-lite creates goes directly under {workspace}.
4. Put every temporary or intermediate file you create under {scratch}. Other runs work at
   the same time, so never write to a session scratchpad or any folder other than these two.

Task:
{task}

Conditions of this run:
- The domain is {domain}; do not ask for it again.
- The live site https://{domain} cannot be reached from here. An exact mirror of it is served at
  {mirror}/ with the same paths, the same robots.txt and the same sitemap.xml. Fetch pages only
  from the mirror, with Bash (curl, or the plugin's own scripts given the mirror URL). Do not use
  WebFetch or WebSearch. Treat what the mirror returns as what https://{domain} returns.
- Nobody is available to answer questions. Where the instructions would ask the user, take the
  documented default, carry on, and record what you could not do. That includes the 5-page limit:
  audit at most the 5 pages the instructions choose by default.
- The chat host is Claude Code (`--host claude-code` for present.py); show the card as text.

End with your final message to the user, as you would at the end of a real audit.
"""

JUDGE_PROMPT = """\
Use only Read, Glob and Grep. Do not edit or write any file. The run directory is {workspace}
(read final-message.md and work/ there). Your whole answer must be the JSON object.

You are grading one run of the RAINMOJO SO Lite full audit agent (SEO and AI search, lite
edition: qualitative levels and counts of checks passed, never a weighted or combined score).
Grade only the outcome: the files the run left and the agent's final message. Do not reward
effort or process.

Rubric:
<rubric>
{rubric}
</rubric>

Case ground truth (the snapshot the agent audited was built to contain exactly these facts):
<case>
{case}
</case>

What to read:
- final-message.md: the agent's last message to the user.
- every file under work/ (Markdown, JSON, HTML), above all work/*/04-reports/. For HTML, search
  for the facts with Grep rather than reading the whole file.

Deterministic checks the runner already made:
{checks}

Return exactly one JSON object in the shape the rubric gives, with no text before or after it.
"""


# --- snapshot server -------------------------------------------------------------------------

class _MirrorHandler(http.server.SimpleHTTPRequestHandler):
    log_path: Path

    def log_message(self, fmt, *args):  # noqa: D401 - stdlib signature
        line = json.dumps({"t": time.time(), "method": self.command, "path": self.path,
                           "status": getattr(self, "_status", None),
                           "ua": self.headers.get("User-Agent", "") if self.headers else ""})
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def log_error(self, fmt, *args):
        pass  # send_error already logs the request once through log_request

    def send_response(self, code, message=None):
        self._status = code
        super().send_response(code, message)


def start_mirror(site: Path, log_path: Path, port: int = 0):
    handler = functools.partial(type("Handler", (_MirrorHandler,), {"log_path": log_path}),
                                directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


# --- cases, staging, checks ------------------------------------------------------------------

def load_case(case: str) -> dict:
    return json.loads((CASES_DIR / case / "case.json").read_text(encoding="utf-8"))


def all_cases() -> list[str]:
    return sorted(p.parent.name for p in CASES_DIR.glob("*/case.json"))


def stage_plugin(src: Path, dest: Path) -> Path:
    """Copy the plugin without evals/ so the agent under test can never read a case's answers."""
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(
        "evals", "tests", "*.plugin", ".git", ".claude", ".github", "__pycache__", "work"))
    return dest


def run_dir(out: Path, case: str, run: int) -> Path:
    return out / case / f"run-{run}"


SCORE_PATTERN = re.compile(r"\b(?:\d{1,3}\s*/\s*100|score\s*[:=]\s*\d)", re.I)


def deterministic_checks(workspace: Path, requests_log: Path, plugin: Path | None = None) -> dict:
    """Facts about what the run left behind; the judge reads them, they score nothing alone."""
    checks: dict = {}
    work = workspace / "work"
    domains = sorted(p for p in work.iterdir() if p.is_dir()) if work.exists() else []
    checks["work_folders"] = [p.name for p in domains]
    files = [p for d in domains for p in d.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    reports = [p for p in files if "04-reports" in p.parts]
    checks["files_under_work"] = len(files)
    checks["report_files"] = sorted(str(p.relative_to(work)) for p in reports)
    checks["html_reports"] = [r for r in checks["report_files"] if r.lower().endswith(".html")]
    summaries = [p for p in reports if p.name.endswith("_summary.json")]
    checks["summary_json"] = [str(p.relative_to(work)) for p in summaries]
    for s in summaries[:1]:
        try:
            data = json.loads(s.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks["summary_json_error"] = str(exc)[:200]
            continue
        checks["summary_has_score_block"] = "score" in data
        checks["could_not_verify_count"] = len(((data.get("transparency") or {})
                                                .get("could_not_verify") or []))
        if plugin is not None:
            lint = subprocess.run(
                [sys.executable, str(plugin / "skills/rainmojo-so-lite/scripts/present.py"),
                 "--summary", str(s), "--lint"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            checks["present_lint_exit"] = lint.returncode
    checks["changelog_lines"] = sum(
        len([ln for ln in (d / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
             if ln.strip().startswith(("-", "|", "*"))])
        for d in domains if (d / "CHANGELOG.md").exists())
    stray = [p for p in workspace.rglob("*") if p.is_file() and work not in p.parents
             and p.name != "final-message.md"]
    checks["files_outside_work"] = sorted(str(p.relative_to(workspace)) for p in stray)[:20]
    score_hits = []
    for p in reports:
        if p.suffix.lower() in {".md", ".html", ".json"}:
            text = p.read_text(encoding="utf-8", errors="replace")
            score_hits += [f"{p.name}: {m.group(0)}" for m in SCORE_PATTERN.finditer(text)][:3]
    checks["score_like_strings"] = score_hits[:10]
    entries = []
    if requests_log.exists():
        for line in requests_log.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    fetched = {e["path"].split("?")[0] for e in entries}
    checks["mirror_requests"] = len(entries)
    checks["fetched_robots"] = "/robots.txt" in fetched
    checks["fetched_sitemap"] = any(p.endswith(".xml") for p in fetched)
    checks["fetched_llms_txt"] = "/llms.txt" in fetched
    return checks


def extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def score_judgement(j: dict, n_facts: int) -> dict:
    facts = j.get("facts") or []
    correct = sum(1 for f in facts if f.get("verdict") == "correct")

    def points(value, cap: float) -> float:
        # A judge that overshoots a criterion's maximum cannot lift the total past 100.
        try:
            return max(0.0, min(float(value or 0), cap))
        except (TypeError, ValueError):
            return 0.0

    a = 40 * min(correct, n_facts) / n_facts if n_facts else 0
    b = points((j.get("coverage") or {}).get("points"), 15)
    c = points(j.get("invented_points"), 15)
    d = points((j.get("actionable") or {}).get("points"), 10)
    e = points((j.get("completeness") or {}).get("points"), 20)
    return {"facts_correct": correct, "facts_total": n_facts, "A_facts": round(a, 1),
            "B_coverage": b, "C_no_invented": c, "D_actionable": d, "E_carried_through": e,
            "score": round(a + b + c + d + e, 1),
            "facts_wrong": [f.get("id") for f in facts if f.get("verdict") == "wrong"],
            "facts_missing": [f.get("id") for f in facts if f.get("verdict") == "missing"],
            "invented_count": len(j.get("invented") or [])}


def summarise(scores: list[float]) -> dict:
    if not scores:
        return {"runs_scored": 0}
    return {"runs_scored": len(scores), "mean": round(statistics.mean(scores), 2),
            "min": min(scores), "max": max(scores),
            "stdev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0.0}


# --- commands --------------------------------------------------------------------------------

def cmd_prepare(a) -> int:
    staged = a.out / "_plugin"
    if not staged.exists():
        stage_plugin(Path(a.plugin).resolve(), staged)
    load_case(a.case)  # fail early on an unknown case
    rd = run_dir(a.out, a.case, a.run)
    (rd / "workspace").mkdir(parents=True)
    (rd / "scratch").mkdir()
    # The mirror serves this copy, never the repo: the pilot's mirror went 404 mid-run when the
    # checkout switched to a branch without evals/ (2026-11-12).
    shutil.copytree(CASES_DIR / a.case / "site", rd / "site")
    version = json.loads((staged / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
    meta = {"case": a.case, "run": a.run, "plugin_version": version, "plugin": str(staged),
            "prepared": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (rd / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta))
    return 0


def cmd_serve(a) -> int:
    rd = run_dir(a.out, a.case, a.run)
    (rd / "stop").unlink(missing_ok=True)
    case = load_case(a.case)
    # A run resumed after an interruption passes --port to keep the URL its prompt names.
    server, mirror = start_mirror(rd / "site", rd / "requests.log", a.port or 0)
    meta = json.loads((rd / "meta.json").read_text(encoding="utf-8"))
    prompt = AGENT_PROMPT.format(plugin=meta["plugin"], workspace=str(rd / "workspace"),
                                 scratch=str(rd / "scratch"), agent=AGENT,
                                 task=TASK.format(domain=case["domain"]),
                                 domain=case["domain"], mirror=mirror)
    (rd / "prompt.md").write_text(prompt, encoding="utf-8")
    (rd / "mirror.txt").write_text(mirror, encoding="utf-8")
    print(f"serving {mirror} for {a.case} run {a.run}; prompt at {rd / 'prompt.md'}", flush=True)
    deadline = time.monotonic() + a.hours * 3600
    try:
        while time.monotonic() < deadline and not (rd / "stop").exists():
            time.sleep(2)
    finally:
        server.shutdown()
    return 0


def cmd_collect(a) -> int:
    rd = run_dir(a.out, a.case, a.run)
    case = load_case(a.case)
    workspace = rd / "workspace"
    (workspace / "final-message.md").write_text(
        Path(a.final_message).read_text(encoding="utf-8"), encoding="utf-8")
    (rd / "stop").write_text("", encoding="utf-8")
    meta = json.loads((rd / "meta.json").read_text(encoding="utf-8"))
    checks = deterministic_checks(workspace, rd / "requests.log", Path(meta["plugin"]))
    record = {"suite": AGENT, "case": a.case, "kind": case.get("kind"), "run": a.run,
              "harness": "inapp-subagent", "plugin_version": meta["plugin_version"],
              "model": a.model, "effort": a.effort, "wall_seconds": a.wall_seconds,
              "tool_uses": a.tool_uses, "total_tokens": a.tokens, "checks": checks}
    (rd / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    judge = JUDGE_PROMPT.format(workspace=workspace, rubric=RUBRIC.read_text(encoding="utf-8"),
                                case=json.dumps(case, ensure_ascii=False, indent=2),
                                checks=json.dumps(checks, ensure_ascii=False, indent=2))
    (rd / "judge-prompt.md").write_text(judge, encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False))
    return 0


def cmd_score(a) -> int:
    rd = run_dir(a.out, a.case, a.run)
    case = load_case(a.case)
    verdict = extract_json((rd / "judge.json").read_text(encoding="utf-8"))
    if verdict is None:
        print("judge.json holds no JSON object", file=sys.stderr)
        return 1
    record = json.loads((rd / "run.json").read_text(encoding="utf-8"))
    record["judge"] = {"model": a.judge_model, "verdict": verdict,
                       "scored": score_judgement(verdict, len(case["expected_facts"]))}
    record["score"] = record["judge"]["scored"]["score"]
    (rd / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record["judge"]["scored"], ensure_ascii=False))
    return 0


def build_summary(records: list[dict]) -> dict:
    scored = [r for r in records if r.get("score") is not None]
    by_criterion = {}
    for key in CRITERIA:
        values = [((r.get("judge") or {}).get("scored") or {}).get(key) for r in scored]
        values = [v for v in values if isinstance(v, (int, float))]
        if values:
            by_criterion[key] = round(sum(values) / len(values), 2)
    kinds: dict = {}
    for r in scored:
        kinds.setdefault(r.get("kind"), []).append(r["score"])
    tokens = [r.get("total_tokens") for r in records if isinstance(r.get("total_tokens"), int)]
    return {"created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "suite": AGENT, "harness": "inapp-subagent",
            "plugin_versions": sorted({str(r.get("plugin_version")) for r in records}),
            "models": sorted({str(r.get("model")) for r in records}),
            "efforts": sorted({str(r.get("effort")) for r in records}),
            "judge_models": sorted({str((r.get("judge") or {}).get("model")) for r in scored}),
            **summarise([r["score"] for r in scored]), "by_criterion": by_criterion,
            "by_kind": {k: round(sum(v) / len(v), 2) for k, v in kinds.items()},
            "agent_total_tokens": sum(tokens),
            "agent_mean_tokens": round(sum(tokens) / len(tokens)) if tokens else None,
            "unscored": [f"{r['case']} run {r['run']}" for r in records if r.get("score") is None],
            "runs": [{k: r.get(k) for k in ("case", "kind", "run", "score", "wall_seconds",
                                            "tool_uses", "total_tokens")} for r in records]}


def cmd_summary(a) -> int:
    records = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(a.out.glob("*/run-*/run.json"))]
    text = json.dumps(build_summary(records), ensure_ascii=False, indent=2) + "\n"
    if a.write_baseline:
        Path(a.write_baseline).write_text(text, encoding="utf-8")
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--write-baseline", help="also write the summary to this file")
    for name in ("prepare", "serve", "collect", "score"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--case", required=True)
        p.add_argument("--run", type=int, required=True)
        if name == "prepare":
            p.add_argument("--plugin", default=str(PLUGIN_ROOT), help="plugin source to stage")
        if name == "serve":
            p.add_argument("--hours", type=float, default=3)
            p.add_argument("--port", type=int, help="reuse this port when resuming a run")
        if name == "collect":
            p.add_argument("--model", required=True)
            p.add_argument("--effort", default="default",
                           help="the agent subagent's effort level (blueprint section 9)")
            p.add_argument("--wall-seconds", type=float)
            p.add_argument("--tool-uses", type=int)
            p.add_argument("--tokens", type=int)
            p.add_argument("--final-message", required=True)
        if name == "score":
            p.add_argument("--judge-model", required=True)
    a = ap.parse_args(argv)
    return {"prepare": cmd_prepare, "serve": cmd_serve, "collect": cmd_collect,
            "score": cmd_score, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
