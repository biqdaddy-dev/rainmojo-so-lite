# Image spec contract

An image item in `image-manifest.json` carries a `spec`: the picture described the way a
photographer's shot brief describes it, with real distances, real sizes and one named light.
`image_spec.py` validates the spec, derives the geometry the brief implies, compiles it into
the `prompt` and `negative_prompt`, and turns it into the questions the reviewer answers
against the generated image.

The prompt is never typed by hand. `prompt`, `negative_prompt` and `spec_compiled` are
outputs of `image_production.py compile-spec`. A prompt edited after compilation, or a spec
changed after compilation, is refused at the next gate: change the spec and compile again.

## Why a spec and not a prompt

A prompt says what the picture shows. A spec says what the picture *is*, and that is what
makes the contradictions visible before anything is generated:

- a camera tilted down cannot put the horizon through the middle of the frame;
- a 50 mm lens at 2.2 m frames 1.6 m, which is not an `extreme_wide` shot;
- a key light from the front left cannot cast shadows to the left;
- an object with no `support` floats;
- a 1.8 m standing person does not fit the 0.83 m frame height of a `full` shot at that lens;
- a sharp background is impossible at f/2.8 with the focus 2.2 m away;
- a `foreground` entity at 9 m is not in front of a `background` entity at 3.6 m;
- a 0.42 m counter does not meet a 1.62 m person "just above the hip", which is 0.86 m;
- a 1.4 m carton does not fit in the palm of a 1.62 m pharmacist;
- a `full` shot promises the whole subject, so a 6 m counter does not fit a 3.6 m frame;
- an `eye_level` lens at 1.52 m is a high angle over a seated figure whose eyes are at 1.23 m;
- a clouded sky covers the sun, so it cannot cast the crisp shadow the brief asks for;
- a `fill` with the key's power and hardness is a second key, and two of those are two suns;
- nothing is held up by "a hovering glass shelf", and nothing is held by a counter.

Each of those is a picture a reader would see as wrong. Catching it costs one message;
catching it after generation costs a generation, a review and a reprint.

## Pipeline

```bash
# 1. a blank spec with every required field present and unanswered
python scripts/image_production.py spec-template --medium photograph --people 2 \
  > /tmp/featured-spec.json

# 2. paste the filled spec into the manifest item's "spec", then compile
python scripts/image_production.py compile-spec --client ./clients/<domain> --slug <slug>

# 3. generate the image from the compiled prompt, save it under images/raw/,
#    approve the raw source, then process the package
python scripts/image_production.py review-source  --client ... --slug ... --image-id featured --review-file ...
python scripts/image_production.py process         --client ... --slug ...

# 4. cut the optimized image into crops and open the blank review
python scripts/image_production.py review-crops    --client ... --slug ... --image-id featured
python scripts/image_production.py review-template --client ... --slug ... --image-id featured

# 5. answer every check and every question with evidence, then record the pass
python scripts/image_production.py mark-reviewed   --client ... --slug ... --image-id featured \
  --status passed --reviewer "<name>" --notes "<notes>" \
  --checklist-json reports/featured-visual-review.json
```

`image_specs_ready` is refused while any generated image has no fresh compiled spec, and
`process` is refused when the prompt has drifted from it.

## Spec fields

`purpose`, `medium`, `location`, `camera`, `lighting`, `composition` and at least one
subject or object are required. `photograph` and `3d_render` are photographic media and
additionally require the camera numbers and the shadow direction.

| Field | What it holds |
|---|---|
| `purpose` | What the reader must understand from the image, in one sentence |
| `medium` | `photograph`, `3d_render`, `illustration`, `flat_vector`, `infographic_base` |
| `style` | `look`, `color_palette`, `mood`, `texture` |
| `location` | `place`, `locale`, `time_of_day`, `weather`, `locale_details[]` |
| `camera` | `shot_type`, `angle`, `tilt`, `horizon`, `height_m`, `focal_length_mm`, `aperture_f`, `subject_distance_m`, `focus_on` |
| `subjects[]` | `id`, `short_name`, `kind`, `count`, `description`, `appearance`, `wardrobe`, `posture`, `pose`, `hands`, `gaze`, `expression`, `action`, `position`, `height_m`, `distance_m`, `plane`, `interacts_with[]` |
| `objects[]` | `id`, `short_name`, `name`, `count`, `material`, `state`, `size`, `height_m`, `width_m`, `scale_anchor`, `support{kind,by}`, `position`, `distance_m`, `plane`, `interacts_with[]` |
| `spatial_layout` | `foreground`, `midground`, `background` |
| `lighting` | `key{source,direction,quality}`, `fill[]`, `shadow_direction`, `color_temperature_k` |
| `composition` | `subject_placement`, `negative_space`, `crop_safety` |
| `background_focus` | `sharp` or `blurred`, checked against the computed depth of field |
| `physical_invariants[]` | The scene facts a wrong picture would break |
| `must_not_show[]` | Scene-specific items for the avoid list |
| `text_in_image` | `none` unless the client has enabled an infographic text workflow |

