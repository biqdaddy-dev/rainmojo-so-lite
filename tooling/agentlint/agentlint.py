#!/usr/bin/env python3
"""agentlint: check and fix agent plugins, skills and subagents against one standard.

Standard library only (Python 3.10+). The RULES table below is the standard;
reference/standard.md is generated from it with `agentlint.py rules --markdown`.

    python agentlint.py check PATH [--json] [--profile portable|claude-ai] [--ci]
    python agentlint.py fix PATH [--apply] [--only RULE,RULE]
    python agentlint.py rules [--markdown]

check exits 0 when clean, 1 when it finds problems, 2 on bad usage. Warnings
(level `warn`) are printed but never change the exit code. With --ci only the
hard rules in CI_FAIL fail; every other finding is printed as a warning.
fix prints a diff and changes nothing unless --apply is given; --apply first
copies every file it touches to PATH/_backups/agentlint-<timestamp>/.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

STANDARD_VERSION = "1.1.0"

SOURCES = {
    "BP": "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices",
    "AS": "https://agentskills.io/specification",
    "CS": "https://code.claude.com/docs/en/skills",
    "MM": "https://code.claude.com/docs/en/memory",
    "SA": "https://code.claude.com/docs/en/sub-agents",
    "HK": "https://code.claude.com/docs/en/hooks",
    "PR": "https://code.claude.com/docs/en/plugins-reference",
    "PE": "https://code.claude.com/docs/en/plugin-evals",
    "XH": "Host docs: Codex, Cursor, VS Code/Copilot, Gemini CLI, Antigravity (checked 2026-10-08)",
    "DD": "Daddy Dock catalog and release contract",
    "PO": "plugin-optimizer field experience",
}


@dataclass(frozen=True)
class Rule:
    id: str
    area: str
    kind: str  # "check" (script enforces) or "review" (a person or agent judges)
    fixable: bool
    title: str
    source: str
    #: "error" fails `check`; "warn" is reported but never fails it.
    level: str = "error"
    #: Date and reason, for every rule added after a mistake (policy since 2026-10-31; older rules get it when edited).
    added: str = ""


RULES = [
    # Skill entry file and frontmatter
    Rule("SKILL-FILE", "Skill", "check", True, "The skill's entry file is named exactly `SKILL.md`.", "AS"),
    Rule("SK-FM", "Skill", "check", True, "Frontmatter opens with `---` on line 1 (no byte-order mark) and parses.", "CS"),
    Rule("SK-NAME", "Skill", "check", True, "`name`: 1-64 chars of `a-z`, `0-9`, `-`; no leading, trailing or double hyphen.", "AS"),
    Rule("SK-NAME-DIR", "Skill", "check", True, "`name` equals the skill's folder name.", "AS"),
    Rule("SK-RESERVED", "Skill", "check", False, "`name` does not contain the reserved words `anthropic` or `claude`.", "BP"),
    Rule("SK-DESC", "Skill", "check", False, "`description` is present and 1-1024 characters.", "AS"),
    Rule("SK-DESC-XML", "Skill", "check", False, "`description` contains no XML or HTML tags.", "BP"),
    Rule("SK-DESC-POV", "Skill", "check", False, "`description` is third person: no I, we, you or your (Thai: ผม, ฉัน, เรา, คุณ).", "BP"),
    Rule("SK-DESC-WHEN", "Skill", "check", False, "`description` says when to use the skill (for example `Use when ...`).", "BP"),
    Rule("SK-WHEN-NOT", "Skill", "check", False, "Two skills (or two agents) whose descriptions share trigger words: at least one says when not to use it and names the other (`Not for ...`, `Do not use ...`, `ไม่ใช้เมื่อ ...`, `ไม่ใช่สำหรับ ...`).", "PO", "warn",
         "2026-10-31, owner decision: when-not text only on colliding pairs such as `seo-audit` and `so-audit`, not on every skill, because descriptions load every session and the Daddy Dock catalog shows 600 characters"),
    Rule("SK-FIELDS", "Skill", "check", True, "Frontmatter uses only portable fields: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`, plus `disable-model-invocation`, `user-invocable`, `paths`, `argument-hint`. Host-only settings (hooks, context, model, effort) go in the host adapter.", "AS"),
    Rule("SK-META", "Skill", "check", True, "`metadata` maps strings to strings; `compatibility` is at most 500 chars; `license` and `allowed-tools` are single strings.", "AS"),
    # Skill body and bundled files
    Rule("SB-LINES", "Skill", "check", False, "`SKILL.md` body is at most 500 lines; move detail into reference files.", "BP"),
    Rule("SB-LINK", "Skill", "check", False, "Every relative link in the skill resolves to a file.", "BP"),
    Rule("SB-INSIDE", "Skill", "check", False, "Links stay inside the plugin, or inside the skills folder for skills outside a plugin; under `--profile claude-ai`, where each skill uploads alone, inside the skill folder.", "AS"),
    Rule("SB-DEPTH", "Skill", "check", True, "Every bundled Markdown file that is linked anywhere is linked directly from `SKILL.md` (one level deep).", "BP"),
    Rule("SB-TOC", "Skill", "check", True, "Bundled Markdown files longer than 100 lines start with a `## Contents` list.", "BP"),
    Rule("SB-SLASH", "Skill", "check", True, "File paths use forward slashes.", "BP"),
    Rule("SC-DEPS", "Skill", "check", False, "Every third-party package a bundled script imports is named in `SKILL.md` with how to install it.", "BP"),
    Rule("FL-EMPTY", "Files", "check", False, "No empty files.", "PO"),
    Rule("FL-JSON", "Files", "check", False, "Every `.json` file parses.", "PO"),
    # Instruction files
    Rule("IF-LINES", "Instructions", "check", False, "`CLAUDE.md`, `AGENTS.md`, `CODEX.md` and `GEMINI.md` are at most 200 lines; move the rest into `.claude/rules/` or linked files.", "MM", "warn",
         "2026-10-31, owner decision: instruction files load in full every session; oversize ones are split into `.claude/rules/`"),
    # Subagents
    Rule("AG-FM", "Agent", "check", False, "Agent files have frontmatter with `name` and `description`; `name` uses `a-z`, `0-9`, `-` and has no `:`.", "SA"),
    Rule("AG-FIELDS", "Agent", "check", False, "Agent frontmatter uses known camelCase fields only; plugin agents do not set `hooks`, `mcpServers`, `permissionMode` or `initialPrompt` (hosts ignore them).", "SA"),
    Rule("AG-MODEL", "Agent", "check", False, "`model` is `inherit`, `haiku`, `sonnet`, `opus`, `fable` or a full `claude-...` model ID.", "SA"),
    Rule("AG-BODY", "Agent", "check", False, "Agent prompt body is at most 30,000 characters.", "XH"),
    # Plugin packaging
    Rule("PL-MANIFEST", "Plugin", "check", False, "`.claude-plugin/plugin.json` has a kebab-case `name`, a semver `version`, a `description`, `author.name`, an `http(s)` `homepage` if set, and string `repository`, `license` and `displayName` and a string list of `keywords` (a wrong type makes Claude Code skip the plugin).", "PR"),
    Rule("PL-KEYS", "Plugin", "check", False, "`.claude-plugin/plugin.json` uses only documented top-level fields (`monitors` and `themes` go under `experimental`).", "PR"),
    Rule("PL-PATHS", "Plugin", "check", False, "Component paths in the manifest start with `./`, stay inside the plugin, exist, list `.md` files for `agents`, and `hooks` does not list `hooks/hooks.json` (it always loads, so its hooks would run twice).", "PR"),
    Rule("PL-VERSION", "Plugin", "check", False, "Every manifest of the plugin (Claude, Codex, Agent Plugins, Gemini, marketplace entry) carries the same name and version.", "XH"),
    Rule("PL-HOOKS", "Plugin", "check", False, "Hook files under `hooks/` parse and wrap their events in a top-level `hooks` key.", "PR"),
    Rule("PL-NAMES", "Plugin", "check", False, "No skill and command in one plugin share a name (both become `/plugin:name`).", "CS"),
    # Daddy Dock (only where daddydock.json exists)
    Rule("DD-CONFIG", "Daddy Dock", "check", False, "`daddydock.json` parses, `license_gate` is `free` or `required`, and a required gate names its `product`.", "DD"),
    Rule("DD-DESC", "Daddy Dock", "check", False, "Skill and agent descriptions are at most 600 characters, so the catalog shows them whole.", "DD"),
    Rule("DD-TH", "Daddy Dock", "check", False, "Every key in `skills_th` and `agents_th` names an existing skill or agent.", "DD"),
    Rule("DD-GATE", "Daddy Dock", "check", False, "A `required` gate has the gate block in every skill and agent plus the `activate` skill and hook; a `free` plugin has none of them.", "DD"),
    # Review rules: a person or agent judges these; the script cannot.
    Rule("RV-CONCISE", "Writing", "review", False, "Only add what the model does not already know (house data, prices, rules, schemas); cut general explanations.", "BP"),
    Rule("RV-TOP", "Writing", "review", False, "Put the most important instructions near the top of `SKILL.md`: after compaction a host may keep only the start of a skill.", "CS"),
    Rule("RV-STANDING", "Writing", "review", False, "Write standing instructions (\"run the tests after every edit\"); hosts do not re-read `SKILL.md` on later turns.", "CS"),
    Rule("RV-TERMS", "Writing", "review", False, "Use one term per concept throughout.", "BP"),
    Rule("RV-TIME", "Writing", "review", False, "No time-sensitive statements; keep legacy material in an `Old patterns` section.", "BP"),
    Rule("RV-DEFAULT", "Writing", "review", False, "Give one default approach with an escape hatch, not a menu of options.", "BP"),
    Rule("RV-NAMES", "Writing", "review", False, "Name skills by activity (`processing-pdfs`) and files by content (`form_validation_rules.md`); avoid `helper`, `utils`, `doc2.md`.", "BP"),
    Rule("RV-FREEDOM", "Workflow", "review", False, "Match freedom to fragility: prose heuristics for open tasks, a template for preferred patterns, an exact script for fragile steps.", "BP"),
    Rule("RV-CHECKLIST", "Workflow", "review", False, "Multi-step workflows give a copyable checklist and say which step to return to when a check fails.", "BP"),
    Rule("RV-LOOP", "Workflow", "review", False, "Quality-critical work runs validate, fix, validate again, and proceeds only when it passes.", "BP"),
    Rule("RV-PATTERNS", "Workflow", "review", False, "Templates state how strict they are; style-dependent output shows input/output examples; branching tasks use a conditional workflow.", "BP"),
    Rule("RV-PLAN", "Workflow", "review", False, "Batch or destructive work writes a plan file, validates it with a script, then executes and verifies.", "BP"),
    Rule("RV-SCRIPTS", "Scripts", "review", False, "Scripts handle their own errors, explain every constant, and the skill says whether to run or read each script.", "BP"),
    Rule("RV-MCP", "Scripts", "review", False, "Name MCP tools fully qualified (`Server:tool`).", "BP"),
    Rule("RV-RUNTIME", "Scripts", "review", False, "Runtime differs by host: APIs may have no network or installs; never install packages globally.", "BP"),
    Rule("RV-HOOKS", "Safety", "review", False, "A rule that must hold every time is enforced by a hook for every host the plugin ships to, not by skill text alone.", "CS"),
    Rule("RV-SIDE-EFFECTS", "Safety", "review", False, "Skills with side effects (deploy, send, publish, delete) set `disable-model-invocation: true`.", "CS"),
    Rule("RV-TOOLS", "Safety", "review", False, "Grant agents only the tools they need; `allowed-tools` pre-approves, it never restricts.", "SA"),
    Rule("RV-EVALS", "Testing", "review", False, "Each skill has at least three eval cases, run with the same pass bar on every model and host it ships to.", "BP"),
]
RULE_BY_ID = {r.id: r for r in RULES}
#: `check --ci` fails only on these; every other finding is a warning there (owner decision 2026-10-31).
CI_FAIL = ("SK-NAME-DIR", "SK-DESC", "SB-LINES")

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "_backups", ".tmp", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
#: `platforms/` directly under a plugin root holds agentpack overlays: partial by design, checked as assembled packages.
OVERLAY_DIR = "platforms"
PLACEHOLDER_FILES = {".gitkeep", ".keep", "__init__.py", "py.typed"}
#: Quoted user phrases and code spans are trigger examples, not the skill's own voice.
QUOTED_RE = re.compile(r"\"[^\"]*\"|“[^”]*”|‘[^’]*’|«[^»]*»|「[^」]*」|`[^`]*`|(?<![\w'])'(?=[^\W\d_])[^'\n]{0,80}?(?<=\S)'(?![\w'])")
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?!-))*$")
PORTABLE_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
CROSS_HOST_FIELDS = {"disable-model-invocation", "user-invocable", "paths", "argument-hint"}
MOVABLE_TO_METADATA = {"version", "author", "tags", "category", "keywords", "homepage", "repository", "updated", "last_updated"}
AGENT_FIELDS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns", "skills",
    "mcpServers", "hooks", "memory", "background", "effort", "isolation", "color", "initialPrompt",
    "omitClaudeMd", "experimental",
}
PLUGIN_AGENT_IGNORED = {"hooks", "mcpServers", "permissionMode", "initialPrompt"}
MODEL_RE = re.compile(r"^(inherit|haiku|sonnet|opus|fable|claude-[a-z0-9.\-]+)(\[1m\])?$")
POV_ANY_CASE = re.compile(
    r"\b(me|my|mine|we|we're|we'll|we've|our|ours|you|your|yours|you're|you'll|you've)\b"
    r"|ผม(?!ร่วง)|ฉัน|(?<!ไพ)เรา(?!เตอร์|ท์|ะ)|คุณ(?!ภาพ|สมบัติ|ค่า|ลักษณะ|ประโยชน์|วุฒิ|ธรรม)",
    re.I,
)
POV_CASED = re.compile(
    r"(?<!Type )(?<!Phase )(?<!Part )(?<!Class )(?<!Level )(?<!Stage )(?<!Tier )(?<!Grade )(?<!Chapter )"
    r"(?<!Volume )(?<!Section )(?<!War )(?<!Mark )(?<![/\w])(I|I'm|I'll|I've|I'd|us)(?![/\w'])"
)
WHEN_RE = re.compile(
    r"\buse[sd]?\b[^.]{0,40}\b(when|whenever|for|if|after|before|during|to)\b|\bwhen (the )?(user|asked|working|you)\b|"
    r"\binvoke[sd]?\b[^.]{0,20}\bwhen\b|\btrigger(s|ed)?\b|ใช้เมื่อ|ใช้ตอน|ใช้สำหรับ|ใช้ใน|เมื่อผู้ใช้",
    re.I,
)
XML_RE = re.compile(r"<\s*/?\s*[A-Za-z][\w:-]*(\s[^<>]*)?/?\s*>")
#: Inline links and images: [text](target "title") and [text](<target with spaces>).
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\s*\)")
#: Reference definitions: [label]: target
REF_DEF_RE = re.compile(
    r"^[ ]{0,3}\[(?!\^)[^\]\n]+\]:[ \t]*(?:<([^>\n]+)>|(\S+))[ \t]*(?:\"[^\"\n]*\"|'[^'\n]*'|\([^)\n]*\))?[ \t]*$",
    re.M,
)
DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
PATH_BACKSLASH_RE = re.compile(r"(?<![\\\w])((?:\.{1,2}|[\w.-]+)(?:\\[\w.-]+)+\.(?:md|py|js|mjs|cjs|ts|json|sh|ps1|txt|ya?ml|csv|html|toml))\b")
TOC_RE = re.compile(r"^#{1,6}\s*(contents|table of contents|toc|สารบัญ)\s*$", re.I)
GATE_MARKER = "<!-- DADDYDOCK_LICENSE_GATE_V1 -->"
PIP_NAMES = {
    "bs4": "beautifulsoup4", "yaml": "pyyaml", "PIL": "pillow", "cv2": "opencv-python", "sklearn": "scikit-learn",
    "dateutil": "python-dateutil", "docx": "python-docx", "pptx": "python-pptx", "dotenv": "python-dotenv",
    "fitz": "pymupdf", "googleapiclient": "google-api-python-client", "jwt": "pyjwt", "Crypto": "pycryptodome",
}
# namespace packages: `import google.cloud.bigquery` comes from a `google-*` distribution, never from `google`
NAMESPACE_PIP = {"google": "google-cloud-bigquery", "azure": "azure-storage-blob"}
NODE_BUILTINS = {
    "assert", "buffer", "child_process", "cluster", "crypto", "dgram", "dns", "events", "fs", "fs/promises", "http",
    "http2", "https", "net", "os", "path", "perf_hooks", "process", "querystring", "readline", "stream", "string_decoder",
    "timers", "tls", "tty", "url", "util", "v8", "vm", "worker_threads", "zlib",
}


# ---------------------------------------------------------------------------
# Small YAML subset for frontmatter: scalars, quoted strings, block scalars,
# lists and one level of mapping. Anything deeper is kept as raw text.
# ---------------------------------------------------------------------------
@dataclass
class FMKey:
    key: str
    start: int  # index of the key line within the frontmatter lines
    end: int  # exclusive
    value: object


@dataclass
class Doc:
    path: Path
    text: str  # with "\n" line endings, BOM removed
    eol: str
    bom: bool
    fm_ok: bool
    fm_error: str
    fm_lines: list[str]
    keys: list[FMKey]
    body: str
    body_start: int  # line number (0-based) where the body starts in text
    utf8: bool = True

    def get(self, key, default=None):
        for k in self.keys:
            if k.key == key:
                return k.value
        return default

    def has(self, key):
        return any(k.key == key for k in self.keys)


def _unquote(s: str) -> str:
    """A YAML scalar's text: quotes removed, escapes decoded, trailing comment dropped."""
    s = s.strip()
    if s[:1] == '"':
        m = re.match(r'"((?:[^"\\]|\\.)*)"\s*(?:#.*)?$', s, re.S)
        if m:
            try:
                return json.loads('"' + m.group(1).replace("\n", "\\n") + '"')
            except ValueError:
                return m.group(1)
    if s[:1] == "'":
        m = re.match(r"'((?:[^']|'')*)'\s*(?:#.*)?$", s, re.S)
        if m:
            return m.group(1).replace("''", "'")
    if " #" in s:
        s = s.split(" #", 1)[0].rstrip()
    return s


