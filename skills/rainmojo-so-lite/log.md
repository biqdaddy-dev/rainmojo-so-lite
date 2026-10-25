# Log - rainmojo-so-lite

The roadmap record for this plugin. Every task, hotfix included, gets a row in Contents
before work starts, with its ID, its `หมวด` (category) and its planned hours. Closing a
task adds a detail entry below and moves the row's facts into it: actual hours, the PR and
the version it shipped in. Daddy Dock's Dev Timeline reads this file and the repo's merged
pull requests; nothing is typed into Daddy Dock by hand.

`หมวด` is one of: content production, image pipeline, audit skills, presentation, platform
and packaging, docs, infrastructure.

## Contents

- [2026-09-12] release - v2.0.0 public release mirror of RAINMOJO SO, lite scope: 43 skills, 17 agents, checklists and counts instead of weighted scores.
- [2026-09-12] feature - v2.1.0 MCP Apps card server and the presentation layer folded in from rainmojo-so 3.15.0.
- [2026-09-12] fix - v2.1.1 plugin description under 500 characters for the Claude Code marketplace.
- [2026-10-01] feature - v2.2.0 AVIF next to WebP, folded in from rainmojo-so 3.18.0.
- [2026-10-11] chore - v2.3.0 cross-host agent standard met: `.claude-plugin`, `.codex-plugin`, `gemini-extension.json` and the `platforms/` overlays built with agentpack.
- [2026-10-13] fix - v2.3.1 repository moved to biqdaddy-dev: the manifests, the marketplace entry and the README install commands point at https://github.com/biqdaddy-dev/rainmojo-so-lite (DP-002).
- [2026-10-25] feature - v2.4.0 image shot spec, physics and logic validation and the plausibility gate, ported from the full edition's DP-014 (DP-015, หมวด: image pipeline, ชม. แผน 5): every generated image now carries a shot spec with real distances, sizes, camera, one key light and a support for every object; `image_spec.py` validates the physics and logic of the brief, derives the geometry it implies (frame width, field of view, depth of field, apparent-size ratios, the fraction of each standing figure the horizon must cross), compiles it into the prompt and avoid list, and builds the reviewer's atomic questions. The prompt is never typed by hand: a hand-edited prompt or a spec changed after compilation is refused. New `image-model-registry.json` carries per-generator capability data so the compiler knows which models have a negative-prompt field at all. The 30-item plausibility rubric is ordered on measured failure prevalence (functional 58.7 per cent, anatomical 51.4, stylistic 39.0, physics 9.17) and asks the physics checks across pairs of entities, because generated frames are consistent object by object and inconsistent between objects.

- [2026-10-26] chore - v2.7.0 re-port from f632e00, carrying the six findings this edition reported (DP-016, หมวด: image pipeline, ชม. แผน 1): `image_spec.py`, `image_spec_contract_test.py`, `image-spec.example.json` and the new `image-spec.real-place.example.json` taken byte-identical from the full edition, plus the `spec-template --reference` flag in `image_production.py`. The contract test runs here unchanged at 169 assertions and `regression.py` is 3/3. The regenerated review example comes out byte-identical to the full edition's while being built from this edition's own defaults and generator, and the contract test now asserts it against the compiler so it cannot drift again. Upstream carries all six findings, three of which were bugs that refused correct briefs, plus `spec.realism.imperfections` and four lint rules.

## [2026-10-26] chore - v2.7.0 re-port from f632e00 (DP-016)

The review loop ran twice: this edition ported `ad2e1ad`, proved parity, and reported six
findings against it; the full edition fixed all six and this edition ported `f632e00` and
proved parity again. That is the loop working as intended, with the module in one place and
the battery in the other.

WHAT THE REPORT FOUND, all six fixed upstream. Three were bugs that refused correct briefs,
which is worse than no check at all: the scale anchor was resolved to `subjects[0]` rather
than to the person the anchor names, so a brief naming the second person was refused with a
message quoting the first; the landmark check compared `height_m` with a height above the
floor for objects that hang or are mounted, where `height_m` is the object's own length; and
a landmark word was read as a height claim even when the anchor was about width, which real
briefs write constantly. The other three: `conditioning_images` were gated on the set rather
than per image, so one client-owned photo authorised feeding anything to a generator,
including a URL with no provenance row; `blank_spec` scaffolded neither the reference block
nor `ground_height_m`, leaving the headline features undiscoverable; and the shipped review
example had drifted from the compiler.

The licensing one earned its keep immediately on the other side: the new per-image rights
check failed one of the full edition's own fixtures on its first run, where a subject's
reference image had no source row. A person's likeness now needs a rights row like anything
else fed to a model.

