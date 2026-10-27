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
- [2026-10-25] feature - v2.5.0 realism checks on the image spec (DP-016, หมวด: image pipeline, ชม. แผน 3): a 25-case realism battery against a scene that validated cleanly moved the spec from 12 caught, 1 warned, 12 missed to 20 caught, 3 warned, 3 missed. `scale_anchor` is now checked against the person it names, using the standard stature fractions of Drillis and Contini (1966); seated and kneeling figures get the eye line that `standing_people` had excluded them from, stated in head heights; the focus subject of a whole-subject shot must fit the frame in width as well as height; a clouded sky cannot cast a crisp shadow and a fill with the key's power and hardness is refused as a second key; the object load limit counts declared items; and `support.by` for `held_by` no longer accepts an object id, which was a plain bug with an error message that contradicted it.
- [2026-10-26] chore - v2.6.0 re-port of image_spec.py from the full edition, restoring byte-parity (DP-016, หมวด: image pipeline, ชม. แผน 1): `image_spec.py` and `image_spec_contract_test.py` taken verbatim from `ad2e1ad` on the full edition's `feat/dp-014-image-plausibility`, after the main session reproduced every battery finding in its own tree and implemented all of them there. The file now carries this edition's realism fixes plus the full edition's reference block for real places, `ground_height_m` for raised subjects, `eye_line_people`, `fits_in_frame`, and the framing-against-angle question split. The contract test runs here unchanged at 135 assertions, so parity is proven rather than assumed, and the regenerated review example drops from 73 spec questions to 68.
- [2026-10-26] chore - v2.7.0 re-port from f632e00, carrying the six findings this edition reported (DP-016, หมวด: image pipeline, ชม. แผน 1): `image_spec.py`, `image_spec_contract_test.py`, `image-spec.example.json` and the new `image-spec.real-place.example.json` taken byte-identical from the full edition, plus the `spec-template --reference` flag in `image_production.py`. The contract test runs here unchanged at 169 assertions and `regression.py` is 3/3. The regenerated review example comes out byte-identical to the full edition's while being built from this edition's own defaults and generator, and the contract test now asserts it against the compiler so it cannot drift again. Upstream carries all six findings, three of which were bugs that refused correct briefs, plus `spec.realism.imperfections` and four lint rules.

## [2026-10-26] chore - v2.7.0 re-port from f632e00 (DP-016)

Closed with PR #6 (biqdaddy-dev/rainmojo-so-lite#6), shipping in v2.7.0. หมวด: image pipeline. Started 2026-10-25 (the v2.5.0 row), finished when PR #6 merges, which is the owner's call. Planned 5 hours across its three rows (3, 1 and 1); actual 8.0 hours of active work and 5440k tokens, measured from this session's transcript as the PR description states: gaps of ten minutes or less between events, and input, output and cache writes, a lower bound by two compaction calls.

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

SIXTEENTH PORT, `fabb04a` and `2034115`, same version: run 02's question fixes, the height
question only for a whole standing figure, an out-of-frame support as a leaves-frame
question, position and crop safety measured; two new warnings; `subject.reference` for a
likeness's provenance; and a rights gap closed, where a legacy reference image on a brief whose
place is marked not real reached the generator unchecked. `image_spec.py`, the contract test
and the contract doc byte-identical, and the review example regenerated from this edition's
own defaults, 78 questions, byte-identical to the full edition's. 376 assertions passing
unchanged, regression 4 of 4, T4 green.

The two doc risks flagged upstream were searched directly, since T4 pins neither question
wording nor the reference rules. No lite-owned doc mentions `reference_image`,
`location.reference`, `subject.reference` or a likeness, so nothing said a reference image
needs `location.reference`; the "identity" in the pipeline `contract.md` is the reviewer's and
a raw source's provenance hash. No doc makes a claim about the height question; the `height_m`
mentions are field requirements and the anchor reading, both still true.

On the real briefs nothing moved, errors or warnings, and nothing reaches the new paths: no
brief has a subject reference image, a reference block whose place is not real, a person on a
declared object at ground height zero, or an avoid entry naming a provenance. The last of those
four reach checks guessed the trigger words; the diff, which shows the warning firing on none of
the eighteen, is the definitive evidence. Both warnings and the rights fix are vouched for by
the contract test alone.

SEVENTEENTH PORT, `6b2a3d8`, `0e0d9ec` and `ba30c4c`, same version. Every recorded reference
may condition the generator, a reference-only source warning instead of being refused, by the
owner's own decision, given directly in the full edition's session; this reverses the per-image rights refusal
this edition argued for, and is ported as written. Height ratios only between things whose
`height_m` is their upright measure; the standing eye-level line only for people on the
camera's floor; likeness, distinct-faces and per-copy variation warnings and questions; and a
count that no longer counts contents. Five files byte-identical, the review example
regenerated from this edition's own defaults and byte-identical at 79 questions, the
real-place example ported. 407 assertions passing unchanged, regression 4 of 4, T4 green.

The doc checks were searched, then tested. No lite-owned doc says a reference-only source may
not condition the generator. No lite-owned doc mentions ratios: a search for "ratio" returns a
dozen lines, every one the substring inside "configuration", "operation" or "generation", and a
count of hits would have said the opposite. One sentence touches the eye line, `agent.json`'s
"a seated or kneeling figure still has an eye line, and in an interview or desk scene it is the
only one". It is still true, since the narrowing is to the standing eye-level line and not to
per-figure crossings, but only its 0.15 m band was pinned. D9 now pins the clause itself: with
nobody standing, every seated person gets a horizon crossing and a measured question; with
seated people simulated out of the eye line it fails on both, so it can catch what it is for.
T4 is at 54 checks.

The new warnings, read one by one. On the client briefs nothing new is refused, the compiled
prompt changes on seven, adding the distinct-faces clause, and new warnings fire on seven
briefs, thirteen warnings in all. Eleven are true positives: groups of people from one
description, which come out with cloned faces; two fighters described in 81 per cent the same
words; and desks, chairs, tables, scooters and produce trays, which really do differ in angle,
wear and contents. Two give advice that would make the picture less real. The solar array's own
invariants put its panels on one rail at one tilt and give each the same size, and its state
already describes the variation that is right, dust on the low edge and a leaf caught on one
panel; the warning still asks for the panels to differ in size and angle. The tiger sculptures
are a moulded matched pair, and varying their size would be wrong. The warning's trigger is a
missing `variation` field, not missing variation, and its justification, that even identical
stock differs in wear and angle, is false for stock mounted at one tilt. A `variation` answer
silences it, so the cost is the advice text, reported upstream. Seven briefs, not the eight
quoted upstream; the shipped examples raise none, and the eighth was likely the real-place
example's fighters, which the same commit made distinct.

EIGHTEENTH PORT, `6363533`, same version: a matched set by design is not a copy. Two of the
seventeenth port's warnings told a solar array on one rail and a moulded pair of sculptures to
differ in size and angle. `variation` now accepts "matched" (identical, uniform, alike by
design, a matched set): no warning, a prompt clause saying the set is matched with each in its
own place and light, and a question about place, light, shadow and perspective, never about
difference. The warning for an unsaid variation offers "matched" and no longer prescribes size
and angle. People cannot be matched, by the owner's rule, and are warned. Three files
byte-identical, 418 assertions passing unchanged; the review example regenerates
byte-identical, since its scene has no repeated object. Regression 4 of 4, T4 green: no
lite-owned doc mentions variation, so nothing new to pin.

On the client briefs the same thirteen warnings fire, reworded; no error, no prompt changes,
since no brief says "matched" yet, and five question sets drop "angle". Declaring the solar
array and the tigers matched silences both and compiles the intended clause. Two findings,
reported upstream. A variation that opens with a matched word and then describes a difference,
"identical model, one with a cracked corner", "all the same model, one bent", "alike by design
but one repainted", is classed matched and the difference is dropped from prompt and question
without a word; the match is on the opening words only. And people declared matched are warned
but the prompt still writes "Each of the 2 differs: matched". Older, not from this commit: a
counted name that is itself a collective, "pair of moulded tiger sculptures" at count 2, "row of
framed photovoltaic panels" at count 5, compiles to "2 pair of" and "5 row of" in the prompt and
the questions, which reads as four sculptures and five rows.