def _scalar(s: str):
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_unquote(x) for x in inner.split(",")] if inner else []
    if s.startswith("{") and s.endswith("}"):
        inner = s[1:-1].strip()
        out = {}
        for part in inner.split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                out[_unquote(k)] = _unquote(v)
        return out
    if s and s[0] not in "\"'":
        plain = s.split(" #", 1)[0].strip()
        if re.fullmatch(r"[-+]?\d+", plain):
            return int(plain)
        if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+)([eE][-+]?\d+)?", plain):
            return float(plain)
        if plain.lower() in ("true", "false", "yes", "no", "on", "off"):
            return plain.lower() in ("true", "yes", "on")
        if plain.lower() in ("null", "~"):
            return None
    return _unquote(s)


def _block_value(head: str, rest: list[str]):
    """Interpret the value of one top-level key from its head text and indented lines."""
    head = head.strip()
    content = [ln for ln in rest if ln.strip() and not ln.lstrip().startswith("#")]
    if head[:1] in ("|", ">"):
        indent = min((len(ln) - len(ln.lstrip()) for ln in content), default=0)
        lines = [ln[indent:] if ln.strip() else "" for ln in rest]
        while lines and not lines[-1]:
            lines.pop()
        if head[0] == "|":
            return "\n".join(lines)
        out, para = [], []
        for ln in lines:
            if ln:
                para.append(ln.strip())
            else:
                out.append(" ".join(para))
                para = []
        out.append(" ".join(para))
        return "\n".join(p for p in out if p)
    if head:
        if content:  # scalar continued on following lines (plain or quoted)
            if head[:1] in ("'", '"'):
                return _unquote(" ".join([head] + [ln.strip() for ln in content]))
            return " ".join([_unquote(head)] + [ln.strip() for ln in content])
        return _scalar(head)
    if not content:
        return ""
    if all(ln.lstrip().startswith("- ") or ln.strip() == "-" for ln in content):
        return [_unquote(ln.lstrip()[2:]) for ln in content]
    out = {}
    indent = min(len(ln) - len(ln.lstrip()) for ln in content)
    for ln in content:
        if len(ln) - len(ln.lstrip()) == indent and ":" in ln:
            k, v = ln.strip().split(":", 1)
            out[_unquote(k)] = _scalar(v) if v.strip() else {}
    return out


