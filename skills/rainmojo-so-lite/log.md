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
