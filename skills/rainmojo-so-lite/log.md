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