KEY_LINE_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:(.*)$")


def parse_frontmatter(lines: list[str]) -> tuple[list[FMKey], str]:
    keys: list[FMKey] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            i += 1
            continue
        m = KEY_LINE_RE.match(ln)
        if not m or ln[0] in " \t":
            return keys, f"line {i + 2}: cannot parse `{ln.strip()[:40]}`"
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or lines[j][0] in " \t" or lines[j].lstrip().startswith("- ")):
            j += 1
        keys.append(FMKey(m.group(1), i, j, _block_value(m.group(2), lines[i + 1:j])))
        i = j
    seen = set()
    for k in keys:
        if k.key in seen:
            return keys, f"duplicate key `{k.key}`"
        seen.add(k.key)
    return keys, ""


def load_doc(path: Path) -> Doc:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
        utf8 = True
    except UnicodeDecodeError:
        text = raw.decode("utf-8-sig", errors="replace")
        utf8 = False
    eol = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return Doc(path, text, eol, bom, False, "no frontmatter: line 1 is not `---`", [], [], text, 0, utf8)
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        return Doc(path, text, eol, bom, False, "frontmatter is never closed with `---`", [], [], text, 0, utf8)
    fm_lines = lines[1:end]
    keys, err = parse_frontmatter(fm_lines)
    body = "\n".join(lines[end + 1:])
    return Doc(path, text, eol, bom, not err, err, fm_lines, keys, body, end + 1, utf8)


def body_offset(text: str) -> int:
    """Index in `text` where the Markdown body starts (after a closed frontmatter block)."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return 0
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    return 0 if end is None else sum(len(ln) + 1 for ln in lines[: end + 1])


def code_mask(md: str, indented: bool = True) -> str:
    """`md` with fenced blocks (``` and ~~~) and inline code spans (any number of backticks)
    blanked to spaces, same length. Indented code is not inferred: whether an indented line is
    code depends on lists, quotes and headings, so a fix never touches indented or quoted lines
    at all (see `fixable_line`) and check reports them as not fixable."""
    out, fence = [], None
    for ln in md.split("\n"):
        s = ln.lstrip()
        if fence:
            # CommonMark: a closing fence uses the same character, is at least as long, and has no info string
            m = re.match(r"^(`{3,}|~{3,})\s*$", s)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append(" " * len(ln))
            continue
        m = re.match(r"^(`{3,}|~{3,})", s)
        if m:
            fence = m.group(1)
            out.append(" " * len(ln))
            continue
        out.append(re.sub(r"(`+)(?:(?!\1).)+?\1", lambda m: " " * len(m.group(0)), ln))
    masked = "\n".join(out)
    # HTML code: <pre>...</pre> and <code>...</code>, across lines too
    return re.sub(r"<(pre|code)\b[^>]*>.*?</\1\s*>", lambda m: re.sub(r"[^\n]", " ", m.group(0)), masked, flags=re.S | re.I)


def fixable_line(md: str, pos: int) -> bool:
    """A line a fix may rewrite: indented under 4 columns (tabs count to the next stop) and not quoted."""
    start = md.rfind("\n", 0, pos) + 1
    end = md.find("\n", pos)
    line = md[start:] if end < 0 else md[start:end]
    lead = len(line) - len(line.lstrip(" \t"))
    return len(line[:lead].expandtabs(4)) < 4 and not line.lstrip().startswith(">")


strip_code = code_mask


def link_spans(md: str) -> list[tuple[int, int, str]]:
    """(start, end, target) of every inline link, image and reference definition outside code
    and HTML comments (a commented-out link is never rendered, so it is not checked or rewritten)."""
    masked = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), code_mask(md), flags=re.S)
    spans = []
    for regex in (LINK_RE, REF_DEF_RE):
        for m in regex.finditer(masked):
            g = 1 if m.group(1) is not None else 2
            spans.append((m.start(g), m.end(g), md[m.start(g):m.end(g)]))
    return sorted(spans)


def is_external(target: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]+:", target, re.I)) and not DRIVE_RE.match(target)


def md_links(md: str) -> list[str]:
    targets = []
    for _start, _end, t in link_spans(md):
        if is_external(t) or t.startswith("#") or t.startswith("{") or "${" in t:
            continue
        t = t.split("#", 1)[0]
        if t:
            targets.append(t.replace("%20", " "))
    return targets


def prose_backslash_paths(md: str) -> list[tuple[int, int]]:
    """Spans of backslash file paths in prose: not in code, not inside a link (links are checked as links)."""
    masked = code_mask(md)
    for start, end, _t in link_spans(md):
        masked = masked[:start] + " " * (end - start) + masked[end:]
    return [(m.start(1), m.end(1)) for m in PATH_BACKSLASH_RE.finditer(masked)]


def body_line_count(body: str) -> int:
    return len(body.rstrip("\n").split("\n")) if body.strip() else 0


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    rule: str
    path: str
    message: str
    can_fix: bool | None = None  # None: whatever the rule says

    @property
    def fixable(self):
        return RULE_BY_ID[self.rule].fixable if self.can_fix is None else self.can_fix


@dataclass
class Context:
    root: Path
    profile: str = "portable"
    ignore: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def add(self, rule, path, message, can_fix=None):
        rel = Path(path).relative_to(self.root).as_posix() if Path(path).is_absolute() else str(path)
        self.findings.append(Finding(rule, rel or ".", message, can_fix))


def load_ignore(root: Path) -> list[str]:
    f = root / ".agentlintignore"
    if not f.is_file():
        return []
    return [ln.strip().rstrip("/") for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]


def ignored(ctx: Context, p: Path) -> bool:
    rel = p.relative_to(ctx.root).as_posix()
    return any(rel == g or rel.startswith(g + "/") or fnmatch.fnmatch(rel, g) for g in ctx.ignore)


def walk(ctx: Context):
    for dirpath, dirnames, filenames in os.walk(ctx.root):
        d = Path(dirpath)
        dirnames[:] = sorted(
            n for n in dirnames
            if n not in SKIP_DIRS and not (n == "worktrees" and d.name == ".claude") and not ignored(ctx, d / n)
            and not (n == OVERLAY_DIR and is_plugin_root(d))
        )
        yield d, sorted(f for f in filenames if not ignored(ctx, d / f))


PLUGIN_MANIFESTS = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "gemini-extension.json", ".cursor-plugin/plugin.json"]


def is_plugin_root(d: Path) -> bool:
    if any((d / m).is_file() for m in PLUGIN_MANIFESTS):
        return True
    pj = d / "plugin.json"
    if pj.is_file():
        try:
            return "agent-plugins" in str(json.loads(pj.read_text(encoding="utf-8")).get("$schema", ""))
        except (ValueError, AttributeError, OSError, UnicodeDecodeError):
            return False
    return False