NINETEENTH PORT, `27c0015`, same version: an open anomaly question and a failure library.
`q_anomalies` asks, after everything else, whether the image is free of anything a careful
viewer would find wrong, with each fault listed in the evidence on a no.
`image-failure-classes.json` is new here: 16 named fault classes, each with symptom, cause,
prevention, detection and regression, closed only with all three and a prevention not
measured to fail. C47 and C48 come with it, and C48 reads the contract test's own source, so
it holds only while that file is identical. Five files byte-identical, the new one included;
the review example regenerates byte-identical at 80 questions. 606 assertions passing
unchanged, regression 4 of 4, T4 green. The lite docs need nothing: step 6 already asks
every spec question `yes` with evidence and treats a `no` as a failed image, which is right
for this question too, and nothing in lite reads the library at run time.

On the client briefs nothing else moves: no error, no warning, no prompt changes, and each of
the fifteen clean briefs gains exactly one question, this one. Battery and corpus identical to
a clean export of 27c0015, 16 of 19 clean, the same three refused.

Read rather than counted, three findings, reported upstream. `q_anomalies` is said to end
every review, and C47 is titled so, but it is second to last: `q_no_text` follows it, and C47
checks only that it is present. C48 checks that each cited regression section exists, not that
it tests the class: `F-unwanted-text` cites C9c, which tests the plain-language words for focal
length, aperture, colour temperature and shot size and never mentions text; C8, C20 and C36 are
the sections that do. Two other citations, C41 for the wrong floor and C37 for face distortion,
test the prevention rather than the detection, which is a fair reading of a regression. And the
library's own `about` says rainmojo-so and rangsarn each keep a copy, which this edition now
also does; the line is ported as written, byte-identical as asked. The matched-prefix finding
from the eighteenth port touches the library: `F-copied-repeats` lists "matched" as a
prevention, and the prefix match drops a described difference.

TWENTIETH PORT, `fce4562`, same version: a level camera does not look down, and locale facts
come early. The looks-down sentence now needs a downward tilt, a high angle or the lens more
than 0.5 m above a head, recorded per crossing as `above_head_by_m`, and never sits beside an
eye-level angle; otherwise the prompt says the camera is level and a little above their eyes.
The locale group moves to just after the opening. Three files byte-identical, 611 assertions
passing unchanged, the review example regenerates unchanged at 80. Regression 4 of 4, T4
green. The lite docs describe neither prompt order nor the looks-down sentence; the one
eye-line sentence, above a seated eye line the camera is a high angle with the 0.15 m band
for nobody standing, still holds and is already pinned by D4.

On the client briefs validation is unchanged. Fifteen prompts change: twelve are reordered
only, ten client briefs and the two shipped examples, and three replace the looks-down
sentence, bangmod, doctorjay and pulseth, the three named upstream. The new sentence is true
on all three: the lens is 0.03 to 0.13 m above the nearest head, 3 to 7 degrees down to the
eyes. Battery and corpus identical to a clean export of `fce4562`, 16 of 19 clean.

Three findings, reported upstream. A valid spec still compiles two contradictions of the kind
this commit fixes: eye-level, tilted down, horizon above the frame, all seated, lens 0.10 to
0.14 m above their eyes, inside the 0.15 m band. The prompt says "the camera is level ... the
horizon passes just above their heads" and, a sentence later, "held down", with the horizon
declared above the frame. The level sentence checks the angle but not the tilt. The contract's
new paragraph says the locale follows the opening, and the paragraph after it still says groups
come out "subject and action first", as does the comment over `GROUP_ORDER`. And, older: in an
indoor scene declared `horizon: not_visible`, the prompt names a horizon three times; the
looks-down sentence used to as well, so this is not new, but "eye line" would not invite a
window or a skyline.

TWENTY-FIRST PORT, `a57d0ef`, same version: the viewpoint sentence knows the tilt, and an
unseen horizon is an eye-level line. It fixes the twentieth port's three findings and one more
of their shape: an eye-level camera tilted down "tips slightly down toward them" instead of
being called level; with the horizon out of frame the camera sentences say "eye-level line";
the contract and the comment over `GROUP_ORDER` give the real order, opening, locale, then
subjects; and the camera-at-eye-height sentence names only the people on the camera's floor,
as its question has since `0e0d9ec`. Three files byte-identical, 615 assertions passing
unchanged, review example unchanged at 80. Regression 4 of 4, T4 green, no lite doc touched.

The test's word-boundary regex was checked in bytes, since the full edition's first draft of
it lost `\b` to a heredoc: the committed file holds a backslash and a b, and no backspace
byte. C50 was then run against `fce4562`'s module, the twin that must fail: the tilt and the
indoor checks fail there as they should, but the eye-height check passes on the old code too.
It asserts that "eye height of the older customer" is absent, and the old sentence said "the
standing people" and never named anyone, so it is absent either way. Its fixture, the customer
raised 0.8 m, is also refused by `validate_spec`. The fix itself is right and reachable: with
the customer raised 0.3 or 0.5 m, both valid, the sentence names the pharmacist alone.

On the client briefs validation is unchanged. Five indoor prompts go from two or three
"horizon" mentions to none, bangmod, biqdaddy, doctorjay, inlingua and theklinique, and the two
with a visible horizon keep theirs, as upstream says; three more now name the people in the
eye-height sentence. Battery and corpus identical to a clean export of `a57d0ef`, 16 of 19
clean.

Two findings, reported upstream. A fifth of the same shape, on a real brief: pulseth's prompt
says the camera is "a little above the eyes of the vendor, so the horizon passes just above
their heads", then "the camera stands at the eye height of the vendor and the two walkers, so
that horizon line crosses their eyes". The lens is at 1.6 m and the vendor's head top at
1.55 m, so the first is true and the second is not; the eye-height sentence names every
floor-standing person, including one its own crossing puts below the line. It was wrong
before this commit too, as "the standing people", but now it names the vendor. And the
validator's eye-level band still averages in people off the camera's floor: a level camera at
the floor people's eye height is refused once someone stands on a 0.8 m platform, the question
narrowed at `0e0d9ec` and the prompt here, the validator not yet. Whether that is intended is
upstream's call.

TWENTY-SECOND PORT, `5e87963`, same version: the horizon meets only the eyes it can meet. It
fixes the twenty-first port's findings. `eyes_on_horizon` returns the standing people on the
camera's floor whose eyes are within 0.15 m of the lens, `EYE_LINE_BAND_M`, and the
eye-height sentence and `q_eye_line` both use it, so pulseth names the two walkers and not the
vendor whose head is below the lens. The validator's eye-level mean uses the people on the
camera's floor, so a platform at 0.8 m no longer refuses a level camera at floor eye height.
Two files byte-identical, the contract doc unchanged; 620 assertions passing unchanged, the
review example unchanged at 80. Regression 4 of 4, T4 green.

The new guards were run against `a57d0ef`'s module. The test as a whole stops there with an
AttributeError at `eyes_on_horizon`, which is a failure but hides whether the later guards
discriminate, so they were run by hand: on the old code the 1.4 m teenager is named in both
the prompt sentence and `q_eye_line` and the 0.8 m platform is refused as not eye level; on
the new code neither. The valid 0.3 m raise that replaced the refused 0.8 m one guards the
previous commit's fix, since `a57d0ef` already names the pharmacist alone there. The teenager
scene, though, is refused by `validate_spec` on both versions, for a reason unrelated to the
eye line: the copied subject keeps the customer's foreground plane while standing behind the
midground pharmacist. With its plane set to midground the scene is valid and the guard gives
the same answer both ways, so the fix is right and the fixture only needs the plane and a
validity check, as the 0.3 m raise already has.

On the client briefs validation is unchanged and only pulseth moves: its eye-height sentence
and `q_eye_line` name the two walkers. Battery and corpus identical to a clean export of
`5e87963`, 16 of 19 clean. The one lite sentence on the band, "with nobody standing the
eye_level band is 0.15 m", still describes the code.

One finding, reported upstream. The mean now counts the camera's floor, but the band width
does not: it is 0.35 m whenever anyone stands, on any floor. With the pharmacist on a 0.8 m
platform and the seated customer the only person on the camera's floor, a lens 0.30 m above
the customer's eyes is accepted as eye level, where the seated rule gives 0.15 m. It was
accepted before this commit too, through the old mean, so it is not a regression; the band
would follow the mean if it asked whether anyone stands on the camera's floor.

TWENTY-THIRD PORT, `ab09d23`, same version: rangsarn's run 04. A count of a thing supported by
a declared entity is counted there, "held by the pharmacist"; a horizon crossing on a figure
the frame cuts is asked at the nearest body landmark within 0.06 of stature, or not at all;
scale questions say to judge real sizes; the review instructions say a child question is
skipped only when its parent thing is absent; and the failure library grows to 21 classes, 11
open. Five files byte-identical, the review example regenerated here and byte-identical to the
full edition's, 80 questions. 681 assertions passing unchanged, regression 4 of 4, T4 green.
Lite's step 6 needs nothing: a review that skips a child because its parent is absent has
already failed on the parent.

