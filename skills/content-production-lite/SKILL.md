---
name: content-production-lite
description: "Run the client-configured SEO content factory from validated article planning through content QA, image production, internal and external linking, and a verified WordPress draft. Supports the shared generic engine and declared client-native adapters. Use when an approved article plan must become a verified WordPress draft."
allowed-tools: Read Grep Glob Write Bash Skill
---
<!-- RAINMOJO_CLIENT_WORKSPACE_ROUTING_V1 -->
## Client workspace routing (mandatory for file changes)

Every generated file has exactly one home. Audit, keyword and comparison
outputs live under `work/{domain}/` created by `new-workspace-lite`
(`00-baseline/` first run, `01-current/` later runs, `02-fixes/`, `03-content/`,
`04-reports/`, `uploads/` read-only for user files); never invent another
top-level folder there. Content production and WordPress publishing use the
client workspace `clients/<client>/` created by `new-client-lite`: read
`workspace-routing.json` first, resolve every artifact with
`{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py route`, use the
most precise registered route, edit root files only when their exact filename is
in `root_policy.allowed_files`, treat `uploads/` as read-only, and when no route
fits use `create-work` then `route-work`; never construct a `work/<name>/...`
path by hand inside a client workspace. Never write generated files to the
plugin tree or the caller's working directory. Append one line to the
workspace's `CHANGELOG.md` or `log.md` after every write. Run
`client_workspace.py validate` before handing a client workspace over. Direct
CMS/API operations retain their own safety and verification gates.

<!-- RAINMOJO_PRESENTATION_LAYER_V1 -->
## Presentation (Two-Tier, 7 modes)

Answer in the response mode that matches the request
(`{PLUGIN_ROOT}/skills/rainmojo-so-lite/_base/presentation-scaffold.md`): quick fact,
how-to, comparison, troubleshoot, audit, deployable, always closing with next
steps. A run that writes a deliverable ends with a Tier 1 card built from
`summary.json` (`templates/widget/summary.schema.json`) and rendered with
`{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/present.py --target auto`, then hands
off to the Tier 2 file, which stays complete and unchanged. Lite cards carry
counts of checks passed, never a weighted score. Every card value is copied
from the deliverable; unmeasured values show as could not verify. No emoji on
any surface; the glyph allowlist applies to chat and Markdown only.


# Content Production

Use this as the callable entry point for a complete article-production workflow.
Read [agent.json](agent.json), then:

- `{PLUGIN_ROOT}/skills/rainmojo-so-lite/_base/skill-scaffold.md`
- `{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/content-production/contract.md`
- `{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/content-production/content-review.example.json`
- `{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/content-production/image-spec.contract.md`
- `{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/content-production/image-spec.example.json`
- `{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/content-production/image-plausibility-review.example.json`
- `{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/content-production/image-model-registry.json`
- `clients/<domain>/CLAUDE.md`
- `clients/<domain>/brand-guidelines.md`
- `clients/<domain>/client-profile.md`
- `clients/<domain>/site-config.md`
- `clients/<domain>/content-pipeline.json`
- `clients/<domain>/workspace-routing.json`

Resolve `{PLUGIN_ROOT}` to the real installed plugin root before invoking any
plugin script.

## Start

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py" validate \
  --client ./clients/<domain>

python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/content_pipeline.py" config-check \
  --client ./clients/<domain> \
  --require-capability end_to_end
```

This command intentionally rejects `image_only` and `partial` clients. Use the
image-production entry point for a declared image-only adapter.

After configuration passes, use the `content-production-orchestrator-lite` agent.
The orchestrator must dispatch according to `engine.mode`:

- `generic`: shared article packages under `content/production/<slug>/`
- `client_native`: only the capability-backed adapter operations declared in
  the client config; never generic package or publisher paths

## Image spec workflow (generic engine)

Lite has no separate image-production skill, so the image instructions live here.
Every image a model will generate carries a `spec` in `image-manifest.json`: the
picture as a shot brief, with real distances in metres, a real height for every
person, a size and a support for every object, one key light with the shadow
direction it implies, and the area that stays quiet for a headline. The `prompt`
and `negative_prompt` are compiled from it and never written by hand.

1. Fill every manifest item with a distinct concept, alt, media title, optional
   caption and provenance record. Leave `prompt` and `negative_prompt` empty.
2. Start each spec from the blank template, which carries every required field as
   an unanswered question in angle brackets:

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/image_production.py" spec-template --medium photograph --people 2
```

   Read `image-spec.contract.md` for the field reference and
   `image-spec.example.json` for a worked two-person scene.