# ---------------------------------------------------------------------------
# Skill checks
# ---------------------------------------------------------------------------
def check_skill(ctx: Context, skill_dir: Path, entry: Path, daddydock: dict | None, plugin_root: Path | None = None):
    if entry.name != "SKILL.md":
        ctx.add("SKILL-FILE", entry, f"entry file is `{entry.name}`, rename it to `SKILL.md`")
    doc = load_doc(entry)
    if not doc.utf8:
        ctx.add("SK-FM", entry, "file is not UTF-8 text; re-save it as UTF-8", can_fix=False)
    if doc.bom:
        ctx.add("SK-FM", entry, "file starts with a byte-order mark, so hosts do not see the frontmatter", can_fix=doc.utf8)
    if not doc.fm_ok:
        ctx.add("SK-FM", entry, doc.fm_error)
        return
    name = doc.get("name")
    folder = skill_dir.name
    folder_ok = bool(NAME_RE.match(folder)) and len(folder) <= 64 and not folder.endswith("-")
    if not isinstance(name, str) or not name:
        ctx.add("SK-NAME", entry, "`name` is missing", can_fix=folder_ok)
    else:
        if len(name) > 64 or not NAME_RE.match(name) or name.endswith("-"):
            ctx.add("SK-NAME", entry, f"`name: {name}` must be 1-64 chars of a-z, 0-9, - with no leading, trailing or double hyphen", can_fix=folder_ok)
        if name != folder:
            ctx.add("SK-NAME-DIR", entry, f"`name: {name}` differs from folder `{folder}`", can_fix=folder_ok)
        if re.search(r"anthropic|claude", name):
            ctx.add("SK-RESERVED", entry, f"`name: {name}` contains a reserved word")
    desc = doc.get("description")
    if not isinstance(desc, str) or not desc.strip():
        ctx.add("SK-DESC", entry, "`description` is missing or empty")
        desc = ""
    else:
        if len(desc) > 1024:
            ctx.add("SK-DESC", entry, f"`description` is {len(desc)} characters (limit 1024)")
        if XML_RE.search(desc):
            ctx.add("SK-DESC-XML", entry, f"`description` contains a tag: `{XML_RE.search(desc).group(0)}`")
        voice = QUOTED_RE.sub(" ", desc)  # quoted user phrases are trigger examples, not the skill's voice
        m = POV_ANY_CASE.search(voice) or POV_CASED.search(voice)
        if m:
            ctx.add("SK-DESC-POV", entry, f"`description` is not third person (found `{m.group(0)}`)")
        if not WHEN_RE.search(desc + " " + str(doc.get("when_to_use", ""))):
            ctx.add("SK-DESC-WHEN", entry, "`description` does not say when to use the skill (add `Use when ...`)")
    allowed = PORTABLE_FIELDS | (set() if ctx.profile == "claude-ai" else CROSS_HOST_FIELDS)
    extra = [k.key for k in doc.keys if k.key not in allowed]
    if extra:
        movable = all(field_is_movable(doc, k, desc) for k in extra) and doc.utf8
        ctx.add("SK-FIELDS", entry, "non-portable frontmatter fields: " + ", ".join(f"`{k}`" for k in extra), can_fix=movable)
    meta = doc.get("metadata")
    if doc.has("metadata"):
        if not isinstance(meta, dict) or not metadata_is_block(doc):
            ctx.add("SK-META", entry, "`metadata` must be a block mapping of string keys to string values", can_fix=False)
        else:
            nested = [k for k, v in meta.items() if isinstance(v, (dict, list))]
            loose = [k for k, v in meta.items() if not isinstance(v, (str, dict, list))]
            if nested:
                ctx.add("SK-META", entry, "`metadata` values must be strings, not nested maps or lists: " + ", ".join(f"`{k}`" for k in nested), can_fix=False)
            if loose:
                ctx.add("SK-META", entry, "`metadata` values must be quoted strings: " + ", ".join(f"`{k}`" for k in loose), can_fix=doc.utf8)
    comp = doc.get("compatibility")
    if doc.has("compatibility") and (not isinstance(comp, str) or len(comp) > 500):
        ctx.add("SK-META", entry, "`compatibility` must be a string of at most 500 characters", can_fix=False)
    if doc.has("license") and not isinstance(doc.get("license"), str):
        ctx.add("SK-META", entry, "`license` must be a single string", can_fix=False)
    tools = doc.get("allowed-tools")
    if doc.has("allowed-tools") and not isinstance(tools, str):
        listable = isinstance(tools, list) and all(isinstance(t, str) for t in tools)
        ctx.add("SK-META", entry, "`allowed-tools` must be a single string (space-separated tool names)", can_fix=listable and doc.utf8)
    lines = body_line_count(doc.body)
    if lines > 500:
        ctx.add("SB-LINES", entry, f"body is {lines} lines (limit 500)")
    if daddydock is not None and len(desc) > 600:
        ctx.add("DD-DESC", entry, f"`description` is {len(desc)} characters; the Daddy Dock catalog shows 600")
    check_skill_files(ctx, skill_dir, entry, doc, plugin_root)


def raw_scalar(doc: Doc, k: FMKey) -> str | None:
    """The text of a one-line scalar value; None for block scalars, collections and multi-line values."""
    if any(ln.strip() and not ln.lstrip().startswith("#") for ln in doc.fm_lines[k.start + 1:k.end]):
        return None
    head = doc.fm_lines[k.start].split(":", 1)[1].strip()
    if not head or head[0] in "|>[{&*!":
        return None
    return _unquote(head)


def metadata_is_block(doc: Doc) -> bool:
    k = next((k for k in doc.keys if k.key == "metadata"), None)
    return k is None or doc.fm_lines[k.start].split(":", 1)[1].split(" #", 1)[0].strip() == ""


def field_is_movable(doc: Doc, key: str, desc: str) -> bool:
    """Whether `fix` can move a non-portable field without losing anything."""
    if key == "when_to_use":
        wtu, real_desc = doc.get("when_to_use"), doc.get("description")
        return (isinstance(wtu, str) and isinstance(real_desc, str) and bool(real_desc.strip())
                and len(real_desc.rstrip().rstrip(".") + ". " + wtu.strip()) <= 1024)
    if key not in MOVABLE_TO_METADATA or not metadata_is_block(doc):
        return False
    meta = doc.get("metadata")
    if doc.has("metadata") and not isinstance(meta, dict):
        return False
    if isinstance(meta, dict) and key in meta:
        return False
    k = next(k for k in doc.keys if k.key == key)
    return raw_scalar(doc, k) is not None


def resolve_link(base: Path, target: str) -> Path:
    return (base.parent / target.replace("\\", "/")).resolve()


def check_skill_files(ctx: Context, skill_dir: Path, entry: Path, doc: Doc, plugin_root: Path | None = None):
    skill_root = skill_dir.resolve()
    # Hosts install a plugin, or a skills folder, as a set, so links may reach sibling skills.
    # A claude.ai or Skills API upload carries one skill only.
    if ctx.profile != "portable":
        boundary = skill_root
    else:
        boundary = plugin_root.resolve() if plugin_root is not None else skill_root.parent
    md_files = []
    for d, files in walk_skill(ctx, skill_dir):
        for f in files:
            p = d / f
            try:
                size = p.stat().st_size
            except OSError:
                ctx.add("FL-EMPTY", p, "cannot be read (a broken link?)")
                continue
            if size == 0 and f not in PLACEHOLDER_FILES:
                ctx.add("FL-EMPTY", p, "file is empty")
                continue
            if p.suffix == ".json":
                try:
                    json.loads(p.read_text(encoding="utf-8-sig"))
                except ValueError as e:
                    ctx.add("FL-JSON", p, f"does not parse: {e}")
            if p.suffix.lower() == ".md" and p != entry:
                md_files.append(p)
    direct = set()
    for t in md_links(doc.body):
        check_link(ctx, entry, t, boundary)
        tp = resolve_link(entry, t)
        if tp.suffix.lower() == ".md":
            direct.add(tp)
    for p in md_files:
        text = p.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
        for t in md_links(text):
            check_link(ctx, p, t, boundary)
            tp = resolve_link(p, t)
            if tp.suffix.lower() == ".md" and tp.is_file() and tp != entry.resolve() and tp not in direct and is_inside(tp, skill_root):
                ctx.add("SB-DEPTH", p, f"links to `{tp.relative_to(skill_root).as_posix()}`, which `SKILL.md` does not link directly")
        n = len(text.rstrip("\n").split("\n"))
        if n > 100 and not any(TOC_RE.match(ln.strip()) for ln in text.split("\n")[:40]):
            ctx.add("SB-TOC", p, f"{n} lines without a `## Contents` list near the top")
        check_slashes(ctx, p, text[body_offset(text):])  # the fix leaves frontmatter alone, so does check
    check_slashes(ctx, entry, doc.body)
    check_deps(ctx, skill_dir, entry, doc, plugin_root)


def walk_skill(ctx: Context, skill_dir: Path):
    for dirpath, dirnames, filenames in os.walk(skill_dir):
        d = Path(dirpath)
        dirnames[:] = sorted(n for n in dirnames if n not in SKIP_DIRS and not ignored(ctx, d / n))
        yield d, sorted(f for f in filenames if not ignored(ctx, d / f))