On the client briefs validation and prompts are byte-identical. Questions: three counts are
scoped, bangmod's aligner tray, doctorjay's hand mirror and theklinique's handpiece, plus the
shipped example's carton, which makes the four upstream counts; and 61 scale questions gain
the real-size sentence. The crossings do not move as upstream says. Of the fifteen crossings in
the client briefs, ten are on figures the frame cuts, but every one of the ten is in a scene
whose horizon is out of frame or above the head, and none had a crossing question before this
commit or has one after. The only crossing questions that change are the two in the shipped
example, which go from 96 and 92 per cent to "at about the eyes". Battery and corpus identical
to a clean export of `ab09d23`, 16 of 19 clean.

Two findings, reported upstream. A snapped landmark is not checked against the frame: the
shipped example at a low angle, lens 0.86 m, is valid, framed from the waist up, and asks
"Does the horizon cross the pharmacist at about the hips?", with the hips below the frame;
the same question at the waist sits on its edge. And the prompt still tells the generator
"about 53 per cent of the way up from the feet" for the same cut figures, so prompt and
question disagree again; on the corpus five cut figures carry a per-cent sentence in the
prompt, bangmod's dentist, both biqdaddy figures and inlingua's teacher and nearer learner.
The two landmark tables agree value for value, `CROSSING_LANDMARKS` restating
`BODY_LANDMARK_FRACTION`.

TWENTY-FOURTH PORT, `457f9cc`, same version: a crossing landmark must be in the picture, and
the head must be. Each horizon crossing records `lowest_visible_fraction`, the lowest part of
that person the frame shows, from their distance, the frame height there, the lens height and
where the horizon sits in the frame; a landmark must sit `LANDMARK_MARGIN`, 0.05 of stature,
above it, or the crossing is not asked. The prompt now describes a cut figure's crossing at
the same landmark as its question, or says nothing. A level camera whose frame top falls
below the focus person's head is warned. `CROSSING_LANDMARKS` is built from
`BODY_LANDMARK_FRACTION`. Three files byte-identical, 688 assertions passing unchanged, the
review example unchanged at 80. Regression 4 of 4, T4 green.

A correction to the twenty-third port's finding, made upstream and confirmed here: the
low-angle case did not ask about hips below the frame. At a 0.86 m lens with the horizon in
the middle the frame at the pharmacist's 2.2 m is 0.83 m tall, 0.44 to 1.28 m, so her hips at
0.86 m are in it and her head at 1.62 m is not. The finding read "framed from the waist up" as
where the frame cuts, and the shot type was what the geometry contradicted.

On the client briefs validation is unchanged and only the five cut figures move, at the
landmarks upstream names: bangmod's dentist at the chin, biqdaddy's strategist and client at
the eyes, inlingua's teacher at the chest and nearer learner at the eyes. All five landmarks
lie inside the frame a level camera gives at each person's distance. Battery and corpus
identical to a clean export of `457f9cc`, 16 of 19 clean.

The battery broke on its own needle, not on a defect: `realism_probe2.py` looked for "per
cent of the way up" for the adult, whom the frame cuts at the waist, and the prompt now says
"crosses the pharmacist at about the eyes". The probe accepts either wording and passes on
`5e87963`, `457f9cc` and this edition; with the landmark sentence removed from a copy of the
compiler it reports MISSING and exits 1.

Two findings, reported upstream. Both new frame checks run only for a horizon in the frame,
and skip `not_visible`, but a level camera puts the horizon through the frame centre whether
or not a wall hides it, as the validator itself says when it refuses upper or lower third
with a level tilt. So the frame's vertical extent is known for every level indoor scene, the
cut figures are mostly indoors, and the shipped example at a 0.86 m lens with the horizon
`not_visible` is valid with no head warning. And the probe's scene was impossible all along:
a 1.02 m child at 2.2 m, placed "lower right of the frame", sits wholly below a frame whose
bottom edge is at 1.13 m, `lowest_visible_fraction` 1.08. The spec raises no error or warning,
and the review asks whether the horizon passes above the head of a child who cannot be in the
picture. The new field makes that a one-line rule: a declared person with a lowest visible
fraction of 1 or more is not in the frame.

TWENTY-FIFTH PORT, `e92bb52`, same version: a level camera's frame is known indoors, and a
person outside it is warned. `horizon_band` places the horizon row at the frame centre for a
level camera with the horizon not visible, and both `_lowest_visible` and the head-cut
warning use it; every declared person is checked against the frame at their own distance and
warned when they lie wholly below or above it. Three files byte-identical, 693 assertions
passing unchanged, the review example unchanged at 80. Regression 4 of 4, T4 green. On the
client briefs validation, warnings and prompts are unchanged, as upstream says. Battery and
corpus identical to a clean export of `e92bb52`, 16 of 19 clean.

The guards, run by hand against `457f9cc`: the indoor 0.86 m lens is silent there and warned
here, and the 1.02 m child at 2.2 m is silent there and warned here. Both C53 child fixtures
are refused by `validate_spec` on both versions, though, with the plane-order error the C50
teenager had: copying the foreground customer and placing the copy at 2.2 m behind the
midground pharmacist. With the plane set to midground the scene is valid and the guard gives
the same answer both ways, so the rule is right and the fixtures need the plane and a validity
check. The same copy pattern has now produced an invalid fixture twice.

The battery moved for the wrong reason. `realism_probe.py` went from 21, 2, 4 to 21, 3, 3, and
the new WARNED was the case "a 1.02 m child and a 1.62 m adult", whose point is the horizon
derivation: it was warned because its child stood wholly below the frame, which says nothing
about the derivation, and the probe's verdict counts any warning. The scene was the impossible
one the twenty-fourth port found. Both probes now place the child at 3.4 m, where the frame's
bottom is at 0.88 m and the top of the child is in it, standing by the shelving with hands at
the sides, since a child 1.5 m behind the counter cannot grip it. The scene is valid and
unwarned on `457f9cc`, `e92bb52` and this edition, the case is MISSED again for its own
reason, 21, 2, 4, and probe 2 still finds the crossing above the child's head and the adult's.

One finding, reported upstream, a limit rather than a regression: a seated child is not
caught. The geometry gives every seated person the adult seated eye height, 1.23 m on a chair,
"whatever the stature", so a seated 1.02 m child is placed with a head at 1.32 m, inside a
frame whose bottom is at 1.10 m, and the wholly-below warning does not fire, where the child's
real head is well below that edge. ANSUR II is an adult survey; a seated eye height scaled by
stature below adult height would close it.

TWENTY-SIXTH PORT, `015d13b`, same version: seated eye height scales with stature, and test
scenes must be valid. `posture_eye_m` keeps the absolute heights for a 1.65 m adult, scales
the body's share with stature, keeps a 0.45 m chair seat fixed and leaves lying flat unscaled:
a seated 1.02 m child's eyes come out at 0.93 m, a 1.85 m adult's at 1.33 m, a floor-seated
child's at 0.48 m. The C50 teenager and both C53 child scenes take the midground plane and
assert their validity first. Three files byte-identical, 701 assertions passing unchanged,
the review example unchanged at 80. Regression 4 of 4. Battery and corpus identical to a clean
export of `015d13b`, 16 of 19 clean, 21, 2, 4.

The seated child, valid with the midground plane, is silent on `e92bb52` and warned wholly
below here. No lite doc quotes 1.23 m, 0.78 m or "whatever the stature", so no claim became
false. T4 passed, but D4 had been passing for a reason that no longer held: it put the lens
0.14 and 0.16 m from `EYE_ABSOLUTE_M["sitting"]`, the 1.23 m constant, and with seated heights
now scaled that constant is nobody's eye height. It landed on the band edge only because the
example's two statures, 1.62 and 1.68 m, average exactly the 1.65 m reference. D4 now measures
from the seated people's own mean eye height, as its standing half already did. With the
example's statures changed to 1.45 and 1.50 m in a copy, the old D4 fails on a correct band and
the new one passes; T4 green, 54 checks.

On the client briefs validation is unchanged and two prompts move. biqdaddy's strategist is now
crossed at the chin, as upstream says. doctorjay moves twice, not once: the patient, eyes at
1.20 m, is the one named in "level and a little above the eyes", and the 1.73 m surgeon, eyes now
at 1.27 m, goes from "passes above the head" to "crosses at about the eyes", which drops his
`q_viewpoint_surgeon`.