An object whose name matches a height fixed by code or settled convention is checked
against it, so a 1.4 m kitchen counter or a 0.3 m stair riser is caught in the brief. The
code-backed bands come from the ADA (door leaves at 2032 mm, hardware 34 to 48 in above the
floor, operable parts 15 to 48 in) and the IRC and IBC (riser maxima 7 3/4 in residential
and 7 in commercial, 10 in minimum tread, 7 ft minimum habitable ceiling). The rest are
conventions and are labelled as such in `REFERENCE_HEIGHTS_M`, because a convention is a
default a client may legitimately override while a code minimum in a picture of a real
building is simply wrong.

`height_m` on a person is mandatory because it is the scale anchor for everything else in
the frame. `support{kind,by}` on an object is mandatory because an unsupported object is the
most common physically impossible thing a generator produces. `scale_anchor` is mandatory
because a size in metres means nothing to an image model: "its top meets the pharmacist just
above the hip" does.

That anchor is also a claim about two numbers the spec already carries, so it is checked
rather than taken on trust. Where it names a body landmark, the landmark's height is read
off the person's stature with the standard anthropometric fractions of Drillis and Contini
(1966), as tabulated in Winter, *Biomechanics and Motor Control of Human Movement*, figure
4.1 - the same measured family `EYE_FRACTION`'s 0.93 comes from, and this table's eye
fraction of 0.936 agrees with it. Eye 0.936, chin 0.870, shoulder 0.818, chest 0.720, elbow
0.630, waist 0.600, hip 0.530, wrist 0.485, fingertip 0.377, knee 0.285, ankle 0.039.

An anchor often brackets a height between two landmarks, as the worked example does with
"just above the hip, a little below her waist", so every landmark occurrence is read with
the hedge immediately before it and the bands are intersected. Where the bands do not
overlap at all, which loose prose can produce, their hull is used instead: refusing a brief
over phrasing would cost more than it catches. With several people in the frame and no name
in the anchor, no check runs at all, because a guessed referent would refuse a correct
brief. The same table gives the held-object rule: above about 0.30 of the holder's stature
an object cannot be described as filling a hand, and above 0.60 it is a two-handed load,
which is a warning rather than a refusal because a person really can carry a ladder.

`short_name` is what the compiled prompt and the review questions call the entity after it
has been introduced once, so a long description does not repeat ten times.

Every string in the blank template is a question in angle brackets. An unanswered one is an
error, so a half-filled template cannot become a prompt.

## What the measurements say, and what this module does about it

Four findings shaped the design. They are measurements, not opinions.

**Generated images are locally consistent and globally not.** Farid checked 25 DALL-E 2
kitchens and found every one had floor tiles whose vanishing point disagreed with the
counter top, and 25 sunlit-cube scenes whose shadows no single light position could
explain; 22 of 25 mirror scenes were plainly broken (*Perspective (In)consistency of
Paint by Text*, arXiv:2206.14617). The same split shows up in the lighting-environment
metric: across images, DALL-E 2 illumination matches photographs at R-squared 0.80, while
within one image pairwise consistency drops to 0.54 to 0.69 (arXiv:2207.13744). So the
question that finds the failure compares two things in the frame. "Does the counter look
right" passes; "do the counter and the floor converge on the same horizon" does not. Every
physics and geometry check in the rubric is written that way, and the compiler emits a
shadow-direction question for each pair of things that meets a surface.

**People cannot see these errors, so the checklist is doing real work.** Nightingale, Wade,
Farid and Watson measured d-prime 0.41 for shadow inconsistency and d-prime -0.01, chance,
for reflections, with a bias toward calling images consistent; only about half of subjects
could place a shadow within 10 degrees of correct (*Can people detect errors in shadows and
reflections?*, Attention, Perception and Psychophysics 81:2917, 2019). Subjects were even
told which object to look at. An unaided eyeball over a 1200 px image is not a review.

