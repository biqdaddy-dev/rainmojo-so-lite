# LITE-010 before and after (so-audit-lite outcome eval)

Same harness as the LITE-007 baseline (`evals/so-audit-lite/`, harness commit 3725705): 10 cases x 3 runs,
one Sonnet 5.5 agent per run reading a pinned copy of the plugin, one Sonnet 5.5 judge per run with the lite
rubric (A facts 40, B honest coverage 15, C no invented numbers 15, D actionable 10, E carried through 20).

- Before: main 257310c (2.8.3), batch run 2026-11-12 to 13, summary in `evals/so-audit-lite/baseline.json`
  on the LITE-007 branch.
- After: this branch at 4b4f735, batch run 2026-11-13, summary in
  [lite-010-eval-after.json](lite-010-eval-after.json).

| | Before | After |
|---|---|---|
| Mean | 97.68 | 98.00 |
| Min / max | 83 / 100 | 76 / 100 |
| Standard deviation | 4.52 | 5.07 |
| Positive cases (7) | 98.44 | 99.33 |
| Negative cases (3) | 95.89 | 94.89 |
| A. Facts | 38.98 | 39.20 |
| B. Honest coverage | 15.00 | 14.53 |
| C. No invented numbers | 14.77 | 14.77 |
| D. Actionable | 9.93 | 10.00 |
| E. Carried through | 19.00 | 19.50 |
| Agent tokens (30 runs) | 7.41M, mean 247k | 7.96M, mean 265k |
| Judge tokens | about 2.70M, mean 96k | 2.93M, mean 98k |

| Case | Before | After |
|---|---|---|
| case-01-roastery | 96, 100, 100 | 100, 96, 100 |
| case-02-clinic | 100, 100, 100 | 100, 100, 100 |
| case-03-spa | 100, 100, 100 | 100, 100, 100 |
| case-04-hotel | 90, 100, 100 | 100, 100, 100 |
| case-05-shop | 100, 100, 100 | 100, 100, 100 |
| case-06-law | 98, 100, 90 | 100, 90, 100 |
| case-07-blocked | 100, 100, 100 | 100, 100, 100 |
| case-08-nositemap | 100, 90, 100 | 100, 100, 95 |
| case-09-thin | 100, 90, 83 | 90, 76, 93 |
| case-10-media | 100, 100, 93.3 | 100, 100, 100 |

Verdict: no regression. The mean moved by 0.32, well inside one standard deviation. Every criterion stayed within
half a point. Agents still followed the routing and presentation rules from the short pointer blocks:
- every run wrote its report under `work/<domain>/04-reports/`;
- every run passed `present.py --lint`;
- no run wrote a combined score.

Where the after-batch lost points, and why none of it comes from this change:
- case-09-thin r1-r3 (90, 76, 93): the weak case in the baseline too. The runs graded content, citability and
  E-E-A-T on a 13-word placeholder page instead of saying there was too little to audit. In r2 the judge
  counted two of those grades as invented results, which cost 7 points on B and 7 on C. This is a gap in
  the instructions, already on the list of follow-ups.
- case-06-law r2 (90): the scripts reported `beautifulsoup4` and `lxml` missing, which is the `python -I`
  problem LITE-009 fixes. This branch does not carry that fix.
- case-08-nositemap r3 (95): the run skipped per-skill steps on its own, with no tool failure (E 15).
- case-01-roastery r2 (96): missed one fact, the missing alt text on the /shop/ images.

Notes on the run:
- One app restart killed three case-08 runs. Their folders are kept as `run-N.abandoned-restart`, and they were
  rerun in fresh folders on new mirror ports.
- One case-10 run hit missing dependencies and installed `requests` and `beautifulsoup4` into its own scratch
  folder to get past them. The judge did not count that against it. It is the same `python -I` cause.