WHAT CAME BACK IN RETURN: `spec.realism.imperfections`, required with at least two placed
entries for a photographic medium, because an unplaced flaw is decoration and a placed one
is what makes a frame read as a photograph; four lint rules, including a refusal of simile
anywhere in a spec, since a generator draws the thing you compared to and a hand "like a
pianist's" puts a piano in the frame; and a full worked real-place example.

THE BATTERY, now four files in the shared notes folder and run against `f632e00`: 20 caught,
2 warned, 4 missed on the first axis set, where three of the four misses are a guard that
must stay legal, a scene that is valid, and the locale contradiction left to the reviewer.
The nine brief-checkable cases on the second axis set are written as fixtures with a guard
each, and all nine report as valid isolated probes against both editions.

THE RULE THAT PAID FOR ITSELF: a probe that comes back caught has to be read, not counted,
because it may have been refused by a rule that fired before the probe tested anything. It
is now enforced in the fixture file rather than left as advice: every case asserts which
error fired and carries a correct brief of the same shape that must stay legal. On its first
run it rejected two fixtures written an hour earlier - one used a negation the module
rightly refuses, the other a simile the new lint rule rightly refuses - and it also found
that an older probe of this edition's own had been reporting a miss while testing nothing,
because moving every entity to one distance had broken plane ordering.

THIRD PORT, `041193e`, same version: both remaining proposals landed upstream and are in.
`state` is required on every object, with the vocabulary left to the reviewer for the reason
argued in the report - a word list would reward "open" and refuse "the leaf swung back
against its stop", inverting the file's own rule that prose beats tokens, and it could not
be validated against any corpus because not one object in any fixture is a mechanism. And
`support.by` is scanned for supports that hold nothing, for bearing kinds only, so a boat
may still float. Contract test 175 assertions, passing here unchanged with no fixture edits
needed. **The first axis set now has no genuine open gaps**: 21 caught, 2 warned, 3 missed,
and all three misses are a guard that must stay legal, a scene that is valid, and the locale
contradiction left to the reviewer.

VERSION FROZEN AT 2.7.0 for the rest of this branch. Two editions assigned versions from
snapshots of a moving branch and collided twice: this branch was read at 2.6.0 and the
sitemap branch was told to take 2.7.0, by which time this branch had bumped to 2.7.0 itself.
The release is one release, not one per commit, so further work here goes in without a bump
and the sitemap branch takes 2.8.0.

FOURTH PORT, `f808a4b`, same version: nine client-sweep defects that each refused a correct
brief, including `extends_beyond_frame`; five atomic hands questions in place of one
compound one; the crash class closed structurally, with shared names bound once at the top
of `validate_spec` and twelve malformed-input shapes asserted to return; and a compiler bug
where a horizon value meaning "outside the frame" was read as a position in it. Contract test
204 assertions passing here unchanged, regression 3/3, and the regenerated review example,
now 80 spec questions, byte-identical to the full edition's. **The battery gives identical
verdicts against both editions with CRASH 0 in every file**, which extends parity from the
module to the tests that probe it.

Two battery fixtures were wrong and the harness found both. The width probe had a guard for
an object merely running out of frame but none for the new field, so a second guard now
asserts that the same 9 m counter becomes legal once it declares `extends_beyond_frame`,
with `width_m` kept as the real size. And of the fourteen malformed-input shapes lifted into
the fixtures, one built a reference block on a spec that had none, where a malformed block
is correctly ignored: it answered with no errors and tested nothing. The new ANSWERED EMPTY
verdict flagged it, and the reference shapes now build on the real-place example as the full
edition's C33 does. That is the read-not-count failure pointing the other way: not a probe
refused by the wrong rule, but a probe that never reached the rule at all.

FIFTH PORT, `7d4748a`, same version, after a re-review of this edition's own work. The rule
refusing a brief that forbids what it also shows fired on any shared word, and the full
edition's tests asserted the wrong refusals as correct; it now fires only when an avoid
entry reduces to the declared name. Contract test 213 assertions passing here unchanged.

THE RE-REVIEW, and what it found in this edition's work rather than upstream's:

- A battery of mutations measures what rules catch and cannot, by construction, measure
  what they wrongly refuse, because every mutation starts from one known-good scene. Run
  against the sixteen real client briefs the sweep wrote, this edition's validator at
  `f808a4b` refused seven, four of them correct briefs: a quarter of real work. The battery
  had surfaced none of them. At `7d4748a` it refuses three, all true positives.