def is_inside(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def check_link(ctx: Context, src: Path, target: str, boundary: Path):
    tp = resolve_link(src, target)
    absolute = target.startswith(("/", "\\")) or bool(DRIVE_RE.match(target))
    if absolute or not is_inside(tp, boundary):
        where = "plugin" if is_plugin_root(boundary) else "skill folder" if (boundary / "SKILL.md").is_file() else "skills folder"
        ctx.add("SB-INSIDE", src, f"link `{target}` points outside the {where}")
    elif not tp.exists():
        ctx.add("SB-LINK", src, f"link `{target}` does not resolve")


def slash_spans(md: str) -> list[tuple[int, int, str, bool]]:
    """(start, end, kind, fixable) of every backslash link target and prose path in `md`."""
    spans = []
    for start, end, target in link_spans(md):
        if "\\" in target:
            absolute = target.startswith("\\") or bool(DRIVE_RE.match(target))
            spans.append((start, end, "link", not absolute and fixable_line(md, start)))
    for start, end in prose_backslash_paths(md):
        spans.append((start, end, "path", fixable_line(md, start)))
    return sorted(spans)


def check_slashes(ctx: Context, p: Path, text: str):
    for start, end, kind, fixable in slash_spans(text):
        hint = "" if fixable else " (indented or quoted: fix it by hand, and put commands in a fenced block)"
        ctx.add("SB-SLASH", p, f"{kind} `{text[start:end]}` uses backslashes{hint}", can_fix=fixable)


def check_deps(ctx: Context, skill_dir: Path, entry: Path, doc: Doc, plugin_root: Path | None = None):
    declared = doc.body + "\n" + "\n".join(str(v) for v in [doc.get("compatibility", ""), doc.get("metadata", "")])
    req = skill_dir / "requirements.txt"
    if req.is_file() and "requirements.txt" in doc.body:
        declared += "\n" + req.read_text(encoding="utf-8", errors="replace")
    # modules of the skill, or of its plugin (scripts often put a plugin folder on sys.path)
    home = plugin_root if plugin_root is not None else skill_dir
    local = {p.stem for p in home.rglob("*.py") if not any(part in SKIP_DIRS for part in p.parts)}
    local |= {p.name for p in home.rglob("*") if p.is_dir() and not any(part in SKIP_DIRS for part in p.parts)}
    for p in sorted(skill_dir.rglob("*")):
        if ignored(ctx, p) or any(part in SKIP_DIRS for part in p.parts) or not p.is_file():
            continue
        mods = set()
        if p.suffix == ".py":
            mods = python_imports(p) - local
        elif p.suffix in (".js", ".mjs", ".cjs"):
            mods = node_imports(p)
        for mod in sorted(mods):
            names = {mod, PIP_NAMES.get(mod, mod)}
            patterns = [r"(?<![\w-])" + re.escape(n) + r"(?![\w-])" for n in names]
            if mod in NAMESPACE_PIP:
                patterns.append(r"(?<![\w-])" + re.escape(mod) + r"-[\w-]+")
                wanted = f"a `{mod}-*` package (such as `{NAMESPACE_PIP[mod]}`)"
            else:
                wanted = f"`{PIP_NAMES.get(mod, mod)}`"
            if not any(re.search(pat, declared, re.I) for pat in patterns):
                ctx.add("SC-DEPS", p, f"imports `{mod}` but `SKILL.md` does not say to install {wanted}")


def python_imports(p: Path) -> set[str]:
    try:
        tree = ast.parse(p.read_text(encoding="utf-8-sig", errors="replace"))
    except SyntaxError:
        return set()
    optional = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
            isinstance(h.type, ast.Name) and h.type.id in ("ImportError", "ModuleNotFoundError", "Exception") or h.type is None
            for h in node.handlers
        ):
            for sub in node.body:
                for n in ast.walk(sub):
                    if isinstance(n, (ast.Import, ast.ImportFrom)):
                        optional.add(id(n))
    mods = set()
    for node in ast.walk(tree):
        if id(node) in optional:
            continue
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return {m for m in mods if m not in sys.stdlib_module_names and m != "__future__"}


def node_imports(p: Path) -> set[str]:
    text = p.read_text(encoding="utf-8", errors="replace")
    mods = set()
    for m in re.finditer(r"""(?:require\(\s*|from\s+|import\s+)['"]([^'"]+)['"]""", text):
        spec = m.group(1)
        if spec.startswith((".", "/", "node:")):
            continue
        base = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
        if base not in NODE_BUILTINS and spec not in NODE_BUILTINS:
            mods.add(base)
    return mods


# ---------------------------------------------------------------------------
# Agent and plugin checks
# ---------------------------------------------------------------------------
def check_agent(ctx: Context, path: Path, in_plugin: bool, daddydock: dict | None):
    doc = load_doc(path)
    if not doc.fm_ok:
        ctx.add("AG-FM", path, doc.fm_error)
        return None
    name, desc = doc.get("name"), doc.get("description")
    if not isinstance(name, str) or not name or not isinstance(desc, str) or not desc.strip():
        ctx.add("AG-FM", path, "frontmatter needs both `name` and `description`")
    elif not NAME_RE.match(name):
        ctx.add("AG-FM", path, f"`name: {name}` must use a-z, 0-9 and single hyphens")
    for k in doc.keys:
        if k.key not in AGENT_FIELDS:
            camel = re.sub(r"[-_]([a-z])", lambda m: m.group(1).upper(), k.key)
            hint = f" (did you mean `{camel}`?)" if camel in AGENT_FIELDS else ""
            ctx.add("AG-FIELDS", path, f"unknown field `{k.key}`{hint}")
        elif in_plugin and k.key in PLUGIN_AGENT_IGNORED:
            ctx.add("AG-FIELDS", path, f"`{k.key}` is ignored for plugin agents; ship it in the plugin's hooks or MCP config")
    model = doc.get("model")
    if doc.has("model") and (not isinstance(model, str) or not MODEL_RE.match(model)):
        ctx.add("AG-MODEL", path, f"`model: {model}` is not a known alias or full Claude model ID")
    if len(doc.body) > 30000:
        ctx.add("AG-BODY", path, f"prompt body is {len(doc.body)} characters (limit 30,000)")
    if daddydock is not None and isinstance(desc, str) and len(desc) > 600:
        ctx.add("DD-DESC", path, f"`description` is {len(desc)} characters; the Daddy Dock catalog shows 600")
    return name if isinstance(name, str) and name else path.stem


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), ""
    except (ValueError, OSError) as e:
        return None, str(e)


MANIFEST_KEYS = {
    "$schema", "name", "displayName", "version", "description", "author", "homepage", "repository", "license",
    "keywords", "metadata", "icon", "documentationUrl", "supportUrl", "privacyPolicyUrl", "termsOfServiceUrl",
    "defaultEnabled", "dependencies", "settings", "userConfig", "types", "channels", "skills", "commands", "agents",
    "hooks", "mcpServers", "lspServers", "outputStyles", "workflows", "experimental",
}
#: Component keys and the default location each one would scan anyway.
COMPONENT_DEFAULTS = {
    "skills": "skills", "commands": "commands", "agents": "agents", "hooks": "hooks/hooks.json",
    "mcpServers": ".mcp.json", "lspServers": ".lsp.json", "outputStyles": "output-styles", "workflows": "workflows",
}


def check_manifest_keys(ctx: Context, root: Path, manifest: Path, data: dict):
    for key in data:
        if key not in MANIFEST_KEYS:
            hint = f"; declare it under `experimental.{key}`" if key in ("monitors", "themes") else ""
            ctx.add("PL-KEYS", manifest, f"unknown top-level field `{key}`{hint}")
    for key, default in COMPONENT_DEFAULTS.items():
        value = data.get(key)
        if value is None or isinstance(value, dict):
            continue
        for item in value if isinstance(value, list) else [value]:
            if not isinstance(item, str):
                continue
            if item.startswith(("http://", "https://")):
                continue
            target = (root / item).resolve()
            norm = (item[2:] if item.startswith("./") else item).rstrip("/") or "."
            if not item.startswith("./") and item != ".":
                ctx.add("PL-PATHS", manifest, f"`{key}` path `{item}` must start with `./`")
            elif not is_inside(target, root.resolve()):
                ctx.add("PL-PATHS", manifest, f"`{key}` path `{item}` leaves the plugin folder")
            elif not target.exists():
                ctx.add("PL-PATHS", manifest, f"`{key}` path `{item}` does not exist")
            elif key == "agents" and not (target.is_file() and target.suffix == ".md"):
                ctx.add("PL-PATHS", manifest, "`agents` lists `.md` files, not folders; leave the `agents/` folder to the default scan")
            elif key == "skills" and not target.is_dir():
                ctx.add("PL-PATHS", manifest, f"`skills` path `{item}` must be a folder")
            elif norm == default and key == "hooks":
                # hooks/hooks.json always loads and declared files load as well, so its hooks would run twice;
                # a repeated MCP or LSP file only replaces servers of the same name, which is harmless
                ctx.add("PL-PATHS", manifest, "`hooks` lists `hooks/hooks.json`, which always loads; remove it or the hooks run twice")


def check_plugin(ctx: Context, root: Path, skills: dict[str, Path], agents: dict[str, Path], daddydock: dict | None):
    claude = root / ".claude-plugin" / "plugin.json"
    versions = {}
    names = {}
    if claude.is_file():
        data, err = read_json(claude)
        if data is None:
            ctx.add("FL-JSON", claude, f"does not parse: {err}")
        elif not isinstance(data, dict):
            ctx.add("PL-MANIFEST", claude, "must be a JSON object")
        else:
            problems = []
            n = data.get("name")
            if not isinstance(n, str) or not NAME_RE.match(n):
                problems.append("kebab-case `name`")
            v = data.get("version")
            if not isinstance(v, str) or not re.match(r"^\d+\.\d+\.\d+([-+][\w.-]+)?$", v):
                problems.append("semver `version`")
            if not isinstance(data.get("description"), str) or not data.get("description", "").strip():
                problems.append("`description`")
            a = data.get("author")
            if not isinstance(a, dict) or not isinstance(a.get("name"), str) or not a.get("name"):
                problems.append("`author.name`")
            h = data.get("homepage")
            if h is not None and not (isinstance(h, str) and re.match(r"^https?://\S+$", h)):
                problems.append("valid `homepage` URL")
            # A field of the wrong type makes Claude Code skip the whole plugin, hooks included
            for key in ("repository", "license", "displayName"):
                if key in data and not isinstance(data[key], str):
                    problems.append(f"`{key}` as a string (not {type(data[key]).__name__})")
            kw = data.get("keywords")
            if kw is not None and not (isinstance(kw, list) and all(isinstance(k, str) for k in kw)):
                problems.append("`keywords` as a list of strings")
            if problems:
                ctx.add("PL-MANIFEST", claude, "needs " + ", ".join(problems))
            versions["claude"], names["claude"] = v, n
            check_manifest_keys(ctx, root, claude, data)
    for label, rel in (("codex", ".codex-plugin/plugin.json"), ("cursor", ".cursor-plugin/plugin.json"), ("agent-plugins", "plugin.json"), ("gemini", "gemini-extension.json")):
        p = root / rel
        if not p.is_file():
            continue
        data, err = read_json(p)
        if data is None:
            ctx.add("FL-JSON", p, f"does not parse: {err}")
            continue
        if not isinstance(data, dict):
            ctx.add("PL-VERSION", p, "manifest must be a JSON object")
            continue
        if label == "agent-plugins" and "agent-plugins" not in str(data.get("$schema", "")):
            continue
        versions[label], names[label] = data.get("version"), data.get("name")
    market = root / ".claude-plugin" / "marketplace.json"
    if market.is_file() and names.get("claude"):
        data, err = read_json(market)
        if data is None:
            ctx.add("FL-JSON", market, f"does not parse: {err}")
        else:
            for entry in data.get("plugins", []) if isinstance(data, dict) else []:
                if isinstance(entry, dict) and entry.get("name") == names["claude"] and "version" in entry:
                    versions["marketplace"] = entry["version"]
    vset = {v for v in versions.values() if v is not None}
    nset = {n for n in names.values() if n is not None}
    if len(vset) > 1 or len(nset) > 1:
        detail = ", ".join(f"{k}={versions.get(k)}" for k in versions)
        ctx.add("PL-VERSION", root, f"manifests disagree: {detail}; names {sorted(nset)}")
    hooks_dir = root / "hooks"
    if hooks_dir.is_dir():
        for hp in sorted(hooks_dir.glob("*.json")):
            data, err = read_json(hp)
            if data is None:
                ctx.add("FL-JSON", hp, f"does not parse: {err}")
            elif not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
                ctx.add("PL-HOOKS", hp, "events must sit under a top-level `hooks` object")
    commands = {p.stem: p for p in (root / "commands").glob("*.md")} if (root / "commands").is_dir() else {}
    # Skills and commands share the `/plugin:name` namespace; agents live in their own.
    for n in sorted(set(skills) & set(commands)):
        ctx.add("PL-NAMES", root, f"`{n}` is both a skill and a command, so `/{n}` is ambiguous")
    if daddydock is not None:
        check_daddydock(ctx, root, daddydock, skills, agents)