That dropped question exposes a finding, older than this commit and reported upstream. Indoors,
with the horizon out of frame, `q_viewpoint_<id>` asks "seen from above, so that the tops of the
shoulders and head show" of anyone whose head is below the lens, by any margin. That is the test
`fce4562` replaced in the prompt with a downward tilt, a high angle or more than 0.5 m of
clearance, never beside an eye-level angle, and the question was not changed with it. Two client
briefs carry the contradiction now: bangmod and doctorjay both tell the generator the camera is
level and the patient's face is seen straight on, and then ask the reviewer whether the top of
her head shows. A correct picture answers no. The question wants the same predicate as the
sentence.

TWENTY-SEVENTH PORT, `86cf0d1`, same version: one looks-down test for the prompt and the
viewpoint question. `camera_looks_down` decides both, a downward tilt, a high angle or the lens
more than 0.5 m above the head, never an eye-level angle, with `HIGH_ANGLES` a constant; a level
camera a little above someone's eyes is asked whether their face is seen nearly straight on.
Two files byte-identical, the contract doc unchanged; 705 assertions passing unchanged, the
review example unchanged at 80. Regression 4 of 4, T4 green. The prompt side is a refactor
that keeps every branch: the names it lists and the sentence it chooses are the same as before
in each case. C55's valid indoor scene asks `from_above` of both people on `015d13b` and
`straight_on` here. On the client briefs validation and prompts are byte-identical and exactly
the two patient questions change, bangmod's and doctorjay's, and no other. Battery and corpus
identical to a clean export of `86cf0d1`, 16 of 19 clean, 21, 2, 4, every probe output
unchanged since the last port.

One finding, reported upstream, in the prompt since `fce4562` and now in the question too:
"never an eye-level angle" applies the angle to everyone, but eye level is measured on the
standing people on the camera's floor. A valid scene: the shipped example at 35 mm, medium-wide,
horizon not visible, with a floor-seated vendor in frame at 3.0 m beside the two standing
people. The lens is at 1.55 m, her eyes at 0.76 m, her head 0.74 m below the lens, about fifteen
degrees down to her eyes. The prompt says the camera is "level and a little above the eyes of
the vendor", and the review asks whether her face is seen nearly straight on with the top of
her head barely visible. Both are false for that picture, and it is a common one, vendors on
the floor or in a boat with buyers standing. The eye-level veto would hold if it applied only
within the clearance, so that more than 0.5 m above a head looks down whatever the angle says.

TWENTY-EIGHTH PORT, `963cc7d`, same version: an eye-level label is the standing people's, and
a head far below is seen from above. `camera_looks_down` returns true whenever the lens is more
than 0.5 m above a head, whatever the angle, so the eye-level exemption holds only within that
clearance; and the opening writes both sentences when a scene has both groups, where one
looking-down person used to silence the other. Two files byte-identical, 709 assertions
passing unchanged, the review example unchanged at 80. Regression 4 of 4, T4 green; no lite
doc touches it. On the client briefs validation, warnings, prompts and questions are all
byte-identical. Battery and corpus identical to a clean export of `963cc7d`, 16 of 19 clean,
21, 2, 4, every probe output unchanged since the last port.

Checked on the twenty-seventh port's own scene, the floor-seated vendor at 3.0 m in the
midground: on `86cf0d1` the prompt calls the camera level and a little above her eyes and the
question asks straight on; here the prompt says it is higher than her and looks down, and the
question asks from above. And on a scene with both groups, a standing pharmacist, a customer
on a stool 0.11 m below the lens and the vendor 0.64 m below it: `86cf0d1` called the camera
level and a little above both of them and asked straight on of both; here the prompt writes the
looks-down sentence for the vendor and the level sentence for the customer, and each person's
viewpoint question agrees with the sentence that names them. Nothing new to report.

TWENTY-NINTH PORT, `ded0d5e`, same version: hands one at a time, contents from their source,
nothing said twice, from the owner's reading of rangsarn's run 05. When a hands field names
both sides each hand is asked on its own, `q_<id>_hand_left` and `_right`, with the picture
side from `facing()`, and a person facing away is told their own right hand is on the right
of the picture; an object may declare `filled_from`, compiled into a prompt clause and a
`q_<id>_contents` question, unknown ids refused; and an object whose state names, as a single
thing of its own, what a hand holds is warned. The failure library has 24 classes, 11 open.
Four files byte-identical, 754 assertions passing unchanged, the review example unchanged at
80. Regression 4 of 4, T4 green; the lite docs say nothing about sides of the body. Battery and
corpus identical to a clean export of `ded0d5e`, 16 of 19 clean, 21, 2, 4, every probe output
unchanged since the last port. On the client briefs validation and warnings are unchanged, the
held-thing warning fires on none, and only theklinique moves, as upstream says.

Read rather than counted, theklinique's move is a false positive, and it is the corpus's only
case. `facing()` reads its practitioner as facing away because her position says "leaning in
from behind the head of the bed", which is where she stands; her pose is "shoulders square to
the client face" and the brief's own composition puts "her masked face on the right third", so
the camera sees her face. The prompt now tells the generator she has her back to the camera,
and the two new hand questions name the picture sides a face-on picture would mirror, so a
correct picture answers them no. The pattern is wider than this brief: `FACING_AWAY_RE` matches
a bare "from behind" and "turned away" anywhere in position, pose, description or gaze, and of
six ordinary phrases for a person facing the camera, five came out away: "looking out from
behind the counter", "lit from behind by the shop window", "head turned away from the glare",
"turned away from the shelves", "stepping out from behind the screen". A backlit pharmacist
facing the lens, with a pen in one hand and a slip in the other, compiles "has their back to
the camera". Reported upstream: the away words want the camera or lens as their object, "back
to the camera", "facing away from the camera", "seen from behind", and a camera word should win
over a bare "from behind". Smaller, also reported: `held_things` singularises by dropping a
final s, so "reading glasses" becomes "glasse" and "scissors" "scissor", and a pair held and
named again on the counter is not warned. The hand parser itself read eight phrasings right,
both sides or none.

THIRTIETH PORT, `381b628`, same version, three small fixes rangsarn found in `ded0d5e`: the
`filled_from` clause drops its trailing negation, `held_things` drops trailing pronouns and
prepositions back to the noun, so "holds her fork beside it" holds a fork, and `possessive()`
puts her or his into the facing sentence and the hand questions. Two files byte-identical, 758
assertions passing unchanged, the review example unchanged at 80. Regression 4 of 4, T4 green.
Battery and corpus identical to a clean export of `381b628`, 16 of 19 clean, 21, 2, 4, every
probe output unchanged. On the client briefs only theklinique moves, to "her own", as
upstream says.

Two findings, reported upstream, neither reaching the corpus beyond theklinique, which reads
"her" correctly. `possessive()` counts every her and his in the hands, pose and action text,
including the other person's: a male dentist whose text reads "his right hand holds the mouth
mirror inside her mouth, his left hand holds her chin", action "examines her teeth", comes out
"her", and so does "his right hand lifts her arm, his fingers under her elbow and her wrist";
a male clinician with a female patient is an ordinary clinic brief. Counting only the
possessive directly before a hand, "his right hand", "her fingers", would read the person's own.
And `held_things` drops prepositions only from the end: "grips his phone near his ear" and
"holds a pen behind his ear" both yield "ear", so a phone or pen said twice on the desk would
not be warned; cutting the phrase at its first preposition keeps the thing held. The
twenty-ninth port's finding is untouched: `facing()` still reads theklinique's practitioner,
whose face the brief puts in frame, as facing away, and her prompt now says "her back".

THIRTY-FIRST PORT, `d90b24e`, same version: an invariant is checked part by part, and a size
comparison in real size, from rangsarn's run 08, where a serving spoon's invariant passed on
its bowl while its handle rested on another plate. Every invariant question now says to check
each part on its own, answer yes only if every part holds and name each part in the evidence,
and one that matches `SIZE_COMPARE_RE` also gets the scale questions' real-size sentence. Four
files byte-identical, the review example also regenerated here and byte-identical to the full
edition's at 80 questions. 765 assertions passing unchanged, regression 4 of 4, T4 green.
Battery and corpus identical to a clean export of `d90b24e`, 16 of 19 clean, 21, 2, 4; probe 2
differs only in the two invariant questions it prints. On the 13 valid client briefs validation
and prompts are unchanged, 65 invariant questions take the new wording and nothing else moves;
the three refused briefs carry the rest of upstream's 80.