3. Compile the specs. This validates the physics and the logic of each brief,
   derives the geometry it implies, and writes `prompt`, `negative_prompt` and
   `spec_compiled` with the review questions:

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/image_production.py" compile-spec --client ./clients/<domain> --slug <slug>
```

   A contradiction stops the compile and names it: a horizon that disagrees with
   the camera tilt, a shot type that disagrees with the lens and the distance,
   shadows that disagree with the key light, an object with no support, a standing
   person who does not fit the frame, a sharp background the aperture cannot
   deliver, an object height outside the band its building code fixes. Fix the
   spec and compile again. Read the `warnings` in the report before moving on:
   they carry the trim report and anything the geometry only makes unlikely.

   Two rules the compiler enforces, so write the spec to them from the start:

   - **Say what the picture is, never what it is not.** A field containing no,
     not, without or free of is refused and named. Describe the state instead: a
     plain unprinted lanyard, an even grey wall, Thai script on the shelf labels.
     Anything to exclude goes in `must_not_show`, which reaches the avoid list and
     never the scene description. A negation in a positive prompt tends to produce
     the thing it forbids.
   - **The quiet area is a thing in the scene, not a hole in a busy frame.** Name
     an even wall, an overcast sky above a low horizon, a plain backdrop. Expect it
     to fail roughly one time in four even so, which is survivable only because
     the headline is laid over the image by the template and never drawn by the
     model. Keep every person and object out of the region it reserves: the
     compiler warns when a `position` opens in that part of the frame, including a
     part of a thing that lies there ("the lower right of" a centred notebook), and
     warns more softly when the quiet area is described around the thing itself.

   A style reference is a subject-free crop of approved art, never a full master.
   A full master's subject leaks into the picture: lotus leaves from a brand
   image's pond appeared in 6 of 6 generated scenes, and in 0 of 3 with a crop of
   its empty wash. Keep frames and borders out of the crop unless the picture wants
   them, and say in `style.reference.origin` what it was cut from.

   A viewpoint that must hold is written as something the camera sees, not as an
   instruction. An angle stated as an instruction failed 4 of 4 times; a near
   thing only that viewpoint can show held 2 of 2 (for a low lens, the underside
   of the nearest raised panel in a corner). Say only what that thing shows, and
   keep it out of the quiet area.

   A third thing the compiler checks, which is worth writing to from the start:

   - **`scale_anchor` is a claim, not a flourish.** For an object that stands or
     rests on the floor, anchor its size to a body landmark of a person in the
     scene and the compiler reads that landmark off their `height_m` and checks the
     object's height against it, within 12 cm either way: the hip of a 1.62 m
     person is 0.86 m, so a 0.42 m counter "at the hip" is refused. Only the first
     landmark the anchor names is checked, and "above" or "below" is not part of
     the check, so lead with the landmark you mean. Name the person when more than
     one is in frame, or no check runs. An anchor about width or length, such as
     "as wide as her shoulders", is left alone, and so is anything that hangs or is
     mounted, whose `height_m` is its own length. When the anchor puts the object
     in a hand, its height is compared with the person holding it, the one named
     in `support.by`, or failing that the person the anchor names, or failing both
     the tallest person in the frame: above three tenths of that height it is a
     warning, above six tenths it is refused.

   Set `images.spec.target_model` to the generator in use. `image-model-registry.json`
   then decides where exclusions go and what prompt length is worth sending. Left
   unset, they go inline in the prompt, which is right for gpt-image on Codex and
   ChatGPT; on a Gemini or FLUX host, name the model, since those vendors advise
   describing the positive state only. Most current generators have no
   negative-prompt field at all, so an empty `negative_prompt` is the normal
   result, not a failure.
4. Generate from the compiled prompt exactly as written, and attach every image in
   the item's `conditioning` list as an image input: the real place's references,
   each person's likeness and the style reference, each with its role. If the
   generator takes no image input, say so in the source review, since a likeness
   or a style it was never shown cannot hold. Save the raw asset under
   `images/raw/`, approve it with `review-source`, then run `process`.
5. Cut the optimized image into the review grid and open the blank review. A whole
   1200 px image hides the failures that matter: fingers, teeth, contact shadows,
   drifting tile repeats, gibberish on signage:

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/image_production.py" review-crops --client ./clients/<domain> --slug <slug> --image-id featured
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/image_production.py" review-template --client ./clients/<domain> --slug <slug> --image-id featured
```

6. Inspect the full frame and then every crop. Technical processing is not visual
   approval. Answer in the review file every `checks` item the client config
   requires; every `plausibility` check, with `status` and `evidence` naming what
   you saw and in which crop; and every `spec_answers` question `yes` with
   evidence. `not_applicable` is allowed only where the check permits it, and the
   evidence must then say what is absent from the frame. A `no` means the image
   does not match its brief: regenerate or fix the spec, do not pass it. The
   rubric leads with the functional, anatomical and stylistic checks because
   those are what actually fail, and asks the physics ones across pairs of things,
   because a generated frame is usually self-consistent object by object and
   inconsistent between objects.

   Where a check or question carries `verify_with`, **measure it rather than
   forming an impression**: `count` means count the fingers, limbs and objects;
   `ocr` means read the lettering at full resolution; `geometry` means put a
   straight edge on the horizon and compare heights. Those are the three things
   both people and vision models judge badly.

   Set `crops_reviewed` to the number of crops you actually opened and
   `image_sha256` to the digest `review-crops` printed, then record the pass with
   `mark-reviewed --status passed --checklist-json <review file>`.