def check_daddydock(ctx: Context, root: Path, dd: dict, skills: dict[str, Path], agents: dict[str, Path]):
    p = root / "daddydock.json"
    gate = dd.get("license_gate")
    if gate not in ("free", "required"):
        ctx.add("DD-CONFIG", p, f"`license_gate` is {gate!r}; set `free` or `required`")
    if gate == "required" and not (isinstance(dd.get("product"), str) and dd.get("product")):
        ctx.add("DD-CONFIG", p, "a required gate needs a `product` slug")
    for key, items in (("skills_th", skills), ("agents_th", agents)):
        for n in (dd.get(key) or {}):
            if n not in items:
                ctx.add("DD-TH", p, f"`{key}.{n}` names no {key[:-4]} in this plugin")
    gated = [f for f in list(skills.values()) + list(agents.values()) if GATE_MARKER in f.read_text(encoding="utf-8", errors="replace")]
    activate = (root / "skills" / "activate" / "SKILL.md").is_file()
    if gate == "required":
        for f in list(skills.values()) + list(agents.values()):
            if f not in gated and f.parent.name != "activate":
                ctx.add("DD-GATE", f, "required license gate: the gate block is missing")
        if not activate or not (root / "hooks" / "hooks.json").is_file():
            ctx.add("DD-GATE", p, "required license gate: needs `skills/activate` and `hooks/hooks.json` (run the license kit)")
    elif gate == "free":
        for f in gated:
            ctx.add("DD-GATE", f, "free plugin carries a license gate block")
        if activate:
            ctx.add("DD-GATE", p, "free plugin still ships `skills/activate`")


# ---------------------------------------------------------------------------
# Colliding descriptions (SK-WHEN-NOT) and instruction files (IF-LINES)
# ---------------------------------------------------------------------------
INSTRUCTION_FILES = {"CLAUDE.md", "AGENTS.md", "CODEX.md", "GEMINI.md"}
INSTRUCTION_MAX_LINES = 200  # Claude Code's memory guide: target under 200 lines per CLAUDE.md
#: Cosine similarity of two descriptions' weighted words at which they collide. Tuned on the
#: 79 skills and 20 agents of rainmojo-so (2026-10-31): 0.30 flags 9 pairs a person agrees
#: collide (wp-audit/wp-content-audit, aiso-schema/seo-schema, seo-audit/so-audit, ...);
#: just under it sit aiso-audit/so-audit (0.29) and, from 0.28, neighbours that only share
#: plumbing words such as wp-canonical/wp-rest-ops ("api, yoast, rest").
COLLIDE_AT = 0.30
WHEN_NOT_RE = re.compile(r"\bnot for\b|\bdo not use\b|\bdon'?t use\b|\bnever use\b|ไม่ใช้เมื่อ|ไม่ใช่สำหรับ|ไม่ใช้สำหรับ", re.I)
#: Words that say nothing about when to pick one skill over another.
TRIGGER_STOP = set("""
a an the and or of to in on for with by from as at is are be been this that these those it its into via per
use used uses using when whenever if after before during run runs running any all each every one two three not no
skill skills agent agents user users asks asked wants want needs need such e.g eg etc also only then than more most can
will would should may must do does done make makes produce produces return returns full new existing
""".split())