- Of the nine proposals this edition ranked and handed over, two were wrong and one too
  broad, which only running each as an oracle against the real corpus showed. The one
  ranked first, requiring `interacts_with` to be declared from both sides, would have
  refused its own guard and twelve of sixteen real briefs: authors write the field as a
  directed relation, and it is inert, since blanking it leaves the prompt, the questions
  and the warnings byte-identical. A fixture comment claimed the shipped example already
  declared both directions; it does not. The transparency proposal missed its own case,
  because its check was not scoped to its object and an unrelated sentence in the base
  scene satisfied it, and refused everyday glass. The reflection proposal refused chrome
  trim and is narrowed to mirrors.
- Neither withdrawn proposal reached the contract test. Only the two that hold were lifted
  upstream, `state` required and `support.by` scanned, and both refuse no real brief.
- PENDING was the weak verdict. It proved a guard passes while no rule exists and never that
  the proposal, once built, would leave correct briefs alone. The battery now carries the
  oracles and the corpus that test that, and reports a rule no real brief reaches as
  UNTESTED rather than READY, since passing a corpus that never triggers it is vacuous.
- The PR figures were re-measured from session metadata rather than commit times and held:
  `createdAt` to `lastActivityAt` agrees with the earlier figure to within 0.05 hours.

SIXTH PORT, `c2761f5` and `cfbdba3`, same version. Only `image_spec.py` and the shipped
review example changed upstream; the contract test did not, so it stays at 213 and passes
here unchanged. The review example, regenerated from this edition's own defaults, grows from
80 to 82 questions and is byte-identical to the full edition's. Against the real briefs:
16 of 19 clean, the same three true positives as before.

The new people-implied warning fires on three real briefs that declare no people. Two are
true positives, where the purpose's opening words would paint people the brief does not
want: "the moment a rental car is handed over" over an empty still life, and "the truck as
its customers meet it". The third is a false positive of a pattern: the regex matches
`explain\w*` and `consult\w*`, so it fires on nouns that name things, "a technical
explainer", "the consultation room", and "the consultant's empty office" where the purpose
says empty. Bounding both to verb forms keeps the two true positives, drops the false one,
and gets six test cases right; reported upstream, not changed here.

THREE DEFECTS IN THIS EDITION'S OWN BATTERY, found while checking this port and fixed. The
battery lives outside the repo, so none of this is in the commit, but it is the record:

- `realism_probe2.py` had not run its own code since the harness was wired in. It imported
  its base scene from `realism_probe.py`, importing runs a module, and that module had come
  to end in `raise SystemExit`, so it ran all of its own probes and then exited the
  interpreter before one line of the importer ran. probe2 was reported green for several
  rounds. The tell was there to read and was not read: its totals were byte-identical to
  probe1's. probe1 now runs only as a script.
- Once running, probe2's prompt check asserted a false negative. It searched for "above the
  child", which the compiler never writes, and reported the child's horizon crossing missing
  when the prompt says "passes above the head of the child". It also labelled a prompt-only
  search "asked" for a fact that is asked, as a review question. It now uses the compiler's
  own phrasing, says where each fact is expected, and fails the run when one goes missing.
- `corpus.py` resolved its scripts directory with a fresh glob, which in the full edition
  picks `skills/activate/scripts` first, so it looked for the self-test brief in the wrong
  skill and silently dropped it: the corpus shrank by one and still reported clean. It now
  resolves from the module actually loaded, reports any source it cannot read, and the
  edition loader refuses to guess if two skills ever ship `image_spec.py`.

All three are the same failure, a result that looks like a pass while measuring less than it
claims, and the last two were found only by asking why two numbers that should match did
not. Every battery file now gives identical results in both editions.

SEVENTH PORT, `6be1a7f`, same version: booster words refused only as a bare list item,
negation skipping quoted lettering, all-caps signage, "No. 9", hyphenated compounds and "not
only", and no more "no a ..." in an inline Constraints block. `image_spec.py`, the contract
test and `image-spec.contract.md` byte-identical; 234 assertions passing here unchanged. On
the eighteen real briefs nothing moved, no refusal, warning or compiled prompt, and that is
because nothing reaches the changed paths: no brief uses a booster word anywhere, and the only
negation word outside `must_not_show` in any of them is `text_in_image`'s required value
"none", which is not prose. So both changes are vouched for by C35 alone, and the corpus
cannot speak for them either way.

THE DOCS THAT DESCRIBED A DESIGN THIS EDITION HAD REPLACED. Porting the contract doc led to a
question that should have been asked five ports earlier: what has this edition's own prose
said since `b7e1d4b`, when its `image_spec.py` was replaced by the full edition's? It had kept
describing the 2.5.0 design it replaced.

- `image-spec.contract.md` said a two-landmark anchor is read by intersecting both bands, with
  the hull as fallback, and named a derived field `eye_line_offsets`. The code takes the first
  landmark the anchor names, and the field does not exist; it is `eye_line_people`. The doc
  was 2.5.0's edit, never re-ported because the full edition's doc had not changed, so the
  parity check, which covered the files ported, never looked at the file edited. It is now
  the full edition's, byte for byte.