**Physics is not the common failure.** Kamali, Nakamura, Chatzimparmpas, Hullman and Groh
annotated 599 diffusion images and gathered 749,828 judgements from 50,444 people (CHI
2025, arXiv:2502.11989). Share of images carrying each kind of flaw: functional 58.7 per
cent, anatomical 51.4, stylistic 39.0, physics 9.17, sociocultural 5.50. What people
actually mentioned: anatomical 61, stylistic 30, functional 21, physics 15, sociocultural
4. A rubric that is all shadows and vanishing points returns "pass" while six fingers, a
guitar with slack strings and waxy skin walk through. The rubric therefore leads with
functional, anatomical and stylistic checks and keeps the physics ones because they are the
part people cannot do.

**Scale will not fix it.** Kang and Yue trained video diffusion models on 2D mechanics from
30K to 3M examples and 22M to 310M parameters: perfect in-distribution, measurable gains
combinatorially, and no out-of-distribution improvement at all. The models generalise
case-based, mimicking the nearest training example, and weight visual factors in a fixed
order, colour over size over velocity over shape (*How Far Is Video Generation from World
Model: A Physical Law Perspective*, arXiv:2411.02385, ICML 2025). A spec describing an
unusual configuration will not be rescued by a bigger model, which is the argument for
checking the brief first and the picture afterwards.

Geometry is also a generator-agnostic signal: classifiers trained only on perspective
fields, line segments and object-shadow relations catch images that defeat signal-based
detectors, and transfer across Kandinsky, SDXL, PixArt-alpha, DALL-E 3 and Firefly
(*Shadows Don't Lie and Lines Can't Bend*, CVPR 2024, arXiv:2311.17138).

## Geometry the spec derives

The camera is a pinhole with a 36 x 24 mm full-frame sensor; focal lengths are full-frame
equivalents. Depth of field is the thin-lens approximation with a 0.03 mm circle of
confusion.

| Derived | Formula |
|---|---|
| Frame width at a distance | `d * sensor_w / f` |
| Horizontal field of view | `2 * atan(sensor_w / 2f)` |
| Hyperfocal distance | `f^2 / (N * c) + f` |
| Near and far focus limits | `d(H - f) / (H +/- d - 2f)` |
| Apparent height, as a fraction of frame height | `(h * f / d) / sensor_h` |
| Apparent height ratio of two entities | `(h1 / d1) / (h2 / d2)` |
| Horizon crossing on a standing figure, from the feet | `h_camera / h` |
| Eye-line offset for a seated figure, in head heights | `(h_camera - eye) / (0.133 * h)` |
| A body landmark's height on a person | `landmark_fraction * h` |

Two facts come out of this that a prompt rarely states and a correct picture must obey.
The first is apparent size: a 1.68 m person at 1.5 m reads about 1.5 times the frame height
of a 1.62 m person at 2.2 m, so the nearer one is visibly larger although they are nearly
the same height. The compiled prompt says that in words, because a model cannot act on
"1.51x"; the exact ratio goes to the reviewer's questions instead.

The second is the eye line, and it is the most useful formula here. The horizon is the
vanishing line of the ground plane, so **any point at the camera's own height images onto
the horizon, whatever its distance and whatever the lens**. A standing person whose eye
height equals the camera height therefore has their eyes on the horizon: the rigorous
version of the painters' heads-on-the-horizon rule. In image rows, for anyone standing on
the ground plane,

```
h / h_camera = (y_base - y_top) / (y_base - y_horizon)
```

exactly, and independently of distance and focal length. Rearranged, the horizon crosses
every standing figure at the same fraction `h_camera / h` of its height. The spec derives
that fraction per person into `horizon_crossings`, states it in the prompt, and asks it as
a question the reviewer can answer with a ruler on the finished image: *does the horizon
cross the pharmacist about 96 per cent of the way up from her feet?* One camera height has
to explain every figure at once; anyone who does not fit is floating, mis-scaled, or
standing on a different floor. The general tilted case is Criminisi, Reid and Zisserman,
*Single View Metrology*, IJCV 40(2):123-148, 2000.

Camera height and camera tilt are different things, and conflating them is the usual
mistake. Height fixes which scene points are at eye level. Tilt only moves the horizon
within the frame, by `f_px * tan(theta)`. So an eye-level camera with the horizon at the
top of the frame is a contradiction unless a large pitch is also declared, which would then
tilt every vertical in the picture.