Read rather than counted, both client invariants that get the real-size sentence need the
opposite. inlingua's "the far page reads shorter than the near one" and papayiw's "the far edge
of every rectangle on it reads shorter than the near edge" are foreshortening invariants: they
ask the reviewer to check how sizes look across distance, and the added sentence tells the
reviewer to judge real sizes, not how large each looks at its distance, which forbids the check
they ask for. A reviewer who follows it answers that the real edges are equal. The one true hit
is the shipped example's "stays smaller than the pharmacist's forearm". The pattern also fires
on position and on events, "hangs higher than the shelf top", "sits lower than the jetty deck",
"the bell has rung twice", where the sentence is noise, and on "the near cup reads larger than
the far one", which is foreshortening again. Reported upstream: an apparent-size verb, reads,
looks, appears, recedes, foreshortens, should keep the sentence off, "higher than" and "lower
than" want a size word, and a bare "twice" wants "the size", "the length" or "as".

THIRTY-SECOND PORT, `00bf8dc`, same version, carrying the docs-only `b333efe` in the
contract doc. It fixes this edition's three open findings: the real-size sentence stays out
where a verb about appearance is present, and "higher than", "lower than" and a bare "twice"
no longer count; a bare "from behind" no longer means facing away; and `possessive()` takes the
pronoun before the person's own hand first. It also gives a per-hand question to every clause
that names a side, `hand_clauses`, and stops a drawn medium's marks-of-use clause saying
"photograph". Four files byte-identical, the review example regenerated here and byte-identical
to the full edition's at 82 questions, the pharmacist's two hands now asked. 778 assertions
passing unchanged, regression 4 of 4, T4 green. Battery and corpus identical to a clean export
of `00bf8dc`, 16 of 19 clean, 21, 2, 4, probe 2 with nothing missing.

Checked: theklinique loses its false back-to-camera sentence, inlingua's and papayiw's
foreshortening invariants lose the real-size sentence, the male dentist reads "his", and of the
five face-on phrases reported, the three with "from behind" now read as not facing away. On the
13 valid client briefs validation and prompts are otherwise unchanged and 19 per-hand questions
appear in 7 scenes; the refused briefs carry the rest of upstream's nine.

Read one by one, three of those 19 are broken, and they are on client briefs. `_SIDE_CLAUSE`
consumes only hand, palm, arm or fingers after the side, and the clauses are split on every
"and". bangmod's "her right thumb and index finger pinch the edge of a clear aligner tray" splits
at "and" and gives right = "thumb": "Is it the right hand of the dentist, her own right, ...,
that thumb?", with the pinch lost. Its "her left index finger steadies the patient jaw" gives
"...that index finger steadies the patient jaw at the chin?". biqdaddy's "his right index finger
rests on a box" gives "...that index finger rests on a box...", and "his left hand lies open and
flat beside the sheet" is cut to "lies open". Verbless phrasings, common in briefs, break the
same way on a constructed scene: "her right hand in her lap" asks "...that in her lap?", and
"holding a coffee cup", "raised to wave", "at her side" and "flat on the patient's cheek" all
follow "that" with no verb. Reported upstream: consume thumb and index finger with the side,
split only where "and" is followed by a pronoun and a side, and put "is" before a clause that
does not open with a verb. Also still open: `FACING_AWAY_RE` keeps a bare "turned away", so
"head turned away from the glare" and "turned away from the shelves" still read as a back to
the camera.

THIRTY-THIRD PORT, `0330de1`, same version: backs to the camera, whole hand clauses, and whose
hand in a group, three defects the sweep found in `00bf8dc`'s per-hand questions. The facing
pattern takes the plural and "seen, viewed or shot from behind"; a hand clause runs from one
side word or named member to the next, so an "and" inside it stays, and one that names a finger
is asked as "whose"; a group's question names the member the hands text names. Three files
byte-identical, the review example regenerated here and byte-identical at 82 questions. 784
assertions passing unchanged, regression 4 of 4, T4 green. Battery and corpus identical to a
clean export of `0330de1`, 16 of 19 clean, 21, 2, 4, probe 2 with nothing missing.

On the client briefs validation is unchanged and every per-hand question now reads as a whole
sentence, as upstream says: bangmod's "whose thumb and index finger pinch the edge of a clear
aligner tray", biqdaddy's "that lies open and flat beside the sheet", "the man among the
waiting visitors". Two prompts gain the side-binding sentence, the Bangla visitors and the
pulseth walkers, and both are true: their briefs say "side by side with their backs to the
camera".

Findings, reported upstream. The side-binding sentence is written for one person, so for these
two groups it reaches the generator as "The waiting visitors has his back to the camera, so his
own right hand is on the right of the picture", for a man and a woman, and "The two walkers has
her back to the camera"; a group needs "have their backs" and "their own right hands". The
clause pronoun is now the first her, his or their in the clause, which undoes the possessive fix
for a clause that does not open with one: "the left hand rests on her shoulder, his right hand
holds the stethoscope to her back" asks of one man "her own left" and "his own right". The
person-level `possessive()` reads him right and would be the better fallback. Still open from
the last two ports: a verbless clause asks "that in her lap?", "that on the steering wheel?",
"that holding a coffee cup?", "that flat on her cheek?"; and a bare "turned away" still means a
back to the camera, so "head turned away from the glare" does.

THIRTY-FOURTH PORT, `9560070`, `d262ad6` and `e07574f`, same version. A drawn medium is told
it is drawn from start to end, with no kelvin, no camera wording and a closing line restating
the style; a monochrome style keeps its light in its own tones, its entity text is
`decolour`ed and every drawn spec is asked `q_medium`; an object may declare `heading_toward`;
a locale detail that instructs the writer warns. Grounded things 0.5 to 4 m tall within 30 m get
horizon crossings, and from a metre a prompt sentence; street seats, tables and vehicles join
the reference heights, matched on the head noun, with a warning for a seat with no table at a
usable height; and a scene that pours carries the pour rule and `q_pour`. Three files
byte-identical, 817 assertions passing unchanged, the review example unchanged at 82.
Regression 4 of 4. Battery and corpus identical to a clean export of `e07574f`, 16 of 19 clean,
21, 2, 4, probe 2 with nothing missing. No lite doc quotes a height band, the closing line,
the camera wording or a colour temperature, so T4 is green with nothing to move.

On the client briefs, all photographs, validation and warnings are unchanged. drivehub's car,
pulseth's two tents and rotkubkhao's truck gain a crossing sentence, tnp's anchor block a
question only, and pulseth the pour rule and `q_pour`, as upstream says.

Three findings, reported upstream. rotkubkhao's grocery truck is cut by the frame,
`fits_in_frame` false, and the question is rightly skipped, but the prompt still says "That
horizon line crosses the truck about 78 per cent of the way up": the cut-figure mismatch
`457f9cc` fixed for people, back for objects. `pours()` misses "waters the potted basil", since
the pattern has only "watering" while the commit says waters, and fires on "tipping the cart
forward to unload" and "sprinkles salt", adding a liquid rule and question to scenes with no
liquid. And `decolour()` strips colour words that are part of a name: "green tea" becomes
"tea", "orange juice" "juice", "brown rice" "rice", "golden retriever" "retriever", and proper
nouns break, "a can of Red Bull" to "a can of Bull", "the Blue Mosque" to "the Mosque". That
touches only monochrome drawn styles, which no client brief uses.

THIRTY-FIFTH PORT, `d0e241a`, same version: an inventory of openings and practicals closes the
scene's light. A spec may declare `openings[]` and `practicals[]`; when it does, the key light
must come from a lit entry or the spec is refused, a fill that is a source of its own is warned
unless listed, lit openings on facing walls with no fill are warned, the prompt says at tier 1
which entries are the only light, and `q_light_sources` and `q_<id>_state` are asked. Specs
without the fields behave as before. The failure library has 25 classes. Four files
byte-identical, the review example unchanged at 82. Regression 4 of 4, T4 green. Battery and
corpus identical to a clean export of `d0e241a`, 16 of 19 clean, 21, 2, 4; on the client briefs
nothing moves, no prompt, question, warning or error, and every probe output is unchanged.

The contract test passes 837 checks, here and on the full edition's own export, not the 825
quoted: C65 adds 8, and C48, which checks every failure class's fields, status, detections and
regressions, grows by 12 with the 25th class.

Two findings, reported upstream. `lit` is read by truthiness, so an entry authored `"lit":
"false"` counts as lit: a closed back window written that way makes the prompt say "The only
light comes from the window in the left wall and the window in the back wall", and the review
ask "Is the window in the back wall closed, with light coming through it?". A non-boolean `lit`
wants a warning or a refusal. And the key-source match is a substring of each entry's id and
kind, so "flat outdoor daylight" names a lit door through "outdoor"; a false accept, harmless.
A design point rather than a defect: "low afternoon sun from the left" is refused with a lit
window in the left wall, physically right but not naming the entry, and the error says how.