- `content-production-lite/SKILL.md` told authors to bracket an anchor between two landmarks
  because both bands are read, so an author following it believed the second landmark
  constrained the check; it is ignored. It also said an object above a third of the holder's
  height cannot be described as filling a palm. The code measures against the tallest person
  in the frame, not the holder, and above three tenths only warns; it refuses above six.
- `agent.json` repeated the bracketing advice, gave a seated eye-level band of one head height
  where the code uses 0.15 m, and said face distance is set by the distance alone, whatever
  the lens, where the code refuses a face closer than a per-lens floor from 1.2 m at 20 mm to
  0.6 m at 85 mm.

All three were in pushed PR #6. Neither lite-only file is ever overwritten by a port, so
nothing would have corrected them. They now describe the code, and `doc_claims_test.py`, T4
in `regression.py`, pairs every number they quote with the constant or behaviour it
describes, and fails if either side moves. Run against the docs as they stood before this
commit it fails fifteen times, including all four stale claims; against the corrected docs
it passes. One claim of the six held and is unchanged: the lighting rule.

Reading the code to write the docs correctly surfaced two upstream questions, reported to
the full edition rather than changed here: the hand-held rule measures against the tallest
person rather than the holder named in `support.by`, so an object that is half a child's
height only warns because an adult is also in frame; and the face-distance table permits the
most nose-to-ear distortion on the longest lens, 1.167 at 85 mm against 1.083 at 20 mm,
although its own comment names a perspective effect that depends on distance alone.

EIGHTH PORT, `0eb7919`, same version: the people-implied warning bounded to verb forms for
explain, consult and welcome, and C36 pinning the six sweep behaviours and the eye-line gate,
24 assertions that did not exist before. `image_spec.py` and the contract test byte-identical;
the contract doc did not change. 258 assertions passing here unchanged, regression 4 of 4,
and T4 passing, which is the first time it has been tested by a real upstream change: this
port moved none of the numbers the lite docs quote, and T4 says so rather than leaving it
assumed. On the corpus the warning fires on drivehub and rotkubkhao, the two true positives,
and no longer on papayiw.

The bounding fixes words whose noun has its own suffix, explainer, consultation, welcoming.
It cannot fix words spelled the same as noun and verb, and five remain that warn on scenes
with nobody in them: "the meeting room before the day starts", "a serving tray of iced
drinks", "teaching materials on an empty desk", "a greeting card by the till", "the staff
room after closing". "A serving tray" and "a waiter serving drinks" are the same token, so no
word list separates them. None of these occurs in the sixteen real briefs, so the rule's
behaviour on them is untested on real work rather than measured. It is a warning, not a
refusal, so the cost is noise; the cheap remedy reported upstream is for the warning to
quote the word that fired, which it does not today, so an author sees "serving" beside
"serving tray" and dismisses it.

NINTH PORT, `569a7ae` and `050ea4e`, same version. The two code questions this edition raised
are fixed upstream: the hand-held rule measures against the holder, and the face floor is one
0.9 m perspective floor on every lens with more room on the two widest. `interacts_with`
leaves the blank template; the contract doc gains the table of what `validate_spec` refuses;
routed questions carry a structured `measure`. `image_spec.py`, the contract test and the
contract doc byte-identical, 277 assertions passing unchanged, review example unchanged. On
the eighteen real briefs nothing moved. The face floor tightened at 50 mm and 85 mm and gained
a floor above 85 mm, which is where real briefs would be newly refused, so the reach was
checked rather than assumed: the nearest face in any of them is 0.9 m on 35 mm, exactly on a
floor that did not move, and every 50 mm face is 1.5 m or more. Again, real work does not
reach the changed path.

T4 DID ITS JOB, AND HAD A HOLE. It failed on the two face floors that moved, as it should.
But it stayed green on the hand-held change, although `SKILL.md` said the rule compared
against "the tallest person in the frame" and the code now measures the holder. Its check of
that sentence was for presence only, which proves a sentence was not deleted and nothing
about whether it is true; the 0.35 m standing band was the same. Both are now tested by
behaviour, in a scene where the doc's claim and its opposite give different answers: a 0.70 m
object in a 1.02 m child's palm with a 1.68 m adult beside her, refused only if the holder is
measured, and a lens 0.34 m and then 0.36 m from the standing eye line. The face floors are
pinned on both sides at 20, 28, 50 and 135 mm. T4 was hardened before the docs were changed,
and failed against them on the claim it had missed, which is the proof it now covers it; it
passes at 32 checks, up from 21, and every claim in it is pinned to a constant or a behaviour.