Eye height comes from posture, not stature alone: 0.93 of stature standing, which holds
across populations (ANSUR II gives 164.0/175.5 for men and 151.7/162.6 for women, and a
British 50th-percentile table agrees within a centimetre), 0.90 under about five years where
the head is relatively larger, and an absolute height above the floor for a seated or
kneeling figure, because the seat and not the stature sets it.

A seated or kneeling figure has an eye line too, and it is the only one available in an
interview, desk or restaurant scene, where nobody is standing. The fraction-of-stature
crossing does not apply to such a figure, so the offset between the horizon and its eyes is
derived instead, into `eye_line_offsets`, and stated in head heights rather than metres: a
head is 0.133 of stature on the 7.5-head canon, and head heights are a unit the reviewer can
count on the image with no external scale. Where nobody is standing, the `eye_level`
tolerance also tightens from 0.35 m to one head height, because the 0.35 m band is the
spread of standing eye heights across a population and that argument does not apply to a
height the seat fixes. A lens above a seated eye line is a high angle, not eye level.

Perspective distortion is set by the subject distance alone; the focal length only decides
the framing, so a longer lens does not rescue a camera held at arm's length from a face.
Inside about a metre the nose-to-ear depth ratio reads as a caricature, which is why
portrait practice is 1.5 m or more with a longer lens to keep the same framing. Both are
warnings rather than refusals, since a deliberate wide-angle portrait is a real choice.

## Prompt compilation

Every clause carries a group and a priority tier. Groups come out in a fixed order, subject
and action first because every model weights the opening of a prompt most heavily, and the
physics line last so a length limit never cuts it.

- Tier 1 is the picture: medium, scene, each subject's identity, action and hands, each
  object with its size and support, the camera, the horizon, the key light and its shadow
  direction, the composition, the quiet area, the locale details, the text ban and the
  closing physics line.
- Tier 2 is strong detail: pose, gaze, scale anchors, the derived scale and eye-line notes,
  focus falloff, the physical invariants.
- Tier 3 is the rest: expression, fill lights, palette, mood, texture, crop safety.

`images.spec.max_prompt_words` trims from tier 3 downward and never touches tier 1, and the
compile report says what it left out. Where the tier 1 clauses alone exceed the budget, the
report says that too, in those words, rather than reporting a trim that did not bring the
prompt under the limit. The default is `0`, which trims nothing: the author sees the word
count and decides. Length is not free, though. Across ten models, accuracy correlates
negatively with prompt length, and the hardest dimension of all is placing a subject in a
named region of the frame, at 11 to 54 per cent against 89 to 99 per cent for background,
lighting and style (DetailMaster, arXiv:2505.16915, whose prompts average 285 tokens).

### Two rules the compiler enforces, because the measurements are one-sided

**A positive prompt never carries a negation.** Not "no text", not "without cars", not
"free of logos". Applying a negative in the first few diffusion steps paradoxically
*generates* the forbidden object, through an inducing effect the paper traces step by step
(arXiv:2406.02965); across 4,800 prompts and 211,200 images the best model managed 31.4 per
cent accuracy on negation and **41.5 per cent of failed statements rendered the exact thing
the prompt forbade** (NegT2IBench, arXiv:2610.03084). Every vendor says the same in its own
words: a party prompted with "no cake" still gets a cake. So `validate_spec` refuses any
spec field that describes the picture by what it is not and names the field, and
`compile_spec` refuses a compiled scene that still contains one. Exclusions go in
`must_not_show`, which reaches the avoid list and never the scene description. The quiet
area for the headline is described the same way, as something that is there: an even wall,
an overcast sky above a low horizon, a plain backdrop, rather than a hole cut in a busy
frame.

**No number is emitted alone.** A number in a prompt is decorative; the words for its
effect are what steer. Measured against the request, with 1.0 as perfect agreement: colour
temperature scores 0.231 on SD3 and 0.236 on FLUX, focal length 0.236 and 0.200, shutter
0.273 and 0.240 (Generative Photography, CVPR 2025, arXiv:2412.02168). Aperture is no
better: requested-against-delivered blur correlates **-0.206** on SD 1.5 and -0.033 on FLUX
(Bokeh Diffusion, arXiv:2503.08434), and in one video test f/2.0 and f/8.0 produced the same
blur. So `5200 K` compiles to "neutral daylight at about 5200 K", `f/2.8` to "f/2.8, a
shallow depth of field, the background clearly soft", `50 mm` to "a 50 mm lens, a normal
view, close to what the eye sees". The number stays for the human reading the brief; the
phrase is what the model acts on. Recraft's and Adobe's own example prompts do exactly this.

