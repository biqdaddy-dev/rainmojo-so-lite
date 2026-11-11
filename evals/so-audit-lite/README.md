# so-audit-lite outcome eval (LITE-007)

Baseline for blueprint DP-023 section 9: 10 cases x 3 runs of the `so-audit-lite` agent, graded on
the outcome only. Every structural change to lite (one version source, `python -I`, shared
blocks, references, agent folds) is measured against this baseline on the same harness.

| File | What it is |
|---|---|
| `cases/<id>/site/` | offline snapshot of a synthetic `.test` site, served on 127.0.0.1 |
| `cases/<id>/case.json` | ground truth: `expected_facts`, `unavailable_data`, `kind` (positive or negative) |
| [rubric.md](rubric.md) | the judge's 100-point scale (A facts 40, B honest coverage 15, C no invented numbers 15, D actionable 10, E carried through 20) |
| `inapp.py` | prepares, serves, collects, scores and summarises runs; standard library only |
| `test_inapp.py` | unit checks for the harness (`python -I evals/so-audit-lite/test_inapp.py`) |
| `baseline.json` | the summary of the baseline batch, once it has run |

The 10 cases are the snapshots of rainmojo-so `evals/so-audit/cases/` (RSO-035 branch, built by its
`build_cases.py`), copied unchanged: 7 positive, 3 negative (all crawlers blocked, no sitemap,
one-page placeholder). The same snapshots let a lite score sit beside a rainmojo-so score, but the
two are never compared as one number: the rubrics differ.

What the lite rubric changes against rainmojo-so's:
- Deliverables are under `work/<domain>/` (`04-reports/` for the combined report and its
  `_summary.json`), not `clients/<domain>/reports/data/audit-base.json`.
- Honest coverage is read from the report and `transparency.could_not_verify`, since lite has no
  `not_audited` array.
- Any combined or weighted score, score out of 100 or `score` block counts as an invented number:
  lite reports levels and counts of checks passed only.

## How a run goes (in the app, one subagent per run)

`claude -p` cannot log in on this machine (2026-11-05 onward), so a session in the app runs the
agents, as rainmojo-so's RSO-029 harness does. The agent reads a staged copy of the plugin
without `evals/`, pinned to one commit, outside the repo; the installed plugin is not used.

```bash
OUT="$TEMP/rainmojo-so-lite-evals/<batch>"
python evals/so-audit-lite/inapp.py prepare --out "$OUT" --case case-01-roastery --run 1 --plugin <plugin copy>
python evals/so-audit-lite/inapp.py serve   --out "$OUT" --case case-01-roastery --run 1   # background
# agent subagent, model sonnet, prompt = $OUT/case-01-roastery/run-1/prompt.md
python evals/so-audit-lite/inapp.py collect --out "$OUT" --case case-01-roastery --run 1 \
    --model sonnet --effort default --wall-seconds N --tool-uses N --tokens N --final-message FILE
# judge subagent, model sonnet, prompt = judge-prompt.md, answer saved as judge.json
python evals/so-audit-lite/inapp.py score   --out "$OUT" --case case-01-roastery --run 1 --judge-model sonnet
python evals/so-audit-lite/inapp.py summary --out "$OUT" --write-baseline evals/so-audit-lite/baseline.json
```

Rules learned on rainmojo-so that apply here:
- Results never sit under a `.claude/` folder (every write there asks for approval).
- Every run has its own `scratch/` folder; parallel runs once shared a scratchpad file.
- The subagent transcript (`~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`)
  is the record of tokens and tool calls; the background task output file is empty on Windows.
- Run nothing heavy beside a batch: a loaded machine makes agents skip steps, which shows up as
  lost points on E.
- Cost is computed from the token counts and the model, never from the weekly meter, which other
  sessions move too.

## Pilot, 2026-11-12 (case-01-roastery run 1, plugin 2.8.3 at 257310c, Sonnet 5.5 agent and judge)

- Score 96: 9 of 10 facts (missed F8, the missing alt text on the /shop/ images, which the run marked
  could not verify), B 15, C 15, D 10, E 20. No combined score, `present.py --lint` passed.
- Agent: 308,309 tokens, 60 tool calls, 49 minutes. Judge: 103,987 tokens, 8 tool calls, under a minute.
  About 412k tokens a run with its judging, against about 270k for a rainmojo-so so-audit Sonnet run
  without judging.
- The run is kept as run 1 of case-01 in the baseline batch: same harness, same pinned plugin copy.
- An earlier attempt (184k tokens) is not scored: its mirror served the cases from the repo checkout and
  answered 404 after the checkout changed branch. `prepare` now copies the snapshot into the run folder.
- The final message was saved condensed in its last two paragraphs (what could not be done, conflicts);
  later runs save the hand-back text verbatim.
- The run surfaced three instruction conflicts in lite itself: `so-audit-lite` promises an 8-row status
  table but lists 7 phases; it allows 15 task items while `report-lite` caps fixes at 10; it names the
  report `_so-audit_` while `report-lite` names it `_aiso-report_`.