### Mandatory image rules

- The prompt is compiled, never authored. Change the spec, not the prompt. A
  prompt edited by hand, or a spec changed after compilation, is refused at the
  next gate.
- The compiled prompt never contains a negation, and never a bare camera number:
  every value is emitted next to the words for its effect, because the words are
  what steer.
- `image_specs_ready` is refused while any generated image has no valid, freshly
  compiled spec, and processing is refused when the prompt has drifted from it.
- The headline is never generated into the image. `text_in_image` stays `none`
  unless the client has enabled an infographic text workflow; approved text is
  added deterministically after processing.
- A physically impossible image is rejected even when it looks attractive:
  shadows that disagree with one light, an object with no contact where it rests,
  a size that does not match its distance, two vanishing points on different
  horizons, a reflection showing something that is not in front of the surface,
  liquid that does not sit level.
- A passed review requires structured evidence tied to the exact image file.
  Reprocessing an image invalidates every previous visual approval.

## Review guidance for model-drafted sections (decision layer)

This section is judgement inside the review record that `content_qa_passed` already requires.
It adds no pipeline state, no ledger column and no new gate; where it appears to disagree with the
safeguards above, the safeguards win. Full procedure and record shapes:
`{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/frameworks/content-production-model-draft-gates.json`

- **Two-pass verification on every model-drafted section.** Pass 1 walks every factual claim and marks
  it verified (source named), wrong, or could not verify. Pass 2 writes what a subject-matter expert would
  insist the piece must contain, before rereading, then lists what is absent. Pass 2 outranks pass 1:
  a draft that states nothing false while omitting half the brief does not pass. A named human signs off
  on both passes with a date; a role title or a model-generated approval is not a sign-off.
- **Topic blocklist: a generative model is never the source of record** for current product pricing,
  directions and routing, weather and other real-time data, live scores, YMYL topics, and news. A block in
  these classes fails the gate no matter how confident the draft reads; it clears only when the values are
  replaced by feed-supplied or human-supplied values and the record says which.
- **Record which engine produced each draft** beside the class check. If the engine cannot be established,
  write could not verify; never assume the currently configured engine produced an older draft.
- **Outbound link qualification.** Assign rel by reason, never as a blanket default: advertising or any
  compensated placement gets `sponsored` (or `nofollow`); anything inside a user-generated area gets `ugc`
  (or `nofollow`); a link the page must carry but does not endorse gets `nofollow`; an editorially chosen,
  trustworthy, topically related source gets no rel, because the endorsement is intended. Record target URL,
  reason class, rel assigned and topical-relation verdict for every outbound link.

Boundaries: off-site link acquisition belongs to `seo-backlink-strategy-lite`; E-E-A-T scoring stays with
`seo-content-audit-lite`; the drafting-side method for running the two passes belongs to `seo-content-creation-lite`.

## Required safeguards

- Missing client configuration fails closed.
- Production placeholder domains and visual-style modes fail validation.
- `content_qa_passed` requires a structured reviewer/checklist record bound to
  the current `article.md` SHA-256.
- Editing the article after review invalidates later gates.
- `image_specs_ready` requires a valid, freshly compiled shot spec on every image
  a model will generate; `process` refuses a prompt that has drifted from it, and
  `mark-reviewed --status passed` refuses a plausibility review that is
  incomplete, unevidenced, short of `zoom_grid` squared crops, or bound to a
  different image file.
- Article state transitions are validated and auditable.
- Required product, pillar, related-content, and external-source links are
  checked against the article plan.
- Image generation and content drafting may run in parallel.
- WordPress media and post writes use one serial worker per client.
- Draft-only is mandatory.
- A non-draft slug is rejected before the first media write.
- Verification failures use verify-only recovery.
- Public publication requires a separate capability and explicit instruction.
- Generic package state is confined to `content/production/<slug>/`. The
  aggregate dashboard is regenerated from package state and publish evidence;
  it is never edited as a second state store.
- At batch checkpoints and before handoff, run `content_pipeline.py batch-report
  --client ./clients/<domain>`. Current JSON and HTML go to
  `content/dashboards/`; immutable run-scoped status, publishing, and batch
  manifest files go to `content/reports/status/<date>/` and
  `content/reports/publishing/<date>/`. The current dashboards are the only
  mutable aggregate views.

## Host image capability

If the host exposes an image-generation capability, use it to create the approved
raw asset from the compiled prompt, exactly as `compile-spec` wrote it. If it
does not, stop after the brief/source
intake stage and report that a raw source asset is required. Never claim that the
image-production script itself generated an image.
