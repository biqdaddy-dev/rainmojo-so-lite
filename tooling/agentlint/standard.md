# Agent plugin and skill standard

Standard version 1.1.0. Generated from `scripts/agentlint.py` by `agentlint.py rules --markdown`; do not edit by hand.

`check` rules are enforced by `agentlint.py check`: a failure is an error unless its level is `warn`, which is reported but never fails the run. `review` rules need a person or agent to judge. Rules marked fixable are repaired by `agentlint.py fix --apply`. Daddy Dock rules apply only where `daddydock.json` exists.

`agentlint.py check --ci` fails only on the hard rules `SK-NAME-DIR`, `SK-DESC`, `SB-LINES` and reports every other finding as a warning (column CI). Consumer repositories copy `ci/agentlint.yml` from the plugin-optimizer repository.

## Contents

- Skill
- Files
- Instructions
- Agent
- Plugin
- Daddy Dock
- Writing
- Workflow
- Scripts
- Safety
- Testing
- Context
- Rule history
- Sources

## Skill

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| SKILL-FILE | The skill's entry file is named exactly `SKILL.md`. | check | error | warn | yes | AS |
| SK-FM | Frontmatter opens with `---` on line 1 (no byte-order mark) and parses. | check | error | warn | yes | CS |
| SK-NAME | `name`: 1-64 chars of `a-z`, `0-9`, `-`; no leading, trailing or double hyphen. | check | error | warn | yes | AS |
| SK-NAME-DIR | `name` equals the skill's folder name. | check | error | fail | yes | AS |
| SK-RESERVED | `name` does not contain the reserved words `anthropic` or `claude`. | check | error | warn | no | BP |
| SK-DESC | `description` is present and 1-1024 characters. | check | error | fail | no | AS |
| SK-DESC-XML | `description` contains no XML or HTML tags. | check | error | warn | no | BP |
| SK-DESC-POV | `description` is third person: no I, we, you or your (Thai: ผม, ฉัน, เรา, คุณ). | check | error | warn | no | BP |
| SK-DESC-WHEN | `description` says when to use the skill (for example `Use when ...`). | check | error | warn | no | BP |
| SK-WHEN-NOT | Two skills (or two agents) whose descriptions share trigger words: at least one says when not to use it and names the other (`Not for ...`, `Do not use ...`, `ไม่ใช้เมื่อ ...`, `ไม่ใช่สำหรับ ...`). | check | warn | warn | no | PO |
| SK-FIELDS | Frontmatter uses only portable fields: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`, plus `disable-model-invocation`, `user-invocable`, `paths`, `argument-hint`. Host-only settings (hooks, context, model, effort) go in the host adapter. | check | error | warn | yes | AS |
| SK-META | `metadata` maps strings to strings; `compatibility` is at most 500 chars; `license` and `allowed-tools` are single strings. | check | error | warn | yes | AS |
| SB-LINES | `SKILL.md` body is at most 500 lines; move detail into reference files. | check | error | fail | no | BP |
| SB-LINK | Every relative link in the skill resolves to a file. | check | error | warn | no | BP |
| SB-INSIDE | Links stay inside the plugin, or inside the skills folder for skills outside a plugin; under `--profile claude-ai`, where each skill uploads alone, inside the skill folder. | check | error | warn | no | AS |
| SB-DEPTH | Every bundled Markdown file that is linked anywhere is linked directly from `SKILL.md` (one level deep). | check | error | warn | yes | BP |
| SB-TOC | Bundled Markdown files longer than 100 lines start with a `## Contents` list. | check | error | warn | yes | BP |
| SB-SLASH | File paths use forward slashes. | check | error | warn | yes | BP |
| SC-DEPS | Every third-party package a bundled script imports is named in `SKILL.md` with how to install it. | check | error | warn | no | BP |

## Files

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| FL-EMPTY | No empty files. | check | error | warn | no | PO |
| FL-JSON | Every `.json` file parses. | check | error | warn | no | PO |

## Instructions

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| IF-LINES | `CLAUDE.md`, `AGENTS.md`, `CODEX.md` and `GEMINI.md` are at most 200 lines; move the rest into `.claude/rules/` or linked files. | check | warn | warn | no | MM |