TENTH PORT, `f5a3989`, same version: the people-implied warning quotes what fired and tells
the author to ignore it when the quoted word names a thing. That was this edition's
suggestion for the five homographs, meeting, serving, teaching, greeting and staff, which no
word list can separate from the verbs. `image_spec.py` and the contract test byte-identical;
the contract doc did not change. 278 assertions passing unchanged, regression 4 of 4 with T4
green, review example unchanged. On the real briefs the warning quotes "handed" for drivehub
and "customers" and "meet" for rotkubkhao; on each of the five homograph purposes it quotes
the word and carries the note to ignore it.

ELEVENTH PORT, `4b64093`, same version: floor sitting at 0.78 m, an unknown posture reported,
`ground_height_m` allowed below the camera's floor, a clear sky letting a hard key through
haze, `HAND_HELD_RE` no longer reading "a hand's width" or "a palm tree", and approximators
no longer read as doubt in a recorded fact. `image_spec.py`, the contract test and the
contract doc byte-identical; 297 assertions passing unchanged, regression 4 of 4, review
example unchanged. The statement that no client brief reaches these paths was checked rather
than taken: none of the eighteen has a floor-seated or unknown posture, a negative ground, haze
with a clear sky, or a hand's width or a palm tree, and nothing moved on any of them.

No lite doc became false, and the audit to establish that found a gap in T4 itself. After the
last port it pinned every claim it contained to a constant or a behaviour, which is not the
same as pinning every claim the docs make. Of about ten behavioural sentences in the
`SKILL.md` anchor bullet and the `agent.json` rules it pinned four, the numbers. The
qualitative rules, that "above" or "below" is not part of the check, that no check runs
without a named person, that a width anchor and a hanging or mounted object are left alone,
and the lighting rule, had been true when written, checked by hand once, and pinned by
nothing, which is exactly the state the hand-held claim was in when it went false. D7 and D8
now pin all of them by behaviour. Four of the new checks assert that something passes, and a
pass can be luck, so each has a twin that differs only in the exempting feature and must be
refused; all four twins are refused, so each exemption is the reason its scene passes. T4 is
at 51 checks, up from 32, and its docstring now says what it covers rather than implying more.

TWELFTH PORT, `f88e7ef`, same version: four question templates that a real run answered "no"
on correct pictures, a grip no longer a finger-count fault, "placed here" for "stand here",
the one-floor question per surface, soft-focus questions only at three times the circle of
confusion, and `detect_as` on counted measures. `image_spec.py`, the contract test and the
contract doc byte-identical, and the review example regenerated from this edition's own
defaults, 80 questions, coming out byte-identical to the full edition's rather than copied.
316 assertions passing unchanged, regression 4 of 4, T4 green.

T4 pins numbers and rules, not question wording, so a green T4 said nothing about whether the
lite docs quoted the old templates. They were searched directly instead: no lite-owned file,
`SKILL.md`, `agent.json`, the pipeline `contract.md` or the orchestrator agent, quotes any
question template old or new; they describe the review only generically. On the real briefs
validation moved on none of the sixteen and the question count on seven of the clean ones,
which is the change doing what it says. probe2's one-floor check still passes and was read
rather than trusted: the regrouped question still says "one floor" because that scene has a
single grounded surface, and the held box now correctly drops out of it.

THIRTEENTH PORT, `cae8c4d`, same version: `detect_as` strips "es" only after sh, ch, x, ss
or zz, so "houses" is "house" and no longer "hous". Three files byte-identical; 320
assertions passing unchanged, regression 4 of 4, T4 green, review example unchanged.

The fix moves an error rather than removing it, measured on 28 plurals. "houses" and "buses"
have the same letter shape, so the rule that now gets "house" right turns "buses", "lenses",
"gases" and "canvases" into "buse", "lense", "gase" and "canvase"; and six are wrong under both
the old rule and the new, "cooky", "movy", "shelve", "knive", "leave" and "tomatoe". It is a
net gain, eighteen right where the old rule had sixteen, and on the real briefs every one of
the six plural object nouns comes out right, since all are plain "-s" plurals and none reaches
the ambiguous shapes. Reported upstream as a measured trade rather than a defect: a rule that
emits a singular only where the suffix is certain, and passes "-ses", "-ies", "-ves" and "-oes"
through as the plural, invents no non-word but keeps eight plurals the current rule gets
right. Which is better turns on whether the detector counts "houses" as well as "house", which
this edition has no measurement of; an explicit `detect_as` in the spec overrides either.

FOURTEENTH PORT, `1e2d475`, same version: `_IRREGULAR_PLURALS`, a table checked before the
suffix rule, for single-s stems, -ves, -oes, the -ies that keep their ie, and the old
irregulars. `image_spec.py` and the contract test byte-identical; the contract doc did not
change. 344 assertions passing unchanged, regression 4 of 4, T4 green, and the six corpus
nouns unchanged.

