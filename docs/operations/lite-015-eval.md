# LITE-015 before and after: scope gate (so-audit-lite outcome eval)

This uses the same harness, rubric and models as LITE-007 to LITE-009 (`evals/so-audit-lite/`, harness commit 3725705, Sonnet 5.5 agent and judge). Plugin under test: this branch at 1bc6688, batch run 2026-11-21. The summary is in [lite-015-eval-after.json](lite-015-eval-after.json).

The eval is targeted, like rainmojo-so's RSO-036 after-eval:
- the two negative cases the gate is for, 3 runs each;
- the three positive cases with the least main text, 1 run each, to show the gate leaves them open.

| Case | Kind | Gate | After (1bc6688) | Before: LITE-009 batch (4f918f3) | Before: baseline (257310c) |
|---|---|---|---|---|---|
| case-07-blocked | negative | closed: robots `Disallow: /`, 3 of 3 noindex | 100, 100, 100 | 100, 100, 100 | 100, 100, 100 |
| case-09-thin | negative | closed: 13 words on 1 page | 100, 100, 100 | 73, 93, 76 | 100, 90, 83 |
| case-03-spa | positive | open: 0 words, client-rendered | 100 | 100, 100, 100 | 100, 100, 100 |
| case-06-law | positive | open: 78 words on 5 pages | 100 | 100, 100, 100 | 98, 100, 90 |
| case-10-media | positive | open: 85 words on 6 pages | 100 | 100, 100, 100 | 100, 100, 93.3 |

All 9 runs scored 100. Every criterion is at the ceiling: A 40, B 15, C 15, D 10, E 20.

Agents used 1.20M tokens. Most negative runs took about 100k each, because the gate stops the audit early. Judges used 0.83M tokens.

## What changed in the runs

- **case-09-thin** was the only case below 100 in every earlier batch. In those runs the agent graded content, citability and E-E-A-T on a 13-word "Coming soon" page with check counts. After the change, all three runs:
  - stopped at the gate;
  - marked every area ตรวจไม่ได้ with the gate reason;
  - still listed the missing robots.txt, sitemap, llms.txt, meta description, canonical and JSON-LD;
  - led the work list with what to build before an audit means anything.
- **case-07-blocked** already scored 100. The gate makes the stop deterministic: before, it depended on the agent reading phase 1.1. Every run now opened with the block and gave no level anywhere. The card reads "Not graded: blocked, noindex".
- **The three positive cases** kept their full audits:
  - case-03 (0 words of raw HTML, React shell) is recognised as client-rendered and audited, with client-side rendering reported as the finding.
  - case-06 (78 words, Thai) and case-10 (85 words, Thai) sit above the 50-word cut and were audited normally.

## Thai word count without pythainlp

Lite does not require pythainlp. Counting each Thai run as one word, as rainmojo-so's fallback does, would put case-06 at 33 words and case-10 at 48. The gate would then close on two real sites.

`text_words.py` therefore estimates one word per 5 Thai characters when pythainlp is missing. That gives 96, 192 and 89 on the three Thai cases, against 78, 181 and 85 with pythainlp.

This eval machine has pythainlp, so the runs above used it. The estimate is covered by `scope_gate_test.py` (ThaiWithoutPythainlp) and by the measurement in the LITE-015 commit.

## Notes

- Several runs saw robots.txt and sitemap.xml return 404 on the case-09 mirror and said so in their reports. That is the snapshot as built: case-09 has neither file.
- The card's gate reason is in English even on a Thai card, because the reasons come from `scope_gate.py`. This is a small follow-up, not part of this change.