## Agent

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| AG-FM | Agent files have frontmatter with `name` and `description`; `name` uses `a-z`, `0-9`, `-` and has no `:`. | check | error | warn | no | SA |
| AG-FIELDS | Agent frontmatter uses known camelCase fields only; plugin agents do not set `hooks`, `mcpServers`, `permissionMode` or `initialPrompt` (hosts ignore them). | check | error | warn | no | SA |
| AG-MODEL | `model` is `inherit`, `haiku`, `sonnet`, `opus`, `fable` or a full `claude-...` model ID. | check | error | warn | no | SA |
| AG-BODY | Agent prompt body is at most 30,000 characters. | check | error | warn | no | XH |
| AG-TOOLS | An agent with a `tools` list is not told to do what those tools cannot: run work in parallel through subagents without `Agent`, invoke a skill without `Skill`, run commands without `Bash`, or use a named tool it lacks. | check | warn | warn | no | SA |

## Plugin

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| PL-MANIFEST | `.claude-plugin/plugin.json` has a kebab-case `name`, a semver `version`, a `description`, `author.name`, an `http(s)` `homepage` if set, and string `repository`, `license` and `displayName` and a string list of `keywords` (a wrong type makes Claude Code skip the plugin). | check | error | warn | no | PR |
| PL-KEYS | `.claude-plugin/plugin.json` uses only documented top-level fields (`monitors` and `themes` go under `experimental`). | check | error | warn | no | PR |
| PL-PATHS | Component paths in the manifest start with `./`, stay inside the plugin, exist, list `.md` files for `agents`, and `hooks` does not list `hooks/hooks.json` (it always loads, so its hooks would run twice). | check | error | warn | no | PR |
| PL-VERSION | Every manifest of the plugin (Claude, Codex, Agent Plugins, Gemini, marketplace entry) carries the same name and version. | check | error | warn | no | XH |
| PL-HOOKS | Hook files under `hooks/` parse and wrap their events in a top-level `hooks` key. | check | error | warn | no | PR |
| PL-NAMES | No skill and command in one plugin share a name (both become `/plugin:name`). | check | error | warn | no | CS |

## Daddy Dock

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| DD-CONFIG | `daddydock.json` parses, `license_gate` is `free` or `required`, and a required gate names its `product`. | check | error | warn | no | DD |
| DD-DESC | Skill and agent descriptions are at most 600 characters, so the catalog shows them whole. | check | error | warn | no | DD |
| DD-TH | Every key in `skills_th` and `agents_th` names an existing skill or agent. | check | error | warn | no | DD |
| DD-GATE | A `required` gate has the gate block in every skill and agent plus the `activate` skill and hook; a `free` plugin has none of them. | check | error | warn | no | DD |

## Writing

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| RV-CONCISE | Only add what the model does not already know (house data, prices, rules, schemas); cut general explanations. | review | - | - | no | BP |
| RV-TOP | Put the most important instructions near the top of `SKILL.md`: after compaction a host may keep only the start of a skill. | review | - | - | no | CS |
| RV-STANDING | Write standing instructions ("run the tests after every edit"); hosts do not re-read `SKILL.md` on later turns. | review | - | - | no | CS |
| RV-TERMS | Use one term per concept throughout. | review | - | - | no | BP |
| RV-TIME | No time-sensitive statements; keep legacy material in an `Old patterns` section. | review | - | - | no | BP |
| RV-DEFAULT | Give one default approach with an escape hatch, not a menu of options. | review | - | - | no | BP |
| RV-NAMES | Name skills by activity (`processing-pdfs`) and files by content (`form_validation_rules.md`); avoid `helper`, `utils`, `doc2.md`. | review | - | - | no | BP |

## Workflow

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| RV-FREEDOM | Match freedom to fragility: prose heuristics for open tasks, a template for preferred patterns, an exact script for fragile steps. | review | - | - | no | BP |
| RV-CHECKLIST | Multi-step workflows give a copyable checklist and say which step to return to when a check fails. | review | - | - | no | BP |
| RV-LOOP | Quality-critical work runs validate, fix, validate again, and proceeds only when it passes. | review | - | - | no | BP |
| RV-PATTERNS | Templates state how strict they are; style-dependent output shows input/output examples; branching tasks use a conditional workflow. | review | - | - | no | BP |
| RV-PLAN | Batch or destructive work writes a plan file, validates it with a script, then executes and verifies. | review | - | - | no | BP |

## Scripts

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| RV-SCRIPTS | Scripts handle their own errors, explain every constant, and the skill says whether to run or read each script. | review | - | - | no | BP |
| RV-MCP | Name MCP tools fully qualified (`Server:tool`). | review | - | - | no | BP |
| RV-RUNTIME | Runtime differs by host: APIs may have no network or installs; never install packages globally. | review | - | - | no | BP |