The 28 plurals this edition measured last port are now in the table and in the assertions,
so they are no longer independent evidence: a table passes the test it was built from. Two
checks it was not built from instead. First, the lookup is an exact word match, which is the
safe choice; a suffix match would have turned "olives" into "olife" through "lives" and
"sleeves" into "sleaf" through "leaves". Every such look-alike comes out right, and the only
misses are compounds of table words, "townspeople" and "firemen", which exact matching returns
as the real plural rather than inventing a word.

Second, held-out words outside the table, and the first attempt was biased. Drawn only from
the class where the suffix rule is wrong, smoothies, buffaloes, cactuses, thieves, it came out
17 of 17 misspelled, and read as a case for passing ambiguous plurals through unchanged. But for
every ambiguous shape the rule is wrong for one class and right for another, usually commoner
one: babies beside smoothies, waves beside thieves, shoes beside buffaloes. On a balanced set
of 33, both classes per shape and none in the table, the shipped design gets 19 right and
misspells 14, and gets every word of the rule-right class; passing the plural through gets
none right. The full edition's choice is the better one, and a sample built from the failing
class alone could only ever have said otherwise. What remains is the long tail outside the
table, which only more entries or an explicit `detect_as` reach.

FIFTEENTH PORT, `408c773`, same version: the five client-likely plurals this edition
suggested, buffalo, mosquito, smoothie, brownie and octopus, added to the table as exact keys,
and the look-alike set turned into assertions. `image_spec.py` and the contract test
byte-identical; the contract doc did not change. 354 assertions passing unchanged, regression
4 of 4, T4 green. All five new entries map correctly and all eight look-alikes stay untouched.
The five were drawn from the held-out set, so they are not held out any longer, and the better
score they give on it is not evidence of reach beyond the table.

BATTERY HARDENED against the one class it could not see. A probe that raises is not a probe
that fails: an exception aborts the run, so every probe after it never runs and the ones
before it look fine, which means a crash in the validator reads as a clean sheet. New
`battery.py` holds the shared harness, and every probe now reports a raise as a CRASH
verdict with its traceback, continues the run, and exits non-zero. A crash outranks every
other verdict, because a validator that raises on a live spec gives the caller no answer at
all rather than a wrong one. This was prompted by the sweep session hitting two live states
that crashed the validator, and it goes in before those fixes land rather than after, so the
battery can see them when they arrive.

- [2026-10-26] chore - v2.6.0 re-port of image_spec.py from the full edition, restoring byte-parity (DP-016, หมวด: image pipeline, ชม. แผน 1): `image_spec.py` and `image_spec_contract_test.py` taken verbatim from `ad2e1ad` on the full edition's `feat/dp-014-image-plausibility`, after the main session reproduced every battery finding in its own tree and implemented all of them there. The file now carries this edition's realism fixes plus the full edition's reference block for real places, `ground_height_m` for raised subjects, `eye_line_people`, `fits_in_frame`, and the framing-against-angle question split. The contract test runs here unchanged at 135 assertions, so parity is proven rather than assumed, and the regenerated review example drops from 73 spec questions to 68.

## [2026-10-26] chore - v2.6.0 re-port from the full edition (DP-016)

The direction was settled with the main session while this work was in flight: the full
edition is the source of truth, because the MCP and Pro editions are thin pointers served
from its bundle and inherit whatever is in it, so a fix written here and copied back would
invert that. This edition keeps the battery and reports; the full edition writes the module
and this edition takes it verbatim.

WHAT WAS TAKEN: `scripts/image_spec.py` and `scripts/image_spec_contract_test.py` from
`ad2e1ad`, byte for byte, plus the one fixture line in `content_pipeline_selftest.py` that
the new landmark check requires ("its top meets the worker at mid-thigh"). Neither script
carries a plugin-name reference, so no path edit was needed again.

PARITY PROVEN, NOT ASSUMED: the ported contract test passes here unchanged at 135
assertions, and `regression.py` is 3/3 including the end-to-end run to `publish_ready` on
WEBP and AVIF. The two edition-specific files are regenerated rather than copied:
`image-plausibility-review.example.json` is rebuilt from this edition's own `defaults.json`
and `review_template`, which is how the question-count change from 73 to 68 surfaced.

