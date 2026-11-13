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

## Baseline, 2026-11-13 (10 cases x 3 runs, plugin 2.8.3 at 257310c, Sonnet 5.5 agent and judge)

[baseline.json](baseline.json) holds the numbers. Mean 97.68 (min 83, max 100, standard deviation 4.52);
positive cases 98.44, negative cases 95.89.

| Criterion | Mean | Max |
|---|---|---|
| A. Facts found | 38.98 | 40 |
| B. Honest coverage | 15.0 | 15 |
| C. No invented numbers | 14.77 | 15 |
| D. Actionable | 9.93 | 10 |
| E. Carried through | 19.0 | 20 |

| Case | Runs | Mean |
|---|---|---|
| case-01-roastery | 96, 100, 100 | 98.7 |
| case-02-clinic | 100, 100, 100 | 100 |
| case-03-spa | 100, 100, 100 | 100 |
| case-04-hotel | 90, 100, 100 | 96.7 |
| case-05-shop | 100, 100, 100 | 100 |
| case-06-law | 98, 100, 90 | 96.0 |
| case-07-blocked | 100, 100, 100 | 100 |
| case-08-nositemap | 100, 90, 100 | 96.7 |
| case-09-thin | 100, 90, 83 | 91.0 |
| case-10-media | 100, 100, 93.3 | 97.8 |

Cost: agents 7.41M tokens (mean 247k a run, 126k to 398k), judges about 2.7M (mean 96k). Wall time
5 to 70 minutes a run; at most 3 to 6 runs at a time, under PC load from other sessions.

What it says about lite today:
- Facts, honesty and invented numbers are at the ceiling, as in rainmojo-so's baseline, so a later
  change can only show up there as a regression.
- E lost points in 2 runs (case-06 r3, case-08 r2) where every script call used `python -I` and the
  scripts stopped on missing `requests`, `bs4` and `lxml`: all 11 python calls in case-06 r3 had `-I`.
  LITE-009 is the fix; its after-batch measures it.
- case-09-thin is the weakest case: two of three runs graded content, citability and E-E-A-T on a
  13-word placeholder with check counts instead of saying there was too little to audit.
- Runs often hit the same three instruction conflicts first seen in the pilot (8-row table with 7
  phases, 15 vs 10 task items, `_so-audit_` vs `_aiso-report_`), and several rewrote
  `build_summary.py` output by hand because `page_analyzer.py` misreads Thai without a charset header
  (false SSR-01 FAIL).

How the batch ran: the first batch folder sat in `%TEMP%`, where `src/` and `_plugin/` vanished
overnight; batches now sit under the user profile. One judge answer had a stray `]` and was repaired
by hand before scoring (case-09 r2). Judge totals that disagreed with their own parts (case-02 r3 said
90, parts 100) are recomputed by the runner.