## Safety

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| RV-HOOKS | A rule that must hold every time is enforced by a hook for every host the plugin ships to, not by skill text alone. | review | - | - | no | CS |
| RV-SIDE-EFFECTS | Skills with side effects (deploy, send, publish, delete) set `disable-model-invocation: true`. | review | - | - | no | CS |
| RV-TOOLS | Grant agents only the tools they need; `allowed-tools` pre-approves, it never restricts. | review | - | - | no | SA |

## Testing

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| RV-EVALS | Each skill has at least three eval cases under `evals/<skill>/` in its plugin (a case is a folder holding `case.json`, `case.yaml` or `prompt.md`; checked by `check --evals`, since built packages carry no evals), run with the same pass bar on every model and host it ships to. | check | warn | warn | no | BP |
| RV-UNUSED | Find skills nobody invokes with Claude Code's `/skill-doctor` (never-invoked skills ranked by context cost) and turn them off or remove them; do not guess from the source. | review | - | - | no | CS |

## Context

| ID | Rule | Kind | Level | CI | Fixable | Source |
|---|---|---|---|---|---|---|
| CX-LISTING | The skill listing (each skill's name plus `description` and `when_to_use`, capped at 1,536 characters an entry) fits Claude Code's listing budget of 1% of the context window: about 8,000 characters at 200k tokens (`check --context-tokens` to change). Past it, Claude Code drops descriptions starting with the least-invoked skills. | check | warn | warn | no | CS |
| CX-SESSION | What loads every session (skill listing, agent descriptions, and the text `SessionStart` hooks print) stays within 2% of the context window, about 16,000 characters at 200k tokens; `agentlint.py context` prints the breakdown. | check | warn | warn | no | HK |
| CX-REPEAT | No block of paragraphs (300 characters or more) repeats word for word in 3 or more skill, agent or command files; keep one copy and link to it. | check | warn | warn | no | BP |
| CX-COUNT | One plugin ships at most 50 skills, commands and agents together: the model picks less reliably past about 30 to 50 entries. | check | warn | warn | no | PO |

## Rule history

A rule added after a mistake carries the date and the reason. Older rules get them only when someone edits them; there is no retroactive sweep (owner decision 2026-10-31).

- SK-WHEN-NOT: 2026-10-31, owner decision: when-not text only on colliding pairs such as `seo-audit` and `so-audit`, not on every skill, because descriptions load every session and the Daddy Dock catalog shows 600 characters
- IF-LINES: 2026-10-31, owner decision: instruction files load in full every session; oversize ones are split into `.claude/rules/`
- RV-EVALS: 2026-11-01, AF-1 of the agent-alignment blueprint (PS-148): evals come before any change to a skill, and the review rule was never checked
- RV-UNUSED: 2026-11-05, PO-2 of the agent-alignment blueprint (DP-023): usage lives in the host, so agentlint points at `/skill-doctor` instead of estimating it
- CX-LISTING: 2026-11-05, PO-2 of DP-023: rainmojo-so's 79 descriptions total 20,370 characters, so most of its skills list without the words that trigger them
- CX-SESSION: 2026-11-05, PO-2 of DP-023: plugins were measured by file size only, never by what every session pays for
- CX-REPEAT: 2026-11-05, PO-2 of DP-023: three blocks repeated in 78 rainmojo-so SKILL.md files were 22% of all its skill text
- CX-COUNT: 2026-11-05, PO-2 of DP-023: the blueprint's 30-50 range for tool selection; rainmojo-so ships 79 skills and 20 agents
- AG-TOOLS: 2026-11-05, PO-2 of DP-023: rainmojo-so `agents/aiso-audit.md` says "run in parallel" with no Agent tool, so the model ignores it or pretends

## Sources

- BP: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- AS: https://agentskills.io/specification
- CS: https://code.claude.com/docs/en/skills
- MM: https://code.claude.com/docs/en/memory
- SA: https://code.claude.com/docs/en/sub-agents
- HK: https://code.claude.com/docs/en/hooks
- PR: https://code.claude.com/docs/en/plugins-reference
- PE: https://code.claude.com/docs/en/plugin-evals
- XH: Host docs: Codex, Cursor, VS Code/Copilot, Gemini CLI, Antigravity (checked 2026-10-08)
- DD: Daddy Dock catalog and release contract
- PO: plugin-optimizer field experience