The same applies to shot size. The taxonomy term is respected but the framing it delivers is
not: asked in words alone, models overshot the staged subject height by 1.73 to 1.91 times,
against 0.955 with geometric conditioning (PACE). So the prompt names the body fraction as
well as the term, "a medium shot, framed from the waist up".

What the research says to stop saying altogether, and what this compiler therefore keeps in
the schema but never emits as a bare value: light azimuth in degrees, light ratios,
high-key and low-key as names, shutter speeds, ISO, and the named portrait patterns beyond
Rembrandt and split. Elaborating the lighting prose is also not worth the words: four
prompt-complexity levels across four models produced no statistically significant
difference in light-direction accuracy. Spend the budget on the subject and the framing.

### Where the exclusions go, per generator

`images.spec.target_model` names an entry in
[`image-model-registry.json`](image-model-registry.json), which supplies `prompt_target` and
`max_prompt_words` unless the client config states them. That file is data, not code,
because model names, prompt limits and negative-prompt support change every few months; an
unregistered name is refused so the fix is a new row rather than an edit to the compiler.

`prompt_target` has three values, and the third is the common case:

- `negative_prompt` keeps the avoid list in its own field, for a generator that has one.
- `inline_constraints` appends a `Constraints:` block to the prompt, which is what OpenAI's
  own guide prescribes and tells you to restate on every edit.
- `none` emits no exclusions anywhere. The avoid list is still compiled and recorded, for
  the reviewer and for the audit trail, but nothing goes to the model.

`none` is the default for most of the shipped registry, and that is not conservatism. Of ten
current generators surveyed, three have a real negative channel and one of those is being
removed; the rest either never had the field or had it withdrawn, and their vendors all say
to describe the positive state instead. A compiler that treats the negative prompt as a
universal field spends most of its output on dead text. The familiar anti-artifact list
inherited from the Stable Diffusion 1.5 era is also unproven on current models, so the
shipped `default_avoid` is kept short and configurable rather than long and ritual.

`positive_only` is accepted as the old name for `inline_constraints`.

## The headline is overlaid, never generated

The quiet area in the spec is a bias, not a guarantee, and the pipeline is built so that
does not matter. Nobody benchmarks the one capability a cover image needs, which is whether
the model left a named region clear; the nearest published figure is 75 to 80 per cent on
absolute-position perception for the best models, and placing a subject in a named frame
region is the weakest dimension measured anywhere. Plan for the quiet area to fail one time
in four or five.

That is survivable only because the headline is real text laid over the image by the
template, not pixels drawn by the generator. Three independent reasons, and they agree:
WCAG 2.2 SC 1.4.5 requires real text wherever the technology can present it, excepting only
customisable and essential cases and treating a logotype as essential, so a baked-in
headline fails at AA while a CSS overlay passes trivially; `alt` is the attribute search
engines actually read, and no baked headline yields an indexable one; and a generated
headline cannot be corrected after publish, localised, kept contrast-safe over an arbitrary
background, or survive a crop that cuts through the type. A gradient scrim plus a headline
cell gives guaranteed contrast over any image, including the ones where the model ignored
the quiet-area clause. This is why `text_in_image` stays `none` and approved text is added
deterministically after processing.

The other half of the same decision is to over-provision the frame. Generate wider and
taller than you ship and crop deterministically, because the delivery set needs 16:9, 4:3
and 1:1 for Article structured data and 2:3 for Pinterest, and none of those can be cropped
out of a 1.91:1 frame. One taller source solves the crop set and the quiet area together.

## Plausibility review

`images.plausibility.checks` is the rubric: fixed questions about the things generators get
wrong, independent of any one spec. A client may extend or replace the list; an empty list
falls back to the shipped rubric, so a thin client config cannot quietly remove the gate.

The rubric runs in the order the prevalence data justifies. **Functional** first: could every
made object work, is it complete and unfused, is what is held held the way it is used, is
the lettering free of distorted glyphs. **Anatomical** next: finger and limb counts,
proportions, the eyes, teeth, ears and glasses close up, whether each person in a group owns
their own limbs, whether a hand closes around what it holds, where the gaze goes.
**Stylistic** next, which nothing in a physics checklist would have caught: waxy or plastic
skin, over-soft hair, a frame that does not look like one photograph, impossible
photoshoot perfection. Then the **geometry and physics** checks, written cross-entity:
shadows that agree with each other, shadow lengths against one light elevation, contact
shadows, support and balance, parallel planes sharing a horizon, figures on one ground
plane, the horizon crossing, relative scale, depth order, straight lines, focus falloff,
reflections and transparency, fluids and fabric. Then **sociocultural** locale truth, and
the composition checks for the quiet area and crop safety.

