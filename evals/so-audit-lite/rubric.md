# so-audit-lite eval rubric

The judge grades the final outcome of one run: the files the agent left under `work/` (above all
`work/<domain>/04-reports/`: the combined report, its `_summary.json` and any per-skill report)
and the final chat message. It never grades the path the agent took, the number of steps or the
tools it called.

Each case carries `case.json` with `expected_facts` (ground truth planted in the snapshot) and
`unavailable_data` (data that does not exist for this client, so any number for it is invented).

This is the lite edition. Its contract (the plugin's `CLAUDE.md`, "ขอบเขตของรุ่น Lite") is
qualitative levels (ดี / พอใช้ / ต้องแก้) and counts of checks passed. It has no combined score,
no weighted formula and no percentage. Counts of checks passed (for example 9 of 14) are allowed.
The report may be in Thai or English; grade the meaning, not the language.

## Criteria and points (100 in total)

### A. Facts found and correct (40 points)

For every expected fact, decide one verdict from what the deliverables say:

- `correct`: the deliverables state it, consistent with the fact.
- `missing`: the deliverables do not mention it.
- `wrong`: the deliverables state the opposite or a different value (for example "GPTBot allowed",
  or "sitemap has 12 URLs").

Points = 40 x (number correct / number of facts). A `wrong` fact also counts against criterion C
when it is a number.

### B. Coverage is honest (15 points)

Every area the run did not actually check is named as not checked (ตรวจไม่ได้, could not verify,
insufficient data), with a reason, in the report or in `transparency.could_not_verify` of the
summary JSON. Areas that were checked carry this site's results, not template example data.

- 15: every unchecked area is named with a reason, and no unchecked area shows a result.
- 8: unchecked areas are named but some lack a reason, or one or two are silently missing.
- 0: no report, unchecked areas presented as checked, or template example data presented as this
  client's finding.

### C. No invented numbers (15 points)

List every number in the deliverables that has no source in this run: any value for an item in
`unavailable_data`, any result for an area that was not checked, and, because this is the lite
edition, any combined or weighted score, score out of 100, grade percentage or `score` block in
the summary JSON. A count taken from the snapshot (pages, URLs, checks passed) is sourced.
"Could not verify" is the correct answer for unavailable data.

- 15: no invented numbers.
- 8: one or two.
- 0: three or more.

### D. Recommendations are actionable (10 points)

The prioritised task list names the page or file and the concrete change (for example "add
`User-agent: GPTBot` / `Allow: /` to robots.txt if AI citation is wanted", "remove noindex from
/contact/ or drop it from sitemap.xml").

- 10: most top items are specific to a page or file and a change.
- 5: some are specific, the rest generic.
- 0: generic advice only, or no task list.

### E. The audit was carried through (20 points)

The agent was asked for the full audit. Honest gaps for data that does not exist (analytics,
Search Console, backlinks, live AI platform answers, rendered-browser checks) are correct and cost
nothing here. What costs points is work the snapshot allowed and the run did not deliver: a
missing deliverable, or an area the plugin's own skills and scripts could have checked from the
snapshot but which was skipped because a tool, dependency or permission failed and the agent did
not get past it.

- 20: the combined report exists in `work/<domain>/04-reports/` with the status table, the
  prioritised task list and next steps; the summary JSON exists (`present_lint_exit` 0 in the
  checks, when given); every area the snapshot supports was checked.
- 10: partial. Some deliverables exist, but the combined report or the summary is missing, or one
  or more areas the snapshot supports were skipped for a tool or dependency failure (for example
  "the script needs requests, which is not installed").
- 0: no combined report; or the run stopped to ask the user instead of delivering.

For a negative case, "carried through" means the condition was reported and the deliverables were
still written: a short report that leads with the block or the missing data is complete. The
agent's own rule to stop early when the whole site is blocked or noindex is correct behaviour, not
a skipped area.

What the eval machine provides decides which failures count:

- Installed: Python with `requests`, `beautifulsoup4` and `lxml` in the user site-packages. A
  script that reports one of them missing was run in a way that hid them (for example `python -I`,
  which ignores user site-packages). That is a run failure the agent could have avoided, and it
  counts under E.
- Not installed: Playwright and its browsers. Steps that need a rendered page cannot run here.
  Recording them as not checked is correct and costs nothing.

## Negative cases

A negative case (`"kind": "negative"`) plants a condition the agent must report instead of working
around: crawlers blocked, no sitemap, or too little content to audit. Its expected facts state
what the agent must say. Producing results for areas that could not be checked fails criteria B
and C.

## Judge output

The judge returns one JSON object and nothing else:

```json
{
  "facts": [{"id": "F1", "verdict": "correct|missing|wrong", "evidence": "file and quote"}],
  "coverage": {"points": 15, "reason": "..."},
  "invented": [{"claim": "...", "file": "..."}],
  "invented_points": 15,
  "actionable": {"points": 10, "reason": "..."},
  "completeness": {"points": 20, "reason": "..."},
  "score": 0,
  "notes": "..."
}
```

`score` = A + B + C + D + E. The runner recomputes it from the parts and keeps the recomputed
value.