THIRTY-SIXTH PORT, `dd60935` and `d11e9c4`, same version. `dd60935` fixes the thirty-fifth
port's findings: a non-boolean `lit` warns and is read dark, inventory names match whole words,
and sun or daylight from a lit wall is accepted. `d11e9c4` adds `physical_checks` asked only
when their trigger matches the scene, a support-capacity warning for things side by side on a
declared supporter, and moves `q_anomalies` first with a vocabulary of failure families built
from `image-failure-classes.json`; C30 now holds the review example to the generator's order and
words. Five files byte-identical, the review example regenerated here and byte-identical at 82
questions. 857 assertions passing unchanged, as on the full edition's own export; regression 4
of 4, T4 green. Battery and corpus identical to a clean export of `d11e9c4`, 16 of 19 clean, 21,
2, 4. On the client briefs prompts and warnings are byte-identical and every valid brief keeps
its question ids, with `q_anomalies` first, as upstream says. `failure_vocabulary` reads the
library next to the module, so lite reads its own copy.

The full-edition session reported that none of this edition's open findings had reached it:
each port reply reaches it as its first 400 characters. So every open finding is now in the
shared notes as `dp-016-lite-open-findings.md`, with `dp-016-realism-battery/open_findings.py`
reproducing each one against either edition; at `d11e9c4` it reports 14 open of 14, identical on
both. Two of the fourteen are new with this port. Support capacity treats a supporter as one
row: 40 cartons on a 3 m shelving wall "in rows on five shelves" warn that it cannot hold them,
and four plates set two per side on a 0.9 m table warn too; no client brief names a supporter
by id, so the corpus could not show it. And a person "leaning on the counter with both elbows"
is counted as a load standing on it.

THIRTY-SEVENTH PORT, `2f24ae9`, `5893348` and `6f20657`, same version; `0e808af` changes only the
full edition's content-pipeline contract test, which this edition does not carry. Seat-to-table
heights are read off the seat by EN 1729-1, the fresh look is told the locale, and `6f20657`
answers this edition's fourteen open findings. Five files byte-identical, the review example
regenerated here and byte-identical at 82 questions. 882 assertions passing unchanged, as on the
full edition's export; regression 4 of 4, T4 green. Battery and corpus identical to a clean
export of `6f20657`, 16 of 19 clean, 21, 2, 4. On the client briefs validation and warnings are
unchanged and the prompt moves only on bangla, pulseth, rotkubkhao and sustainmap, as upstream
says.