On top of the rubric, the spec compiles into its own questions: one per entity count, per
attribute, per action, per hand, per gaze, per support relation, per position, per derived
size ratio, per horizon crossing, per grounded pair, per locale detail, per invariant and
per `must_not_show` item.

How those questions are written follows the measured findings of the Davidsonian Scene
Graph work (Cho et al., ICLR 2024, arXiv:2310.18235), which sets four properties and shows
what each buys. Questions are **atomic**, one smallest semantic unit each, because
atomicity rises from 78.5 per cent under the earlier TIFA scheme to 96.5 per cent under
this one, and a non-atomic question gets an answer about the half the reader noticed.
Questions are **unique**, because duplicates silently re-weight the result. Coverage is
complete and invents nothing. And every child question names its `parent`, because
dependency gating raises per-question agreement from 65.2 to 73.8 per cent: a question
about an entity that is not there has no answer, and scoring it as a pass is worse than
leaving it out.

Three kinds of question are routed away from judgement entirely, with `verify_with`. A
vision model answers questions about rendered text at 13.7 to 24.9 per cent accuracy and
says yes almost whenever any text is present at all, and counting at 67.4 per cent, wrong
about 40 per cent of the time. Shot size, camera angle, lens and lighting are the third
case: across 24 vision models the best averaged under 60 per cent, with camera angle at 51
to 58 and lens at 44 to 49 (ShotBench, arXiv:2506.21356). So `verify_with: "ocr"` marks the
text checks, `"count"` the how-many checks, and `"geometry"` the camera, horizon and
apparent-size checks, which are measured on the image rather than judged. A human reviewer
should treat those three the same way: count the fingers, read the signage at full
resolution, and put a straight edge on the horizon instead of forming an impression.

A pass requires every rubric check `passed` or legitimately `not_applicable`, every spec
question answered `yes`, evidence on each one naming what was seen and where, and
`crops_reviewed` at least `zoom_grid^2`. `review-crops` cuts the optimized image into that
grid at `crop_scale` magnification, because a 1200 px image hides the failures that matter:
fingers, teeth, contact shadows, drifting tile repeats, gibberish on signage.

`not_applicable` is allowed only where the check's `not_applicable_when` permits it:
`no_people`, `non_photographic`, `no_locale_details`, or `absent_from_image` for the checks
about things a given scene may simply not contain, such as reflective surfaces or liquid.
Evidence is still required, and must say what is absent.

Reprocessing an image invalidates every previous approval, and the review records the
`image_sha256` it was made against, so a review never carries over to a different file.

## Limits

The physics here is first-order: a pinhole camera and a thin lens. It catches contradictions
in the brief; it does not prove a generated picture is correct. Nothing in this module looks
at pixels. The reviewer still looks, which is what the crops, the rubric and the evidence
requirement are for.

The review is a flagging system, not an oracle, and it should not be the only gate. The
best per-question agreement anyone has measured for an automated judge is about 74 per cent,
and item-level correlation with human ratings peaks near 0.40 against a human-to-human
ceiling of 0.45 (VIEScore, ACL 2024, arXiv:2312.14867). Automated physics judges also
produce false violations on genuine photographs: one evaluator scored real footage of
bouncing balls at 0 per cent physical-rule adherence (arXiv:2504.02918). Budget for false
positives, and keep a person behind the gate.

Where a generator supports it, the stronger move is to stop describing the spec and start
conditioning on it. The spec already names every person and object with a position, a size
and a distance, which is exactly the intermediate representation that layout-conditioned
generation consumes: per-instance boxes or masks (InstanceDiffusion, arXiv:2402.03290,
which reports +20.4 AP50 on box inputs and +25.4 IoU on mask inputs), grounded attention
(GLIGEN, arXiv:2301.07093), or depth and pose maps (ControlNet, arXiv:2302.05543) where
depth enforces the declared distances and pose enforces limb counts and plausible
articulation. Compiling the spec to a prompt is what this module does today because it
works with any generator; compiling it to a condition is the obvious next step for a client
whose generator accepts one.
