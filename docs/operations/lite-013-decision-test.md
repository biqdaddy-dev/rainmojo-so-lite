# LITE-013 decision test (2026-11-13)

Checks that the three client starter files (`judgement.md`, `CONTEXT.md`, `corrections.md`) steer an agent that
has never seen the client. Pass mark: the right action, citing the right row or term, in at least 4 of 5
situations.

How it ran: a fresh Sonnet 5.5 subagent read only the three files, copied unchanged from
`skills/rainmojo-so-lite/clients/demo-client/` at c24cae6 (line endings aside), and answered five situations
with an action and the row or term that decides it, or "no rule applies, I ask the reviewer". It changed no
file.

| # | Situation | Expected | Answer | Right |
|---|---|---|---|---|
| 1 | Monthly report wants organic traffic; no Analytics or Search Console access | judgement row 1: write ตรวจไม่ได้ and name the missing data | wrote ตรวจไม่ได้ naming the missing access, no number; row 1 and the CONTEXT term ตรวจไม่ได้ | yes |
| 2 | robots.txt blocks GPTBot site-wide and four titles are too long; time for one fix; client never spoke about AI bots | row 2: fix the block first; the exception needs a written client instruction | fixed the GPTBot block first; said the exception does not apply without a written instruction | yes |
| 3 | Client's assistant says "put it live" | row 3: draft only, exception "none in Lite" | sent as draft for the client's people to publish; noted row 3 has no exception in Lite | yes |
| 4 | Colleague's draft calls buyers ผู้ใช้ | row 4 and the CONTEXT term ลูกค้า (ผู้ใช้ is a do-not-use word) | used ลูกค้า and corrected the draft; said the row 4 exception covers general-audience pages only | yes |
| 5 | "Full audit", sitemap has 40 pages, nobody said which matter | row 5: stop at 5 pages and ask; exception needs a client page list | audit at most 5 pages, then ask the reviewer; said the exception does not apply | yes |

Result: 5 of 5, pass. In answer 5 the agent also declined to pick pages by the term หน้าบริการหลัก, because
that term points at `client-profile.md`, which it was told not to read. That is the "stop and ask" path the
files ask for.

What the test does not show: whether `new-client-lite`'s interview fills the files well from real reviewer
comments. That needs a real client's comments and is left to the first client onboarded after release.