def trigger_words(text: str, drop: list[str]) -> list[str]:
    """Words of a description that could trigger it. English: lower-case words of 3+ letters,
    hyphenated words also split, a crude suffix strip so "audits" and "audit" meet, stop words
    out. Thai has no spaces between words, so each run of Thai script becomes overlapping
    three-character pieces: shared Thai phrases then share pieces without a dictionary.
    Names in `drop` (the other skills) are removed first: "run after wp-link-fix" says the
    two are steps of one pipeline, not that they compete."""
    for n in sorted(drop, key=len, reverse=True):
        text = re.sub(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", " ", text, flags=re.I)
    out = []
    for w in re.findall(r"[a-z0-9][a-z0-9-]*", text.lower()):
        for part in [w] + (w.split("-") if "-" in w else []):
            if part in TRIGGER_STOP or len(part) < 3 or part.isdigit():
                continue
            out.append(re.sub(r"(ies|es|s|ing|ed)$", "", part) if len(part) > 5 else part)
    for run in re.findall(r"[\u0e00-\u0e7f]+", text):
        out += [run[i:i + 3] for i in range(max(1, len(run) - 2))]
    return out


def says_not_for(desc: str, other: str) -> bool:
    """`desc` has a when-not clause that names `other` somewhere after it."""
    m = WHEN_NOT_RE.search(desc)
    return bool(m) and re.search(r"(?<![\w-])" + re.escape(other) + r"(?![\w-])", desc[m.start():], re.I) is not None


def check_collisions(ctx: Context, items: dict[str, tuple[Path, str]], kind: str):
    """Warn on pairs of `items` (name -> (file, description)) whose descriptions collide and
    neither says when not to use it, naming the other. Weights are TF-IDF over this scan, with
    smoothed IDF so a scan of two skills still scores a shared phrase (plain IDF gives it nearly 0)."""
    if len(items) < 2:
        return
    names = sorted(items)
    bags = {n: {} for n in names}
    for n in names:
        for w in trigger_words(items[n][1], [o for o in names if o != n]):
            bags[n][w] = bags[n].get(w, 0) + 1
    df: dict[str, int] = {}
    for bag in bags.values():
        for w in bag:
            df[w] = df.get(w, 0) + 1
    vec = {}
    for n, bag in bags.items():
        v = {w: (1 + math.log(c)) * (1 + math.log((len(names) + 1) / (df[w] + 1))) for w, c in bag.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vec[n] = {w: x / norm for w, x in v.items()}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = {w: x * vec[b][w] for w, x in vec[a].items() if w in vec[b]}
            score = sum(shared.values())
            if score < COLLIDE_AT:
                continue
            (fa, da), (fb, db) = items[a], items[b]
            if says_not_for(da, b) or says_not_for(db, a):
                continue
            top = ", ".join(w for w in sorted(shared, key=shared.get, reverse=True)[:5])
            ctx.add("SK-WHEN-NOT", fa, f"{kind} `{a}` and `{b}` share trigger words ({top}; similarity {score:.2f}); "
                    f"add a `Not for ...` clause that names `{b}` to `{a}`, or the reverse")


def check_instruction_file(ctx: Context, path: Path):
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return
    n = len(text.replace("\r\n", "\n").rstrip("\n").split("\n")) if text.strip() else 0
    if n > INSTRUCTION_MAX_LINES:
        ctx.add("IF-LINES", path, f"{n} lines (limit {INSTRUCTION_MAX_LINES}); move detail into `.claude/rules/` or linked files")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def run_checks(root: Path, profile: str = "portable") -> Context:
    ctx = Context(root.resolve(), profile)
    ctx.ignore = load_ignore(ctx.root)
    skill_entries: list[tuple[Path, Path]] = []
    agent_files: list[Path] = []
    plugin_roots: list[Path] = []
    skill_dirs: set[Path] = set()
    for d, files in walk(ctx):
        if is_plugin_root(d):
            plugin_roots.append(d)
        for f in files:
            if f in INSTRUCTION_FILES:
                check_instruction_file(ctx, d / f)
        entry = next((d / f for f in files if f.lower() == "skill.md"), None)
        if entry:
            skill_entries.append((d, entry))
            skill_dirs.add(d)
    for d, files in walk(ctx):
        if d.name == "agents" and not any(is_inside(d, s) for s in skill_dirs):
            agent_files += [d / f for f in files if f.endswith(".md") and f.lower() != "readme.md"]
    owner = lambda p: max((r for r in plugin_roots if is_inside(p, r)), key=lambda r: len(r.parts), default=None)
    dd_cache: dict[Path, dict | None] = {}

    def daddydock_for(root_dir):
        if root_dir is None:
            return None
        if root_dir not in dd_cache:
            f = root_dir / "daddydock.json"
            data, err = read_json(f) if f.is_file() else (None, "")
            if f.is_file() and data is None:
                ctx.add("DD-CONFIG", f, f"does not parse: {err}")
                data = {}
            dd_cache[root_dir] = data if isinstance(data, dict) or data is None else {}
        return dd_cache[root_dir]

    per_plugin_skills: dict[Path | None, dict[str, Path]] = {}
    per_plugin_agents: dict[Path | None, dict[str, Path]] = {}
    for d, entry in skill_entries:
        r = owner(d)
        check_skill(ctx, d, entry, daddydock_for(r), r)
        per_plugin_skills.setdefault(r, {})[d.name] = entry
    for f in agent_files:
        r = owner(f)
        name = check_agent(ctx, f, r is not None, daddydock_for(r))
        if name:
            per_plugin_agents.setdefault(r, {})[name] = f
    for r in plugin_roots:
        check_plugin(ctx, r, per_plugin_skills.get(r, {}), per_plugin_agents.get(r, {}), daddydock_for(r))
    # Skills compete with skills and agents with agents, across the whole scan: plugins installed together share one host.
    # Copies of one name (templates, per-host mirrors, vendored plugins) are one skill, compared once from its first path.
    for kind, files in (("skills", [e for _d, e in skill_entries]), ("agents", agent_files)):
        items: dict[str, tuple[Path, str]] = {}
        for p in sorted(files):
            doc = load_doc(p)
            desc = doc.get("description") if doc.fm_ok else None
            name = p.parent.name if kind == "skills" else doc.get("name") or p.stem
            if isinstance(desc, str) and desc.strip() and isinstance(name, str):
                items.setdefault(name, (p, desc))
        check_collisions(ctx, items, kind)
    for f in ctx.findings:
        if f.fixable and not own_file(ctx.root / f.path, ctx.root):
            f.can_fix = False  # fix never writes through a link, so do not promise it
    ctx.findings.sort(key=lambda f: (f.path, f.rule, f.message))
    return ctx


def own_file(p: Path, root: Path) -> bool:
    """A real file of the target: not a symlink, junction or hard link, and inside `root`."""
    try:
        if p.is_symlink() or (p.is_file() and p.stat().st_nlink > 1):
            return False
        return Path(os.path.realpath(p)).is_relative_to(Path(os.path.realpath(root)))
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Fixes: mechanical only. Everything else is reported for a person or agent.
# ---------------------------------------------------------------------------
def yq(s: str) -> str:
    """Quote a scalar for YAML when needed."""
    if s and re.match(r"^[\w][\w .,()/+-]*$", s) and not re.match(r"^(true|false|yes|no|on|off|null|~|\d[\d.]*)$", s, re.I):
        return s
    return json.dumps(s, ensure_ascii=False)


def render(doc: Doc, keys_lines: list[str], body: str) -> str:
    return "---\n" + "\n".join(keys_lines) + ("\n" if keys_lines else "") + "---\n" + body


def fix_frontmatter(doc: Doc, only: set[str], skill_dir: Path) -> str | None:
    """Rewrite only the frontmatter lines a fix needs; every other line is kept byte for byte."""
    if not doc.fm_ok or not doc.utf8:
        return None
    lines = list(doc.fm_lines)
    blocks = {k.key: k for k in doc.keys}
    new_block: dict[str, list[str]] = {}
    remove: set[str] = set()
    insert_top: list[str] = []
    add_meta: list[tuple[str, str]] = []
    folder = skill_dir.name
    folder_ok = bool(NAME_RE.match(folder)) and len(folder) <= 64 and not folder.endswith("-")
    if only & {"SK-NAME", "SK-NAME-DIR"} and folder_ok and doc.get("name") != folder:
        if "name" in blocks:
            new_block["name"] = [f"name: {folder}"]
        else:
            insert_top.append(f"name: {folder}")
    desc = doc.get("description") if isinstance(doc.get("description"), str) else ""
    if "SK-FIELDS" in only:
        for k in doc.keys:
            if k.key != "when_to_use" and field_is_movable(doc, k.key, desc):
                add_meta.append((k.key, raw_scalar(doc, k)))
                remove.add(k.key)
        if field_is_movable(doc, "when_to_use", desc) and "description" in blocks:
            merged = desc.rstrip().rstrip(".") + ". " + doc.get("when_to_use").strip()
            new_block["description"] = ["description: " + json.dumps(merged, ensure_ascii=False)]
            remove.add("when_to_use")
    meta_k = blocks.get("metadata")
    if "SK-META" in only:
        tools = doc.get("allowed-tools")
        if isinstance(tools, list) and all(isinstance(t, str) for t in tools):
            new_block["allowed-tools"] = ["allowed-tools: " + yq(" ".join(tools))]
        if meta_k is not None and metadata_is_block(doc):
            block = lines[meta_k.start:meta_k.end]
            content = [ln for ln in block[1:] if ln.strip() and not ln.lstrip().startswith("#")]
            indent = min((len(ln) - len(ln.lstrip()) for ln in content), default=2)
            changed = False
            for i, ln in enumerate(block[1:], 1):
                m = re.match(r"^( +)([^\s:#][^:]*?):[ \t]+(\S.*)$", ln)
                if not m or len(m.group(1)) != indent:
                    continue
                value, sep, comment = m.group(3).partition(" #")
                value = value.rstrip()
                if value[:1] in "\"'|>[{&*!" or isinstance(_scalar(value), str):
                    continue
                block[i] = f"{m.group(1)}{m.group(2)}: {json.dumps(value)}" + (f" #{comment}" if sep else "")
                changed = True
            if changed:
                new_block["metadata"] = block
    tail: list[str] = []
    if add_meta:
        added = [(k, json.dumps(v, ensure_ascii=False)) for k, v in add_meta]
        if meta_k is None:
            tail = ["metadata:"] + [f"  {yq(k)}: {v}" for k, v in added]
        else:
            block = new_block.get("metadata", lines[meta_k.start:meta_k.end])
            content = [ln for ln in block[1:] if ln.strip() and not ln.lstrip().startswith("#")]
            indent = min((len(ln) - len(ln.lstrip()) for ln in content), default=2)
            last = max((i for i, ln in enumerate(block) if ln.strip()), default=0)
            block = block[: last + 1] + [f"{' ' * indent}{yq(k)}: {v}" for k, v in added] + block[last + 1:]
            new_block["metadata"] = block
    if not new_block and not remove and not insert_top and not tail:
        return None
    out: list[str] = list(insert_top)
    i = 0
    for k in doc.keys:
        out += lines[i:k.start]
        if k.key in remove:
            pass
        elif k.key in new_block:
            out += new_block[k.key]
        else:
            out += lines[k.start:k.end]
        i = k.end
    out += lines[i:] + tail
    return render(doc, out, doc.body)


def fix_slashes(text: str) -> str:
    """Forward slashes in relative link targets and prose paths of the Markdown body; code is left alone."""
    offset = body_offset(text)
    head, body = text[:offset], text[offset:]
    spans = [(start, end) for start, end, _kind, fixable in slash_spans(body) if fixable]
    for start, end in sorted(set(spans), reverse=True):
        body = body[:start] + body[start:end].replace("\\", "/") + body[end:]
    return head + body


def contents_block(text: str) -> tuple[list[str], int]:
    """Lines of a `## Contents` list and the line index to insert them at (after the title)."""
    lines = text.split("\n")
    masked = code_mask(text).split("\n")
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in masked if re.match(r"^##\s+\S", ln)]
    items = [f"- {h}" for h in heads if not TOC_RE.match("## " + h)]
    start = 0
    if lines and lines[0].rstrip() == "---":
        start = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), 0) + 1
    for i in range(start, min(start + 6, len(lines))):
        if re.match(r"^#\s+\S", masked[i]):
            block = ["", "## Contents", ""] + items
            if i + 1 >= len(lines) or lines[i + 1].strip():
                block.append("")
            return block, i + 1
    return ["## Contents", ""] + items + [""], start


