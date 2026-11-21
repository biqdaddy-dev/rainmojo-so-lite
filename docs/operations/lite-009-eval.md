# LITE-009 before and after (so-audit-lite outcome eval)

This uses the same harness as the LITE-007 baseline (`evals/so-audit-lite/`, harness commit 3725705):
- 10 cases x 3 runs.
- One Sonnet 5.5 agent per run, reading a pinned copy of the plugin.
- One Sonnet 5.5 judge per run, using the lite rubric: A facts 40, B honest coverage 15, C no invented numbers 15, D actionable 10, E carried through 20.

- Before: main 257310c (2.8.3), batch run 2026-11-12 to 13, summary in `evals/so-audit-lite/baseline.json` on the LITE-007 branch.
- After: this branch at 4f918f3, batch run 2026-11-13 to 21, summary in [lite-009-eval-after.json](lite-009-eval-after.json).

| | Before | After |
|---|---|---|
| Mean | 97.68 | 98.07 |
| Min / max | 83 / 100 | 73 / 100 |
| Standard deviation | 4.52 | 6.54 |
| Positive cases (7) | 98.44 | 100.00 |
| Negative cases (3) | 95.89 | 93.56 |
| A. Facts | 38.98 | 39.00 |
| B. Honest coverage | 15.00 | 14.53 |
| C. No invented numbers | 14.77 | 14.53 |
| D. Actionable | 9.93 | 10.00 |
| E. Carried through | 19.00 | 20.00 |
| Runs that lost E points | 3 | 0 |
| Agent tokens (30 runs) | 7.41M, mean 247k | 7.55M, mean 252k |
| Judge tokens | about 2.70M | 2.92M |

| Case | Before | After |
|---|---|---|
| case-01-roastery | 96, 100, 100 | 100, 100, 100 |
| case-02-clinic | 100, 100, 100 | 100, 100, 100 |
| case-03-spa | 100, 100, 100 | 100, 100, 100 |
| case-04-hotel | 90, 100, 100 | 100, 100, 100 |
| case-05-shop | 100, 100, 100 | 100, 100, 100 |
| case-06-law | 98, 100, 90 | 100, 100, 100 |
| case-07-blocked | 100, 100, 100 | 100, 100, 100 |
| case-08-nositemap | 100, 90, 100 | 100, 100, 100 |
| case-09-thin | 100, 90, 83 | 73, 93, 76 |
| case-10-media | 100, 100, 93.3 | 100, 100, 100 |

## Verdict

The fix does what it is for. E (carried through) is at the ceiling in all 30 runs.

The baseline lost E points in three runs. In case-06 r3 and case-08 r2, every script call used `python -I`, and the scripts stopped on missing `requests`, `bs4` and `lxml`. The LITE-010 after-batch, which lacks this fix, hit the same failure in case-06 r2. No run in this batch reported a missing module, and all 21 positive runs scored 100.

The mean moved by 0.39. That is inside one standard deviation, so the number alone proves nothing; the E line and the per-case table carry the evidence.

## Where points were lost, and why it is not this change

case-09-thin (73, 93, 76) is the 13-word placeholder site. It was the weakest case in every batch: 100/90/83 before, and 90/76/93 after LITE-010.

All three runs graded content, citability and E-E-A-T on that page with check counts instead of saying there was too little to audit. Two of them also put on-page tuning ahead of pre-launch build work. The judges counted those grades as invented results and missed facts, which cost points on A, B and C.

This is a gap in the instructions, not a script failure. The port of rainmojo-so RSO-036, a scope gate that withholds grading for a blocked or near-empty site, is the follow-up that targets it.

## Notes on the run

- An app restart on 2026-11-13, then a pause by the owner, stopped three runs: case-04 r2 and case-05 r1 and r2. Their folders are kept as `run-N.abandoned-restart2`, and the runs were redone on 2026-11-21 in fresh folders on new mirror ports.
- case-08 r3 handed back the literal word `PLACEHOLDER` as its final chat message. Its report, summary and per-skill files were all written, and it was kept as recorded. The judge graded the files and scored it 100.
- The case-09 r1 judge wrote 45 as its total while its parts add up to 73. The runner recomputes the total from the parts and keeps 73.