WHAT THE UPSTREAM FILE ADDS over the 2.5.0 local implementation: `spec.location.reference`
for scenes that depict a real place, with two-source corroboration, a fixed viewpoint
vocabulary, rights on every source and verified facts that reach both the prompt and the
review questions; `ground_height_m` per subject, so a figure on a stage does not inherit a
floor-standing eye line; `eye_line_people` covering everyone whose eye height is known,
measured against the height the pose gives rather than the stature; `fits_in_frame`, so a
ratio question is only asked where both entities are in the frame; framing split from
camera angle; horizon questions suppressed where the spec puts the horizon out of shot; and
`thigh` at 0.420 in the landmark table. The main session measured the effect of the last
group on a live client scene run twice through codex exec: unanswerable review answers fell
from 54 per cent of the set to 26.

WHAT THE LOCAL 2.5.0 IMPLEMENTATION DID DIFFERENTLY, now superseded: it intersected the
bands of every landmark an anchor named, where upstream takes the first landmark named as
the claim; it shifted the band by the hedge ("above the hip" meant higher than the hip)
where upstream uses a symmetric tolerance; and it resolved the anchor's referent by name,
declining to check when several people were in frame and none was named. Nothing it caught
is lost, and the differences are recorded in the report to the main session rather than
re-litigated here.

- [2026-10-25] feature - v2.5.0 realism checks on the image spec (DP-016, หมวด: image pipeline, ชม. แผน 3): a 25-case realism battery against a scene that validated cleanly moved the spec from 12 caught, 1 warned, 12 missed to 20 caught, 3 warned, 3 missed. `scale_anchor` is now checked against the person it names, using the standard stature fractions of Drillis and Contini (1966); seated and kneeling figures get the eye line that `standing_people` had excluded them from, stated in head heights; the focus subject of a whole-subject shot must fit the frame in width as well as height; a clouded sky cannot cast a crisp shadow and a fill with the key's power and hardness is refused as a second key; the object load limit counts declared items; and `support.by` for `held_by` no longer accepts an object id, which was a plain bug with an error message that contradicted it.

## [2026-10-25] feature - v2.5.0 realism checks on the image spec (DP-016)

Trigger: the owner asked to keep testing the spec until it is as realistic as it can be on
proportion, viewing distance, the human body, objects, lighting and location, and to settle
with the main session where the fixes land.

METHOD: one pharmacy scene that validates with 0 errors and 0 warnings, then 25 mutations
that each make it wrong in a way a reader would see, recording whether `validate_spec`
refuses it. The battery is the evidence for every line below; it began at 12 caught, 1
warned, 12 missed. Two of the original 12 catches turned out to be incidental, refused by
the `eye_level` rule rather than by any proportion check, so those probes were re-run at a
high angle to confirm the gap was real. One probe was mis-framed and corrected: an object
wider than the frame is ordinary when it runs out of frame, so the real gap was narrower
than it first looked and the check written for it is correspondingly narrow.

THE BUG: `support.by` for `held_by` and `worn_by` checked membership in `ids`, which spans
subjects and objects, so a carton held by a counter compiled while the error message said
the value had to be a subject id. One expression.

PROPORTION, the largest gap: `scale_anchor` is mandatory precisely because a size in metres
means nothing to an image model, yet nothing checked it. Now a landmark named in the anchor
is read off the person's `height_m` with `BODY_LANDMARK_FRACTION` (Drillis and Contini 1966
as tabulated in Winter, figure 4.1, the same measured family as `EYE_FRACTION`, whose 0.93
agrees with this table's 0.936 for the eye). Each landmark occurrence is read with the hedge
immediately before it, so "just above the hip, a little below her waist" intersects two
bands instead of one landmark winning; where loose prose yields bands that do not overlap,
the hull is used, because refusing a brief over phrasing would cost more than it catches.
With several people in the frame and no name in the anchor, no check runs at all. The check
earned its place immediately by refusing a wrong anchor in this edition's own self-test
fixture, written by hand an hour earlier: a 0.73 m desk top is at thigh height on a 1.7 m
person, not at the hip.

THE HUMAN BODY: `standing_people()` filters on `EYE_FRACTION`, so sitting, seated, kneeling
and lying figures were excluded from `horizon_crossings` entirely, removing the most
measurable cue in the module from most interview, desk and restaurant scenes. They now
derive `eye_line_offsets` instead, stated in head heights on the 7.5-head canon so the
reviewer can count them on the image with no external scale, each with a prompt clause and a
`verify_with: geometry` question. The `eye_level` tolerance tightens from 0.35 m to one head
height where nobody is standing, since 0.35 m is the spread of standing eye heights across a
population and a seated eye line is fixed by the seat instead; a mixed scene keeps the
standing band, and there is a test for that.

ALSO: the `focus_on` entity of a `full`, `wide` or `extreme_wide` shot must fit the frame in
width as well as height, which previously only standing people were checked for; a face
closer than 1 m is reported whatever the lens, because perspective distortion follows the
subject distance alone; `location.weather` is checked against the key's quality, since a
clouded sky covers the sun and becomes the largest soft source there is; a `fill` claiming
the key's power and hardness is refused as the second key it is; the object load limit counts
declared items rather than entries; and `support.by` is scanned for supports that hold
nothing, while `floats_in` is still allowed to float.