def plan_fixes(root: Path, only: set[str] | None = None) -> tuple[dict[Path, str], dict[Path, Path], Context]:
    """Return {path: new_text} edits, {old: new} renames, and the findings they answer."""
    ctx = run_checks(root)
    want = {r.id for r in RULES if r.fixable} & (only or {r.id for r in RULES})
    edits: dict[Path, str] = {}
    renames: dict[Path, Path] = {}
    by_file: dict[Path, set[str]] = {}
    for f in ctx.findings:
        if f.rule in want:
            by_file.setdefault(ctx.root / f.path, set()).add(f.rule)

    def current(p: Path) -> str:
        if p in edits:
            return edits[p]
        return p.read_text(encoding="utf-8-sig").replace("\r\n", "\n")

    def is_utf8(p: Path) -> bool:
        try:
            p.read_bytes().decode("utf-8-sig")
            return True
        except (UnicodeDecodeError, OSError):
            return False

    def is_own(p: Path) -> bool:
        return own_file(p, root)

    for p, rules in sorted(by_file.items()):
        if not p.is_file() or not is_own(p) or not is_utf8(p):
            continue  # never rewrite bytes we cannot read back exactly, or a file reached through a link
        if "SKILL-FILE" in rules and p.name.lower() == "skill.md":
            renames[p] = p.with_name("SKILL.md")
        if p.name.lower() == "skill.md" and rules & {"SK-NAME", "SK-NAME-DIR", "SK-FIELDS", "SK-META"}:
            doc = load_doc(p)
            new = fix_frontmatter(doc, rules, p.parent)
            if new is not None:
                edits[p] = new
        if "SK-FM" in rules and load_doc(p).bom:
            edits.setdefault(p, current(p))
        if "SB-TOC" in rules:
            text = current(p)
            block, at = contents_block(text)
            lines = text.split("\n")
            edits[p] = "\n".join(lines[:at] + block + lines[at:])
        if "SB-SLASH" in rules:
            fixed = fix_slashes(current(p))
            if fixed != current(p):
                edits[p] = fixed
    # SB-DEPTH: link every deep file directly from its SKILL.md.
    for f in ctx.findings:
        if f.rule != "SB-DEPTH" or "SB-DEPTH" not in want:
            continue
        src = ctx.root / f.path
        target_rel = re.search(r"links to `([^`]+)`", f.message).group(1)
        skill_dir = next(p for p in [src.parent, *src.parents] if any(c.name.lower() == "skill.md" for c in p.iterdir() if c.is_file()))
        entry = next(c for c in skill_dir.iterdir() if c.name.lower() == "skill.md")
        if not is_own(entry) or not is_utf8(entry):
            continue
        text = current(entry)
        link = target_rel.replace(" ", "%20")
        if f"]({link})" in text:
            continue
        tfile = skill_dir / target_rel
        title = next((re.sub(r"^#+\s*", "", ln).strip() for ln in tfile.read_text(encoding="utf-8", errors="replace").splitlines() if ln.startswith("#")), tfile.stem)
        line = f"- [{target_rel}]({link}): {title}"
        if "\n## Additional resources\n" in text:
            head, tail = text.split("\n## Additional resources\n", 1)
            sec_end = re.search(r"\n#{1,2}\s", tail)
            cut = sec_end.start() if sec_end else len(tail.rstrip("\n"))
            text = head + "\n## Additional resources\n" + tail[:cut].rstrip("\n") + "\n" + line + tail[cut:]
            if not text.endswith("\n"):
                text += "\n"
        else:
            text = text.rstrip("\n") + "\n\n## Additional resources\n\n" + line + "\n"
        edits[entry] = text
    return edits, renames, ctx


def apply_fixes(root: Path, edits: dict[Path, str], renames: dict[Path, Path]) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = root / "_backups" / f"agentlint-{stamp}"
    n = 1
    while backup.exists():  # two runs in one second must not share (and overwrite) a backup
        n += 1
        backup = root / "_backups" / f"agentlint-{stamp}-{n}"
    for p in set(edits) | set(renames):
        dest = backup / p.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    for p, text in edits.items():
        raw = p.read_bytes().decode("utf-8-sig")
        eol = "\r\n" if "\r\n" in raw else "\n"
        p.write_bytes(text.replace("\n", eol).encode("utf-8"))
    for old, new in renames.items():
        rename(old, new)
    return backup


def rename(old: Path, new: Path):
    """Rename through git when the file is tracked: on a case-insensitive file system a plain
    case-only rename (skill.md -> SKILL.md) is invisible to git and would never be committed."""
    try:
        subprocess.run(["git", "-C", str(old.parent), "mv", "-f", old.name, new.name], check=True, capture_output=True, timeout=30)
        return
    except (OSError, subprocess.SubprocessError):
        pass
    tmp = old.with_name(old.name + ".agentlint-tmp")
    old.rename(tmp)
    tmp.rename(new)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def rules_markdown() -> str:
    out = [
        "# Agent plugin and skill standard",
        "",
        f"Standard version {STANDARD_VERSION}. Generated from `scripts/agentlint.py` by `agentlint.py rules --markdown`; do not edit by hand.",
        "",
        "`check` rules are enforced by `agentlint.py check`: a failure is an error unless its level is `warn`, which is reported "
        "but never fails the run. `review` rules need a person or agent to judge. "
        "Rules marked fixable are repaired by `agentlint.py fix --apply`. Daddy Dock rules apply only where `daddydock.json` exists.",
        "",
        f"`agentlint.py check --ci` fails only on the hard rules {', '.join(f'`{r}`' for r in CI_FAIL)} and reports every other "
        "finding as a warning (column CI). Consumer repositories copy `ci/agentlint.yml` from the plugin-optimizer repository.",
        "",
        "## Contents",
        "",
    ]
    areas = list(dict.fromkeys(r.area for r in RULES))
    out += [f"- {a}" for a in areas] + ["- Rule history", "- Sources", ""]
    for a in areas:
        out += [f"## {a}", "", "| ID | Rule | Kind | Level | CI | Fixable | Source |", "|---|---|---|---|---|---|---|"]
        for r in (r for r in RULES if r.area == a):
            lv, ci = (r.level, "fail" if r.id in CI_FAIL else "warn") if r.kind == "check" else ("-", "-")
            out.append(f"| {r.id} | {r.title} | {r.kind} | {lv} | {ci} | {'yes' if r.fixable else 'no'} | {r.source} |")
        out.append("")
    out += [
        "## Rule history",
        "",
        "A rule added after a mistake carries the date and the reason. Older rules get them only when someone edits them; "
        "there is no retroactive sweep (owner decision 2026-10-31).",
        "",
    ] + [f"- {r.id}: {r.added}" for r in RULES if r.added] + [""]
    out += ["## Sources", ""] + [f"- {k}: {v}" for k, v in SOURCES.items()] + [""]
    return "\n".join(out)


def level(rule: str, ci: bool) -> str:
    """"error" when a finding of `rule` fails the run, "warn" when it is only reported."""
    if ci:
        return "error" if rule in CI_FAIL else "warn"
    return RULE_BY_ID[rule].level


def annotation_path(root: Path, rel: str) -> str:
    """A finding's path relative to the working directory, which is the repository root in a workflow."""
    p = (root / rel).resolve()
    try:
        return p.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agentlint", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="report problems")
    c.add_argument("path", nargs="+", type=Path)
    c.add_argument("--json", action="store_true")
    c.add_argument("--profile", choices=["portable", "claude-ai"], default="portable")
    c.add_argument("--ci", action="store_true", help=f"fail only on {', '.join(CI_FAIL)}; warn on the rest")
    f = sub.add_parser("fix", help="repair mechanical problems (dry run unless --apply)")
    f.add_argument("path", type=Path)
    f.add_argument("--apply", action="store_true")
    f.add_argument("--only", default="", help="comma-separated rule IDs")
    r = sub.add_parser("rules", help="list the standard")
    r.add_argument("--markdown", action="store_true")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "rules":
        if args.markdown:
            sys.stdout.flush()
            sys.stdout.buffer.write(rules_markdown().encode("utf-8"))  # bytes: no CRLF translation on Windows
        else:
            for x in RULES:
                print(f"{x.id:16} {x.kind:6} {'fix' if x.fixable else '   '}  {x.title}")
        return 0

    if args.cmd == "check":
        all_findings = []
        for p in args.path:
            if not p.exists():
                print(f"agentlint: {p} does not exist", file=sys.stderr)
                return 2
            ctx = run_checks(p, args.profile)
            all_findings += [(p, x) for x in ctx.findings]
        levels = [(p, x, level(x.rule, args.ci)) for p, x in all_findings]
        errors = sum(1 for *_, lv in levels if lv == "error")
        if args.json:
            print(json.dumps([{"root": str(p), "rule": x.rule, "path": x.path, "message": x.message, "fixable": x.fixable, "level": lv} for p, x, lv in levels], ensure_ascii=False, indent=1))
        elif args.ci:
            github = os.environ.get("GITHUB_ACTIONS") == "true"
            for p, x, lv in sorted(levels, key=lambda t: t[2] != "error"):
                if github:  # workflow commands: GitHub shows them on the PR's changed files
                    msg = x.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                    print(f"::{'error' if lv == 'error' else 'warning'} file={annotation_path(p, x.path)},title={x.rule}::{msg}")
                else:
                    print(f"{'error' if lv == 'error' else 'warning'}: {x.path}: {x.rule}: {x.message}")
            print(f"\nagentlint --ci: {errors} error(s) fail CI ({', '.join(CI_FAIL)}), {len(levels) - errors} warning(s).")
        else:
            for p, x, lv in levels:
                print(f"{x.path}: {x.rule}{' (warning)' if lv == 'warn' else ''}{' (fixable)' if x.fixable else ''}: {x.message}")
            fixable = sum(1 for _, x in all_findings if x.fixable)
            warned = f" and {len(levels) - errors} warning(s)" if len(levels) > errors else ""
            print(f"\n{errors} problem(s){warned}, {fixable} fixable with `agentlint.py fix --apply`." if all_findings else "No problems found.")
        return 1 if errors else 0

    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    unknown = (only or set()) - set(RULE_BY_ID)
    if unknown:
        print(f"agentlint: unknown rule(s) {sorted(unknown)}", file=sys.stderr)
        return 2
    root = args.path.resolve()
    edits, renames, ctx = plan_fixes(root, only)
    for p, text in sorted(edits.items()):
        old = p.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
        rel = p.relative_to(root).as_posix()
        sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), text.splitlines(True), f"a/{rel}", f"b/{rel}"))
    for old, new in sorted(renames.items()):
        print(f"rename {old.relative_to(root).as_posix()} -> {new.relative_to(root).as_posix()}")
    if not edits and not renames:
        print("Nothing to fix automatically.")
        return 0
    if args.apply:
        backup = apply_fixes(root, edits, renames)
        print(f"\nApplied {len(edits)} edit(s) and {len(renames)} rename(s). Originals copied to {backup.relative_to(root).as_posix()}/.")
        left = run_checks(root).findings
        print(f"{len(left)} problem(s) remain; run `agentlint.py check` for the list.")
    else:
        print(f"\nDry run: {len(edits)} edit(s), {len(renames)} rename(s). Re-run with --apply to write them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