The reproducer, `open_findings.py`, was itself corrected twice this round. Its first run on
`6f20657` stopped at D2, which now refuses people marked matched, so D1 to D3 were made to judge
the outcome: D1 whether the named difference reaches the prompt, which it now does ("...a matched
set ...; one with a cracked corner"), D2 a refusal as fixed. Then a regex written through a
Python string lost its word boundary to a backspace byte, the trap logged at the twenty-first
port, and A3 printed FIXED with "that holding a coffee cup?" in its own evidence; the byte was
replaced and the file holds none. Read against its evidence it now reports 2 open of 14 at
`6f20657` and 14 of 14 at `d11e9c4`.

The two still open. D3 was not fixed but inverted. `counted_name` pluralises the collective, so
the prompt now reads "2 pairs of moulded tiger sculptures", "3 rows of parked scooters" and "5
rows of framed photovoltaic panels", and the count questions ask for "exactly 5 rows of framed
photovoltaic panels". Each brief sizes one item: one tiger "about 1.6 m long", one scooter "each
about 1.1 m tall at the mirrors", one panel "each panel 1.76 m by 1.13 m", the array 8.8 m wide,
five panels in one row. The count is of items inside one collective; the old "2 pair of" was
ambiguous and this states the wrong reading, on two valid client briefs, prompt and questions
both. It wants "a pair of moulded tiger sculptures", "a row of 3 parked scooters", "a row of 5
framed photovoltaic panels", and a count of the items. And A3 holds for prepositions but not
participles: "that is in her lap?" now, but "...that holding a coffee cup?" and "...that
resting on the table?" remain, since `VERBLESS_RE` lists no -ing word.

THIRTY-EIGHTH PORT, up to the full edition's frozen `917a789` and its note `963e292`, same
version, one commit on top of `0000fcc` as asked. It carries the thirty-seventh port's commits,
whose own commit `196749d` was never pushed and is folded in here, plus `4aa1605`
(`relative_size_clause`, off by default), `ef386cd` (`prevention_history` in the failure library,
held by C48, and F-backlight-front-lit), `917a789` (seated landmarks for scale anchors,
`landmark_height_m`, `anchor_posture_mismatch` and `usable_anchor`; a `style.reference` with its
rights and `conditioning_references()`; the A1 sentence plural throughout) and `963e292` (the
owner's backlight choice, a note). `0e808af` stays out: it changes only the full edition's
content-pipeline contract test, which this edition does not carry. Five files byte-identical,
the review example regenerated here and byte-identical at 82 questions. 922 assertions passing
unchanged, as on the full edition's export; regression 4 of 4, T4 green. No lite doc mentions a
style reference, a likeness or conditioning rights. Battery and corpus identical to a clean
export of `963e292`, 21, 2, 4.

The corpus itself moved during this port, outside version control: a seventeenth brief,
sustainmap-rooftop-visible, and biqdaddy and doctorjay rewritten at 17:23 with seated anchors. So
it reads 17 of 20 clean, the same three refused. Against `0000fcc`'s module on those same files:
biqdaddy and doctorjay are refused by the old code only, since it measured a seated person's
elbow at standing height, and s45 loses that same false error while staying refused for its
real ones. Every prompt change is one of the fixes, on bangla, pulseth, rotkubkhao and the two
sustainmap briefs.

The reproducer reports 2 open of 14 at `963e292`, identically on both editions: D3, which now
reaches a third brief, sustainmap-rooftop-visible's "4 rows of framed photovoltaic panels", and
A3's participles, "...that holding a coffee cup?". The posture rule raised no false alarm on six
phrasings, "an egg standing on end beside the pharmacist" and "stands upright by" among them; it
misses "the pharmacist, seated, at the elbow" and "as she sits", so it errs silent.

THIRTY-NINTH PORT, `963e292` to the full edition's final `d6a7468`, same version, one commit on
`2ebaaa2`: `bfceed1` (the garlic bowl in F-wrong-floor), `6a2d868` (a counted arrangement counts
its members, "a row of 5 framed photovoltaic panels", and a participle hand clause gets "is"),
`725c462` (group references in scale anchors), `1a865a7` (commas no longer hide an anchor's pose),
`c3ebfa2` (plate contents asked as identity, and `q_<id>_own_things` with `own_held` and
`own_things`), and `3462358`, `deefa53`, `97e7397` and `d6a7468`, which rework `own_held` on real
hand texts after rangsarn found five of six expected lists wrong. `c3ebfa2` was first called final
and then retracted; its port, `a5daaea`, was never pushed and is folded in here. Four files
byte-identical, the review example regenerated here and unchanged at 82. 939 assertions passing
unchanged, as on the full edition's export; regression 4 of 4, T4 green,
no lite doc touched. Battery and corpus identical to a clean export of `c3ebfa2`, 17 of 20 clean,
21, 2, 4. The findings reproducer reports 0 open of 14 on both editions.

On the client briefs validation and warnings are unchanged. The prompt moves on bangla and both
sustainmap briefs, to "a pair of moulded tiger sculptures", "a row of 3 parked scooters" and "a
row of 5" and "of 4 framed photovoltaic panels", their count and distinct questions with them,
and the pulseth vendor gains `q_vendor_own_things`, expecting the ladle and the wok, which is
right. The delta first showed `q_anomalies` changed on every brief: that was the harness, whose
copy of the old module sat in a scratch folder with no failure library beside it and so asked
the question without its vocabulary. Pointed at the same library, both modules write it the same.

Three findings on `c3ebfa2`'s `own_held`, reported upstream and fixed by `d6a7468`, none having
reached the corpus: "a spoon in her right hand and a fork in her left" yielded nothing, now spoon
and fork; "holds a cup of tea" expected "tea", now the cup; "her left a saucer" dropped the
saucer, now kept. One smaller finding at `d6a7468`, reported: "spoonful" and "bowlful" sit in the
quantity list, so "holds a spoonful of rice" expects rice and "holds a bowlful of soup" expects
soup, where the hand holds the spoon and the bowl. "bunch of bananas", "pile of plates" and
"stack of menus" read right.

FORTIETH PORT, `d6a7468` to `e6704f9`, same version, one commit on `4f30add`, after the sweep's
run lifted the freeze. "a spoonful of rice" is held by its spoon, and bowlful, cupful and ladleful
likewise, which closes this edition's last open finding; a subject or object whose position
opens in the region `composition.negative_space` reserves is warned, unless the position is
relative to another thing or the reserved field is written around it; and the contract doc gains
the viewpoint-as-content guidance. Three files byte-identical, the review example regenerated
here and unchanged at 82. 945 assertions passing unchanged, as on the full edition's export;
regression 4 of 4. Battery and corpus identical to a clean export of `e6704f9`, 17 of 20 clean,
21, 2, 4, and the findings reproducer at 0 of 14. On the client briefs the one change is the new
warning on sustainmap-rooftop-visible, a true positive: it reserves "the upper left quarter" and
its near panel "overhangs the top left corner", the case the commit was written for.

The full edition also changed its seo-image-production SKILL. Lite carries the same quiet-area
rule in `content-production-lite/SKILL.md`, so the two points are written there in lite's words.
The quiet-area bullet now says the compiler warns on a position that opens in that part of the
frame and not on one relative to another thing. The viewpoint advice became its own paragraph
after the list rather than a third bullet, because the list opens "Two rules the compiler
enforces" and a viewpoint is guidance it does not enforce. The new warning claim is a behaviour,
so T4 gains D10: the claim and its exemption are in the docs, a person positioned in the reserved
upper right is warned, and one at the upper right of the counter, or in another part of the
frame, is not. Run against `d6a7468`'s module the positive case fails, so it can catch what it is
for. T4 is at 59 checks.

FORTY-FIRST PORT, `e6704f9` to `3c7dab3`, same version, one commit on `a99b27d`. Two things.

`962c4e3`, a production bug this edition shared. `defaults.json` shipped `"prompt_target":
"negative_prompt"` and `compile_specs` passed it on, which overrode the model registry: a client
that set `images.spec.target_model` to openai-gpt-image still had its exclusions compiled into
`negative_prompt`, a field gpt-image does not have, and lost every one. This edition's
`defaults.json` and `image_production.py` are its own files, not copies of the full edition's,
and they carried the same default and the same line, so the fix is applied here by hand: the
default is empty, `compile_specs` lets the registry decide, warns when neither a target model
nor a prompt target is set, and reports the target the compile actually used; the selftest
asserts the warning on the real compile path and fails on the old two files. The ported C74
failed against this edition's old default before the fix, which is how the port showed it. The
docs here already promised it, "image-model-registry.json then decides where exclusions go", in
both SKILL.md and agent.json, and T4 had pinned nothing about it; D11 now does: the claim is in
the docs, the shipped default is empty, and a gpt-image client gets its exclusions inline with
no negative prompt. On the old code the last two fail.

`3c7dab3` reverses the negative-space exemptions the fortieth port described. The sweep showed
from the images that both skips hid real collisions, so a position relative to another thing now
resolves through that thing's own place in the frame, and a thing the quiet area is described
around is warned softly. SKILL.md's sentence that a relative position "is not warned" became
false and is rewritten; D10 is rebuilt on the example's own layout: its counter runs across the
lower third and its medicine box sits near the centre, so "the upper right of the counter"
resolves away from the reserved upper right and stays clear, while "the upper right of the
medicine box" keeps its offset and is warned. On the previous module that case fails. T4 is at
64 checks.

The image-spec files are byte-identical to `3c7dab3`, the review example regenerated here and
unchanged at 82. 951 assertions passing, as on the full edition's export; regression 4 of 4.
Battery and corpus identical to a clean export of `3c7dab3`, 17 of 20 clean, 21, 2, 4, the
findings reproducer at 0 of 14. On the client briefs prompts are unchanged and two warnings are
added, both the collisions the sweep saw: papayiw's pen "across the lower right of the notebook"
and drivehub's terminal canopy, which the quiet area is described around.

FORTY-SECOND PORT, `3c7dab3` to `a8ec844`, same version, one commit on `3d18662`. The owner
decided, as relayed by the full edition, that a config naming no `target_model` sends its
exclusions inline: the sweep found that none of the 8 client configs sets one, and the hosts they
run on draw with gpt-image, which has no negative field, so production was losing every exclusion
there. In the shared module `compile_spec` now falls back to `inline_constraints`, and a drawing's
closing medium line comes after the Constraints block, where an inline block had taken the last
line from it. Then `a8ec844`: a registry that cannot be read is named as the cause, rather than
reported as a model it does not list; here, with the registry file moved away, the error names
its path. The image-spec files are byte-identical to `a8ec844`, the review example unchanged at
82; 954 assertions passing, as on the full edition's export. The port of `8ef6916` alone,
`2a4c70b`, was never pushed and is folded in.

Mirrored by hand in this edition's own files: `compile_specs` warns with the new text and falls
back to `inline_constraints`, and the selftest expects that target, an empty `negative_prompt`
and "Constraints: no " in each prompt. This selftest also holds the scene description free of
negation, a check the full edition's does not make, and an inline block puts "no" into every
prompt; the rule is about the description, so the check now reads the prompt up to its
Constraints block. On all 14 compilable client specs the scene part carries no negation. SKILL.md
gains the line that an unset target goes inline and that a Gemini or FLUX host should name its
model, and D11 pins it: the sentence is there, an unset config compiles inline with no negative
prompt, and a named Gemini model keeps the exclusions out of the prompt. The fallback case and
the selftest fail on the previous module and `image_production.py`. T4 is at 67 checks.
Regression 4 of 4. Battery and corpus identical to a clean export of `8ef6916`, 17 of 20 clean,
21, 2, 4, the findings reproducer at 0 of 14; every compilable client spec compiles inline.

FORTY-THIRD PORT, `a8ec844` to `a1f19dc`, same version, one commit on `36ac5a9`. Shared:
`a1f19dc` puts `hangs_from` in `UPRIGHT_SUPPORT`, since a hanging thing's `height_m` is its own
vertical size and the clean truth-v2 scoring found three of four hanging ratios to be real faults;
wide structures stay out. `d786903`, `ef6ab22` and `1bc17d6` change only the contract doc, on how
recall is scored against review-blind readers. The image-spec files are byte-identical to
`a1f19dc`, the review example unchanged at 82; 957 assertions passing, as on the full edition's
export.

Mirrored by hand, `844846b`, a production bug this edition shared: every recorded reference may
condition the generator, by the owner's decision, and `conditioning_references()` listed them,
but nothing sent them. The skill told the host to generate from the compiled prompt alone, so a
real place's references, a likeness and a style reference never reached the generator.
`compile_specs` now writes each item's `conditioning` list into the manifest and a count into
the compile report; SKILL.md's step 4 and the agent.json workflow say to attach every image in
that list as an image input, and to say so in the source review when the generator takes none.
The selftest gives the first fixture item a style reference and asserts the list reaches the
manifest; on the old `image_production.py` it fails. T4 gains D12: the docs say to attach the
list, and a style reference is in it with its role and rights. T4 is at 70 checks.

Regression 4 of 4. Battery and corpus identical to a clean export of `a1f19dc`, 17 of 20 clean,
21, 2, 4, the findings reproducer at 0 of 14. On the client briefs the only change is four ratio
questions returning, the whiteboard against the projector on ecc and the bag roll, scale and
spirit house on rotkubkhao, as upstream says.

FORTY-FOURTH PORT, `a1f19dc` to `f6c4ea9`, same version, one commit on `fb89da8`, shared files
only. When a spec with a style reference also sets its own colours, a `color_palette` or a
monochrome look, the style clause takes only line, texture and finish from the reference, and the
spec is warned that the reference image still carries its own colours; in rangsarn's A/B the
brand art's palette beat the spec's "one amber wash" in every interior arm. Three files
byte-identical, the review example unchanged at 82; 960 assertions passing, as on the full
edition's export. Checked both ways on the shipped example: with its palette the narrower clause
and the warning, with the palette removed the full clause and no warning. The lite docs mention
the style reference only as an image to attach, so nothing in them moves. Regression 4 of 4, T4
green at 70, the selftest unchanged, since its fixture's reference has no palette. Battery and
corpus identical to a clean export of `f6c4ea9`, 17 of 20 clean, 21, 2, 4, the findings
reproducer at 0 of 14; no client brief carries a style reference, so the corpus does not move.

FORTY-FIFTH PORT, `f6c4ea9` to `096e3d2`, same version, one commit on `5b910e9`. A palette that
restricts, a drawn monochrome look or one that says "only", "limited to" or "duotone", now warns
on any field that asks for several colours or names one the palette does not hold
(`restrictive_palette`, `palette_conflicts`): in rangsarn's interior, coloured book spines beat
one amber wash in every arm. The image-spec files are byte-identical to `096e3d2`, the review
example unchanged at 82; 966 assertions passing, as on the full edition's export.

`a8b818c`'s guidance that a style reference is a subject-free crop of approved art, never a full
master, lives in the full edition's seo-image-production SKILL. This edition's SKILL.md has no
such section, but since the forty-third port it tells the host to attach style references, so the
advice belongs beside it: written as its own paragraph before the viewpoint advice, in lite's
words. It is an observed result, 6 of 6 scenes leaking a master's subject against 0 of 3 with a
crop, not a rule the compiler enforces, so T4 has nothing to pin.

Checked on the shipped example: its own palette does not restrict, so it is not warned; with "warm
neutrals only: sand, cream, walnut" the shelving's sage green and the pharmacist's navy are
flagged, as they should be. One small finding, reported upstream: `palette_conflicts` does not use
the exemption `decolour` gained at `6f20657`, so "iced green tea" is flagged as asking for green
and "a can of Red Bull" for red. It reaches only a restrictive palette, which no client brief
has. Regression 4 of 4, T4 green at 70, the selftest unchanged. Battery and corpus identical to a
clean export of `096e3d2`, 17 of 20 clean, 21, 2, 4, the findings reproducer at 0 of 14; the
corpus does not move.

FORTY-SIXTH PORT, `096e3d2` to `1c5db92`, same version, one commit on `8e53f35`, shared files
only. The forty-fifth port's finding is fixed upstream: `palette_conflicts` now uses `decolour`'s
`_keep_colour` exemption, so under "warm neutrals only: sand, cream, walnut" "small glass of iced
green tea" and "can of Red Bull" are no longer flagged, while "bright green ceramic mug" still is.
Two files byte-identical, the review example unchanged at 82; 967 assertions passing, as on the
full edition's export. Regression 4 of 4, T4 green at 70. Battery and corpus identical to a clean
export of `1c5db92`, 17 of 20 clean, the findings reproducer at 0 of 14; the corpus output is
unchanged since the last port.

FORTY-SEVENTH PORT, `1c5db92` to `93fd723`, same version, one commit on `d8792a4`. `09641f3`:
a figure must be whole in the frame, by position as well as size, to be measured from its feet,
so `whole_in_frame` replaces `fits_in_frame` at the per-cent crossing in the prompt and its
question, the stature question, ratios and object crossings. `93fd723`: `camera.pitch_deg`
derives through a tilted pinhole, with `fraction_in_image` for per-cent crossings on a tilted
camera. The image-spec files are byte-identical to `93fd723`, the review example regenerated
here and unchanged at 82; 977 assertions passing, as on the full edition's export. T4 and the
selftest were unaffected.

`e19d324`'s guidance, that a restrictive palette needs a recoloured swatch and each thing
coloured inside it, is written into SKILL.md beside the style-reference paragraph, in lite's
words. Its last sentence, that the compiler warns when a field still asks for colours the palette
does not hold, is a behaviour, so T4 gains D13: the sentence is there, a palette that says only
warns on a navy polo, and one that describes rather than restricts does not. The warning has
existed since `096e3d2`, so D13 fails on the module before it and guards the claim from here on.
T4 is at 73 checks.

Regression 4 of 4. Battery and corpus identical to a clean export of `93fd723`, 17 of 20 clean,
21, 2, 4, the findings reproducer at 0 of 14; the only probe change is the new
`fraction_in_image` field in printed output. On the client briefs validation and warnings are
unchanged; five briefs lose per-cent crossings and ratios of things the frame cuts at the bottom,
bangla, biqdaddy, drivehub, inlingua and tnp, five and not the six upstream quoted. Checked on
drivehub: at the car's 3.4 m the frame spans 0.18 to 2.02 m, so the 1.63 m car fits by height but
its bottom 18 cm, the base its per-cent crossing is measured from, is out of the picture.

FORTY-EIGHTH PORT, `93fd723` to `9ac142c`, same version, one commit on `a0b8de5`. The shared
files change only in the contract doc: `dcf28d7` (a line-art medium is the generator's, not the
prompt's), `67d01f4` (`pitch_deg` checked against pixels, roll not modelled), `2d68119` and
`9ac142c` (a disagreement between instruments becomes a pointed question, never a finding). The
contract doc is byte-identical to `9ac142c`; `image_spec.py` and its test are unchanged, 977
assertions.

Mirrored by hand in this edition's own files, `a8f4501`: `image_production` gains
`compile_spec_file()` and a `compile-spec-file` command for a client whose content runs through
its own adapter, which prints one JSON report and exits 1 on a refused spec; `compile-spec`'s
`--target` choices, stale at negative_prompt and positive_only, now list every target; and the
selftest gains `check_compile_spec_file()`, covering the example compiled inline for gpt-image, a
real place whose reference returns in its conditioning list, and a refused spec, which fails on
the old `image_production.py`. Run by hand, the shipped example exits 0 inline with 82 questions
and a refused spec exits 1. SKILL.md documents the command in its compile step, and gains
`dcf28d7`'s line-art paragraph after the palette paragraph, as observed guidance. T4 gains D14:
the docs name the command and its refusal exit code, and the command line itself compiles the
example with exit 0 and refuses a broken spec with exit 1 and no prompt; on the old file the
command does not exist and both fail. T4 is at 76 checks.

Regression 4 of 4. Battery and corpus identical to a clean export of `9ac142c`, 17 of 20 clean,
21, 2, 4, the findings reproducer at 0 of 14; the corpus output is unchanged since the last port.

FORTY-NINTH PORT, `9ac142c` to `ffb7cbe`, same version, and the release paperwork for 2.7.0.
Mirrored by hand, `01926a5`: `review-crops-file` cuts the reviewer's grid of magnified crops from
an image file, named `<stem>-r<row>c<col>.png` with the image's sha256, and `review-template-file`
compiles a spec exactly as `compile-spec-file` does and writes the blank review; the selftest
cuts a fixture image and checks the review's questions are the compile's, and fails on the old
`image_production.py`; SKILL.md gains the paragraph after the compile-spec-file block. Run by
hand, the shipped example gives nine crops and a review of 82 questions carrying the same
sha256. One small finding, reported upstream: `--image-id` is documented as the id written into
the review, but `review_template()` writes no item id, so the option changes nothing in the
output; both editions behave alike. Shared, `ffb7cbe` renames one C71 check; the contract test
is byte-identical, 977 assertions.

The release paperwork, checked against what the branch ships. The 2.7.0 user section had four
bullets, describing only the first 2.7.0 port, and one of them, that each reference image needs a
rights row of its own or is refused, was reversed by the owner's decision at `6b2a3d8`. No tag
exists after v2.3.1, so 2.7.0 is the first release since and ships everything in 2.4.0 to 2.6.0
too; the section now has three plain bullets for the whole of it, and the opening of Under the
hood states the shipped state. In this log, DP-016's v2.5.0 and v2.6.0 rows sat in the body
above their own detail entries instead of in Contents; they are moved there in date order, and
the DP-015 and DP-016 detail entries now open with their closing record: category, start date,
planned and actual hours, tokens, the PR and the version.

FIFTIETH PORT, `3fa9275`, same version: the `--image-id` finding above, fixed upstream. Mirrored
by hand: `review_template_file()` now opens the review with `image_id`, the option's value or
the spec file's name, so `review-template-file --image-id` writes what it documents. The
selftest checks the default id is `image-spec.example` and that `image_id="cover-01"` comes back,
and fails on the old `image_production.py` with KeyError 'image_id'. `image_spec.py` is untouched
and byte-identical; the contract test stays at 977 assertions, regression 4 of 4, T4 green.

BATTERY HARDENED against the one class it could not see. A probe that raises is not a probe
that fails: an exception aborts the run, so every probe after it never runs and the ones
before it look fine, which means a crash in the validator reads as a clean sheet. New
`battery.py` holds the shared harness, and every probe now reports a raise as a CRASH
verdict with its traceback, continues the run, and exits non-zero. A crash outranks every
other verdict, because a validator that raises on a live spec gives the caller no answer at
all rather than a wrong one. This was prompted by the sweep session hitting two live states
that crashed the validator, and it goes in before those fixes land rather than after, so the
battery can see them when they arrive.

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

Closed with PR #6 (biqdaddy-dev/rainmojo-so-lite#6), shipping in v2.7.0, together with DP-016. หมวด: image pipeline. Started 2026-10-25, finished when PR #6 merges, which is the owner's call. Planned 5 hours; actual 0.3 hours and 270k tokens, measured as for DP-016.

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