TESTS: `image_spec_contract_test.py` goes from 118 to 146 assertions, with a case per fix and
a guard per fix against the false positive it could cause - the example's own overcast window
and its own fills stay legal, an object that merely runs out of frame stays legal, a stature
comparison is not read as a landmark, and a one-letter entity id no longer matches as a
substring, which was a bug the new tests caught in the new code.

PARITY: `image_spec.py` is no longer byte-identical to the full edition's. That was
deliberate and agreed: lite carries the implementation and the battery, and the full edition
takes the file verbatim under DP-014, after which the two are identical again. Until it does,
the editions differ and the MCP and Pro editions inherit the full edition's older behaviour.

NOT DONE: a locale detail that contradicts the locale, such as snow on a Bangkok pavement,
is still only asked of the reviewer by the rubric's sociocultural check. Checking prose
against prose in code would cost more than it catches. The two items recorded under DP-015
are unchanged: root `plugin.json` version drift, and `images.spec.target_model` not reaching
`prompt_target` through `compile-spec`.

## [2026-10-25] feature - v2.4.0 image shot spec and plausibility gate (DP-015)

Trigger: the owner asked for the prompt and image logic of every rainmojo-so edition to
check people and objects for physical and logical correctness, with camera angle and
size-by-distance stated, and for the prompt spec to be as detailed as it can be. The full
edition shipped that as DP-014 in 3.21.0; the MCP and Pro editions inherit it because their
image skills are thin pointers into the full edition's bundle. Lite is the only other
edition that carries its own copy of the pipeline scripts, so it needed a real port.

PORTED AT PARITY: `image_spec.py` is byte-identical to the full edition's module, including
the comments that carry the measured research behind each rule. Its `REFERENCE_DIR` resolves
relative to the script's own parent, so it needed no path edit under
`skills/rainmojo-so-lite/`. `image_spec_contract_test.py` is identical too, and all 118 of
its assertions pass here. The `images.spec` and `images.plausibility` blocks, the schema
additions and the `image-model-registry.json` rows are the same data.

WHAT GATES NOW: `image_specs_ready` is refused while any generated image lacks a valid,
freshly compiled spec; the images stage of `validate_package` checks the same freshness;
`process` is refused when the prompt has drifted from its spec; `mark-reviewed --status
passed` is refused unless every rubric check and every spec question is answered with
evidence, `crops_reviewed` reaches `zoom_grid` squared, and the review names the sha256 of
the file that shipped.

WHERE THE INSTRUCTIONS LIVE: lite has no `seo-image-production` skill (images belong to
`content-production-lite`), so the spec workflow, the two hard rules (say what the picture
is and never what it is not; the quiet area is a thing in the scene), the `verify_with`
instruction to measure rather than judge, and the rule that the prompt is compiled and never
authored are in `skills/content-production-lite/SKILL.md` and its `agent.json`. The spec gate
is also stated in `reference/content-production/contract.md` beside the content-review gate.

TESTS: `image_spec_contract_test.py` (118 assertions) and a new `content_pipeline_selftest.py`
that drives one package from `planned` to `publish_ready` on both WEBP and AVIF: fill a spec,
compile it, refuse a spec with no compiled record, refuse a spec that contradicts itself,
refuse a hand-edited prompt, approve the source, process, cut the 3x3 crops, refuse an
unanswered plausibility check, answer the review, pass the publish gate. Lite had no
regression harness at all, so `scripts/regression.py` was added as the one entry point and
runs all three packaged tests.

EXAMPLES GENERATED, NOT COPIED: `image-plausibility-review.example.json` is built from lite's
own `defaults.json` and `image_spec.review_template`, so its 30 rubric checks and 73 spec
questions cannot drift from what `review-template` writes. It came out identical to the full
edition's file, which is the expected result since the rubric data is the same.
`image-spec.example.json` is the full edition's worked two-person pharmacy scene, verified to
validate and compile under lite with no errors and no warnings.

NOT DONE: no `aiso-task-completion` equivalent and no new skill, per the lite scope. Root
`plugin.json` still reads 2.2.0, a version drift that predates this change and that agentpack
does not manage. `images.spec.target_model` cannot change `prompt_target` through the
`compile-spec` command: `compile_specs` passes the client config's value, substituting
`negative_prompt` even when the key is absent, so the registry's `prompt_target` is only
honoured when `image_spec.compile_spec` is called directly with an empty target. The full
edition behaves the same way; it is recorded here rather than fixed, because fixing it would
put the two editions out of parity.
