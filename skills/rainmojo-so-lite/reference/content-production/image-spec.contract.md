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
- a `foreground` entity at 9 m is not in front of a `background` entity at 3.6 m.

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
| `location` | `place`, `locale`, `time_of_day`, `weather`, `locale_details[]`, `reference{}` for a real place |
| `realism` | `imperfections[]`: located flaws, required for a photograph |
| `camera` | `shot_type`, `angle`, `tilt`, `horizon`, `height_m`, `focal_length_mm`, `aperture_f`, `subject_distance_m`, `focus_on` |
| `subjects[]` | `id`, `short_name`, `kind`, `count`, `description`, `appearance`, `wardrobe`, `posture`, `pose`, `hands`, `gaze`, `expression`, `action`, `position`, `height_m`, `ground_height_m`, `distance_m`, `plane`, `reference{path,rights,origin}` or `reference_image` |
| `objects[]` | `id`, `short_name`, `name`, `count`, `material`, `state`, `size`, `height_m`, `width_m`, `ground_height_m`, `extends_beyond_frame`, `scale_anchor`, `support{kind,by}`, `position`, `distance_m`, `plane` |
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

`short_name` is what the compiled prompt and the review questions call the entity after it
has been introduced once, so a long description does not repeat ten times.

Every string in the blank template is a question in angle brackets. An unanswered one is an
error, so a half-filled template cannot become a prompt.

`interacts_with[]` is still accepted on a subject or an object, and its ids are checked,
but nothing else reads it: blanking it in both shipped examples leaves the prompt, the
questions and the warnings byte-identical. It is no longer in the blank template, so an
author does not spend time on a field with no effect. Contact between a person and a
thing is carried by `support{kind: held_by, by}` instead.

## What validate_spec refuses, and why

Each rule below refuses a brief, or warns on one, from fields in the spec alone. The
message names the field and says what would fix it. Every rule here has been run against
sixteen real client briefs, but several are reached by none of them, among them face
distance and the conditioning rights, and are vouched for by the contract test alone; see
"Measuring the review".

| Rule | Fields | Refuses or warns when | Why |
|---|---|---|---|
| Body landmark | `objects[].scale_anchor`, `height_m`, `ground_height_m`, `support.kind` | An anchor names a landmark on a person ("just above the hip"), and the object's top, `height_m + ground_height_m`, is more than 0.12 m from that landmark on that person. Landmark fractions: eye .936, chin .870, shoulder .818, chest .72, elbow .630, waist .600, wrist .485, hip .530, thigh .420, fingertip .377, knee .285, ankle .039 (Drillis and Contini; Winter, fig. 4.1). | A size the model can read is a size against a body; one that disagrees with the metres is a contradiction the picture will resolve at random. |
| Which landmark, which person | the same | The first landmark the anchor names is the claim, so "just above the hip, a little below her waist" is checked at the hip. The person is the one the anchor names by id or `short_name`, or the only person in frame. With several people and none named, the rule does not run. | A wrong referent produces a confident error about someone the author never mentioned, which is worse than no check. |
| Not a height | the same | No landmark check when the anchor talks about width or length ("as wide as her shoulders"), or the object does not stand or rest on a surface (it hangs, is mounted, fixed, held, worn or floats), because then `height_m` is its own length and not a height above a floor. | Comparing a banner's length with a hip is meaningless. |
| Held in one hand | `scale_anchor`, `support.by`, `height_m` | An anchor says it is held in a hand (not "a hand's width", not "a palm tree") and the object is over 0.60 of the holder's height (refused) or over 0.30 (warned). The holder is `support.by` for `held_by`, else the person the anchor names, else the tallest person in frame. | A child cannot hold in one hand what an adult can. |
| Support | `objects[].support{kind,by}` | `kind` is missing or not one of `rests_on`, `stands_on`, `mounted_on`, `hangs_from`, `fixed_in`, `held_by`, `worn_by`, `floats_in`; `by` is empty or names nothing that bears weight ("thin air", "nothing", "floating"); or `held_by`/`worn_by` names something that is not a person. | An unsupported object is the commonest physically impossible thing a generator draws. |
| State | `objects[].state` | Empty. | "New", "worn", "open", "lit" and "wet" are what make an object a particular one rather than the model's average. |
| Wider than the frame | `objects[].width_m`, `distance_m`, `extends_beyond_frame` | An object is more than three times the width the lens covers at its distance, and `extends_beyond_frame` is not set. | Either the numbers are wrong, or the thing genuinely runs past the edge (a floor, a roof deck, a lake) and should say so, which keeps `width_m` its real size for every ratio computed from it. |
| Raised or lowered floor | `ground_height_m` | Never refused. It is relative to the camera's own floor and added to eye height and to an object's top, so a fighter on a 1.2 m ring and a spectator at ringside cross the horizon at different points on their bodies; it is negative for someone below that floor, such as vendors in a boat under the landing the camera stands on. | Getting it wrong is how a picture ends up with a fighter whose eye line matches a spectator's. |
| Eye level | `camera.angle`, `height_m`, people's posture | `angle: eye_level` with the lens more than 0.35 m from the mean eye height of the people in frame, or 0.15 m when nobody in frame is standing. Seated eye height is 1.23 m on a chair and 0.78 m on the floor (`floor_seated`, `cross_legged`) for a 1.65 m adult (ANSUR II sitting eye height); the body's share scales with stature and a 0.45 m chair seat does not, so a seated 1.02 m child's eyes are at 0.93 m, not an adult's 1.23 m. A posture the geometry does not know is warned, because that person's eye line is then not checked. | Eye level is a height, and a seated eye line is the only one in a desk or restaurant scene. |
| Hard light in diffuse weather | `lighting.key.quality`, `location.weather` | A hard key with overcast, rain, fog, mist, haze or snow in the weather, unless the weather also says the sky is clear or sunny ("a clear sunny morning, a light haze in the distant canopy" is hard sun). | An overcast sky is the light source, and it is the size of the sky. |
| Said twice | a subject's `hands`, an object's `state` and `material` | Warns when an object's state names, as a single thing of its own, what a person's hands already hold ("a spoon and fork on each" beside hands holding a spoon and a fork). Plural stock ("a tray of empty cups") and a word used as a modifier ("the handpiece cable") do not count. | The generator draws it twice: run 05 and 06 put a third utensil on a plate. |
| Head or person out of frame | `camera.height_m`, `horizon`, `focal_length_mm`, each person's `distance_m` | Warns when, with a level camera, the frame's top edge at the focus person's distance falls below the top of their head, and when any declared person lies wholly below or above the frame at their distance. With the horizon not visible, a level camera still puts the horizon row at the frame centre, so indoor scenes are checked too. | A level camera puts the horizon row at the lens height, so the horizon band and the frame height there fix what of the person is shown; a 0.86 m lens at a medium shot with the horizon in the middle cuts off the head while the shot type says waist up. |
| Face distance | `camera.focal_length_mm`, nearest person's `distance_m` | The nearest person is closer than 0.9 m on any lens, or 1.0 m at 28 mm and 1.2 m at 20 mm. | The nose renders `(d + 0.10) / d` times the scale of the ears, set by distance alone; a long lens up close only crops into it, and a wide lens adds its own stretch toward the edges. |
| Located imperfection | `realism.imperfections[]` | A photograph with fewer than two (the client's `min_imperfections`); an entry under four words is warned as too short to place. | An unplaced flaw is decoration. A placed one ("a scuff on the counter edge by the till") is what reads as a photograph rather than a render. |
| Forbidding what is shown | `must_not_show[]` against every declared name | An entry that reduces to a declared thing's name and nothing else ("a counter", "counters"). Any state, attribute, place, quantity or coordination ("a cluttered counter", "a second counter", "pills on the counter") is a constraint and is accepted. | The model would be given the thing twice, once as content and once as a prohibition. |
| People implied | `purpose`, `subjects[]` | Warns when the spec declares nobody and the purpose describes a human act ("is handed over", "as its customers meet it"). Verb forms only, so "an explainer" or "the consultant's empty office" do not warn. | The purpose opens the prompt and outweighs an empty subject list: two of six zero-subject client briefs came back with people. |
| Real place | `location.reference{}` | With `place_is_real`: no `place_name`; fewer than two `sources` (the client's `min_reference_sources`); a source without `url`, `publisher`, `shows`, `accessed`, a known `viewpoint` and `rights`; no `verified_facts`, or one that hedges; and no source that shows the space from where the camera is. Inside needs an interior viewpoint; outside needs an exterior one; a staff portrait or a product shot never answers for a room. A `state` other than `existing` warns that the image is a visualisation. | A picture of a named place that gets it wrong is worse than a generic one, because the client's own customers know the room. |
| Conditioning rights | `reference.conditioning_images[]`, `subjects[].reference{path,rights,origin}`, `subjects[].reference_image` | Every image fed to the generator needs its own provenance: a row in `sources`, or the subject's own `reference` block with `path`, `rights` and `origin` ("lock sheet cast/pim v3"), independent of any real place. Any recorded rights value may condition, `client_owned`, `licensed` or `reference_only` (owner decision, 2026-10-26); a `reference_only` image warns that the published file must be the generated image and never the source. The older `reference_image` must match a row in `location.reference.sources` whether or not the place is real: before, with `place_is_real` false, it was fed with no provenance check at all. | Every input to the picture is on record, so a reviewer can see what it was built on, and the source of a reference-only image never reaches the page. |
| A writer's note as a locale detail | `location.locale_details[]` | Warns when a detail talks about the text itself ("is named exactly", "written out", "described as"). | It becomes a question no picture can answer; in run 10 the reviewer rightly answered no to "the species is named exactly". |
| Light inventory | `openings[]`, `practicals[]`, `lighting.key.source`, `lighting.fill[]` | Optional. When declared, the key light must come from a lit opening or practical (refused otherwise), a fill that is a source and not a bounce should be listed (warned), and lit openings facing each other with no fill are warned. The prompt says the lit entries are the only light and every other opening is dark; `q_light_sources` and `q_<id>_state` ask it. | A second lit window appeared where one was allowed, and nothing asked about light sources. |
| People never matched | `subjects[].variation` | Refuses a person whose `variation` declares a matched set ("matched", "identical", "uniform"). A matched set of things keeps any difference its `variation` names ("identical model, one with a cracked corner"), in the prompt and in its question. | Owner rule: people in a scene never look alike. A shared uniform is wardrobe, and each person keeps a face, build and age of their own. |
| Relative size, an experiment | `relative_size_clause` (default false), `support.by` naming an object `id`, both `width_m` | Must be true or false. With it true, each thing resting or standing on a declared supporter, between a twelfth and the whole of its width, is said as a fraction of it: "Each bowl is about a third as wide as the table". `derive` gives the same ratio in `relative_widths` either way, so the checking side measures the number the prompt states. | Metres are inert in a prompt; a relation to the thing beside it in the frame may not be. rangsarn runs it on against off on five scenes fixed before generating; until a result, it stays off. |
| Scale anchor as posed | `objects[].scale_anchor`, the named person's `posture` | A landmark is measured on the person as posed: standing from the standing proportions, chair-seated from a 0.45 m seat (eye, chin, shoulder, chest, elbow, waist, lap, thigh above it; knee from the floor), floor-seated from the floor, the body's share scaled by stature. An anchor that puts its person in a posture they are not in ("the mid-thigh of the surgeon standing" for a seated surgeon) is warned and left out of the prompt and the scale question. | Nobody can draw or check a pose the person is not in, and the prompt would tell the generator to stand him up. The landmark table was standing only, so authors had no other way to write it (the sweep session, s45 and doctorjay). |
| Style reference | `style.reference{path, rights, origin}` | Path, origin and rights are required, rights one of `client_owned`, `licensed`, `reference_only` (warned). The prompt says to take only its line, texture, palette and finish; when the spec sets its own palette (`color_palette`, or a monochrome look), only line, texture and finish, so the more specific source wins and the prompt names one palette. Both present is warned: the reference image still carries its own colours, so use a swatch in the spec's palette or drop the colour words. In rangsarn's A/B the reference moved palette and medium where three rounds of words had not (9 of 9 pairs), its brand colours beat the spec's "one amber wash" in every arm, and a master with a subject leaked it: lotus leaves in 6 of 6 misty images from the full master, 0 of 3 from a subject-free crop of its wash, which kept the medium. A reference is a subject-free crop of approved art, with frames and borders left out, and its `origin` names what it was cut from. `conditioning_references()` lists it with the place and likeness images, each with its role and rights. | Approved channel brand art and lock sheets may set the style (owner, 2026-10-26); where words failed to make a drawing read as ink, an image may. |
| Negative space kept clear | `composition.negative_space`, each subject's and object's `position` | Warns when a position's opening phrase names the same part of the frame the negative space reserves ("overhangs the top left corner" in a reserved upper left quarter). A position relative to another thing is placed through that thing: "the lower right of" a centred notebook is the lower right of the frame, "the upper right of" a counter placed at the lower left is the lower left. A thing the quiet area is described around ("the sky above the canopy") shares its region and is warned too, more softly. Both were first exempted, and the sweep's images showed both collisions happen: the canopy filled the reserved quarter in all three drivehub pictures. | The headline is laid over that region; the sweep session's viewpoint arm put a panel there and the review made it the worst fault. |
| Where exclusions go | `images.spec.target_model`, `images.spec.prompt_target` | `prompt_target` empty (the default) lets the registry entry for `target_model` decide: `inline_constraints` for gpt-image (Codex, ChatGPT), `none` for Gemini, `negative_prompt` for a model with that field. An explicit `prompt_target` wins. With neither set, the exclusions go inline (owner decision, 2026-10-26), and compile warns that a Gemini or FLUX host should name its model. A drawing's closing medium line stays last, after the Constraints block. | Until `e6704f9` the shipped `prompt_target` overrode the registry, so a gpt-image client lost its exclusions to a field the model does not have. No client config names its generator, so the fallback decided every client: as `negative_prompt` it was the sweep's `none` arm, which drew stray people and a terminal sign that the inline arm did not. |
| Palette contradicted inside the spec | `style.color_palette`, `style.look`, locale details, each object's and subject's name, material, state, wardrobe, appearance | When the palette restricts (a drawn monochrome look, or "only", "limited to", "duotone" in the palette), warns on a field that asks for several colours ("different colours", "multicoloured") or names a colour the palette does not hold. A palette that describes, as every client brief's does, restricts nothing, and a photograph's "charcoal" suit is not a monochrome drawing. | rangsarn's interior: a pack's "spines of different heights, colours and thicknesses" sat beside "one amber wash only", and the coloured spines won in every arm. A statement about the whole picture loses to the colours of the things in it. |
| Physical checks | `physical_checks[]` `{check, trigger, ask, prompt}` | A check needs its words; `trigger` must compile as a pattern; `ask` and `prompt` must be true or false. A check applies only when its `trigger` matches the scene's own words (purpose, place, what people do, what is there): then it is asked as `q_check_NN` in group `check` unless `ask` is false, and said in the prompt only when `prompt` is true. Its words pass the same lint as any prompt field. | A rule an untriggered scene carries is noise twice, in the prompt and as `not_applicable` in the review. Group `check` is counted apart from recall, because whether the generator was told changes what a pass means; rangsarn measures `prompt` true against false on five or more triggered scenes, fixed before generating, and leaves it false with fewer. |
| Support capacity | an object that `stands_on` another object's `id`, `width_m`; a person standing or sitting "on the <object>", or whose `position` opens with it | Warns when what stands side by side on a declared supporter is wider than it: each thing its `width_m` times its `count`, a person 0.5 m standing and 0.6 m seated. Only what stands: what `rests_on` a surface is set out in two dimensions and on tiers (plates on both sides of a table, cartons on five shelves), so a sum of its widths says nothing, and leaning on a counter is not standing on it (the lite session). Only above 100%, which cannot be; a set table is near full, so crowded is the reviewer's. `derive` reports `support_loads` with how many resting things were checkable. | A 0.5 m bund carried a buffalo and a man in rangsarn's scene. On our 16 client specs it checked 0 of 70, since none names a supporter by id: it covers what a spec declares, nothing more. |
| Seat and table | objects named as a seat and as a table, `height_m` | Warns when a declared seat has no table at the height EN 1729-1 pairs with a seat of its height, ±0.04 m. The standard's eight size marks put the table 0.19 m above a 0.21 m seat up to 0.31 m above a 0.51 m one (PN-EN 1729-1:2007; 2015-era guides give the same pairs); between rows it interpolates, beyond them it holds the end row. The pairing reads furniture against furniture, never the sitter's stature: at a family dinner a child sits at the adults' table, and is right to (rangsarn). So an adult stool at a child-height table, or a stool far below a full-height one, is caught; a 0.45 m street stool at a 0.72 to 0.75 m folding table passes. A high chair, a bar stool and a coffee table are not seat or table names on purpose: each pairs differently. Bands include a street plastic stool, a folding table and a low floor table, all conventions, and a tuk-tuk and a motorcycle. A name is matched on its head noun, so "folding steel tables with plastic stools" is tables. | Whoever sits at it is drawn too low or too high for the table. |
| Unseeable exclusion | `must_not_show[]` | Warns on an entry that names a provenance or an origin ("plants from outside Southeast Asia", "imported", "made in"). | No reviewer can see where a leaf was grown, so the question can only be answered `cannot_tell`. Name what such a thing would look like. |
| Floor left at the camera's | `subjects[].position`, `ground_height_m` | Warns when a standing person's position puts them on a declared thing at least 0.2 m high ("on the landing", "on the stage") and their `ground_height_m` is 0. | Their eye line and their floor are then measured from the camera's floor, and they are grouped there with everything else. |
| Lint | every prose field that reaches the prompt | Negation, quality boosters, similes ("hands like a pianist's"; "what X is really like" is an idiom and accepted), a pose named by its effect ("a confident pose"), camera words in a drawing, and hedges in `verified_facts` (maybe, probably, reportedly; not an approximator such as "about as wide as" or "roughly square", and not "around the square"). Audit fields such as `sources` and `conflicting_claims` are exempt, because they never reach the prompt. | Each of these is measured to cost fidelity, or to put the compared thing in the frame. |

## What the review asks that the brief cannot

The compiled questions also carry rules of their own, which shape the review rather than
refuse the brief:

- **Framing follows `camera.focus_on`.** A person in focus is asked about a body fraction
  ("framed from the waist up"); an object in focus is asked about the shot ("a medium shot
  of the counter"), never about a waist it does not have.
- **Depth of field asks how soft, not whether softer, and only where it shows.** Anything
  whose blur circle is at least three times the 0.03 mm circle of confusion is asked
  whether its edges are blurred and any lettering on it unreadable, because "softer than
  the pharmacist" is yes for any blur at all. A thing just past the depth-of-field limit
  is acceptably sharp by the definition of that limit, so it is not asked: in rangsarn's
  run 01 a box at 2.0 m against a 2.05 m near limit (1.4 circles of confusion) was
  answered no on a correct photograph. The prompt still names it as outside the focus.
- **Fingers are counted where they can be.** A hand holding a spoon, a paddle or a box
  covers some of its fingers; asking for "no finger hidden behind another" failed 10 of
  10 such hands in run 01. The question asks for five wherever they can be counted, none
  extra, fused or bending the wrong way, and `cannot_tell` where none can.
- **Position asks where someone is placed**, never whether they stand, which a seated
  person fails, and it is measured: position and crop-safety questions route to
  `geometry` and are answered in fractions of the frame. In rangsarn's run 02 all four
  remaining misses were in-frame position and scale, judged by eye.
- **Things on the camera's floor are pinned to the horizon too.** The horizon crosses
  anything standing on the camera's floor at camera height over its height, the same
  identity as for people (Hoiem et al. put cars on it). A grounded thing from 0.5 to
  4 m tall and within 30 m, single, not running past the frame, gets a crossing
  question, and one a metre or taller a prompt sentence: "That horizon line crosses the
  car about 68 per cent of the way up". A far building is left out, because it may not
  stand on the camera's floor. Any tool that measures this against a horizon it
  calibrated itself should answer firm only when that horizon agrees with the one the
  people give: rangsarn's GeoCalib put a street horizon 100 rows low, which read a 1.5 m
  tuk-tuk as 2.6 m.
- **A scene that pours is told and asked where the liquid leaves.** A ladle scene drew
  broth falling from beneath a bowl; a scene whose action pours, ladles or waters
  carries the rule that liquid leaves at the lip and falls in one arc.
- **A count is counted where the thing is.** Something supported by another declared
  entity is counted there: "exactly 3 baskets resting on the near sampan", because in
  rangsarn's run 04 a far boat carried a fourth. A surface named only in words does not
  scope the count.
- **A crossing on a figure the frame cuts is asked at a landmark.** "At about the eyes"
  rather than "96 per cent of the way up from the feet" when the feet are out of frame;
  a crossing that falls between landmarks is not asked, and neither is one at a landmark
  the frame does not show. Each crossing records the lowest part of that person in the
  picture, from their distance, the frame height there, the lens height and where the
  horizon sits in the frame. The prompt describes a cut figure's crossing the same way.
- **Scale is judged in real size.** Every scale question says to judge real sizes, not
  how large each looks at its distance: run 04 compared a near buyer with far shutters
  as drawn.
- **An invariant is checked part by part.** Most invariants read "cause, so effect and
  effect", so each question says to check each part on its own, answer yes only if every
  part holds, and name each part in the evidence; a comparison of sizes in one is judged
  in real size. In rangsarn's run 08 a serving spoon's invariant passed on its bowl alone
  while its handle rested on another plate. Writing one fact per invariant is better
  still; a validator warning was not added because it would fire on 37 of 85 real ones.
- **Hands are asked one at a time.** Every clause in a hands field that names a side
  gets its own question, whether that hand holds something ("a spoon in the right
  hand"), rests ("her left rests on the chair arm") or gestures ("his right hand is
  raised"); the client sweep's four real which-hand catches were all of the last three
  kinds. Each is asked from the person's own side, with the picture side stated when the
  spec says which way they face (a place such as "from behind the head of the bed" is
  not a facing), and with the person's own pronoun; a person with their back to the camera is told in the prompt that their own
  right hand is on the right of the picture. "A utensil in each hand" passed a spoon and
  fork held the wrong way round in rangsarn's run 05.
- **Contents come from their source.** An object may declare `filled_from`, the ids it
  takes its contents from; the prompt says it holds only what they provide and the
  review asks it. Run 05 drew fried rice on plates served from three dishes that could
  not make it.
- **A child question is skipped only when its parent thing is absent.** When the parent
  fails on count or kind, every question below it is still answered: run 04 skipped the
  missing steam and serving spoons because the dish was on a plate, not in a bowl.
- **A stature is asked only where it shows**: of a person standing, walking or leaning
  whose whole height fits the frame. Seated and cropped people gave 8 honest
  `cannot_tell` answers in run 02.
- **A support outside the picture** ("fixed in the trunk, out of frame to the right") is
  asked as whether the thing runs out of the frame toward it, never for a contact shadow
  nobody can see.
- **One floor per floor.** The shared-floor question groups the people and things that
  stand on the same surface: the same `ground_height_m`, or the same declared entity for
  a thing resting on another. A man on a raised landing and baskets inside a boat are not
  asked to share the quay's floor.
- **Ratios a person can read.** A height ratio is asked only between 1:8 and 8:1; beyond
  that it cannot be read off an image and only adds `cannot_tell`.
- **The declared fill is named** in the light question, so a reviewer does not count it as
  a second key light.
- **Nothing undeclared** (`q_undeclared`, counted) and **no invented glyphs**
  (`q_malformed_glyphs`, read as text) are asked of every image: a count of declared
  people says nothing about twenty extras in the lane, and illegible pseudo-lettering is
  still lettering.
- **People do not look alike, and repeats are not copies.** The owner's rule, after
  rangsarn's run 03 drew two vendors with one face. Two people described with 60% or more
  of the same trait words (description, appearance, wardrobe) are warned, because a
  generator draws one face for both. Every scene with two or more people carries a prompt
  clause that each has a face, a build and an age of their own, and a `q_distinct_faces`
  question that compares the face crops side by side. Anything with a count above one
  takes a `variation` field that the prompt carries ("one deeper and darker with age, one
  with a split rim"), is warned without one, and is asked whether each looks like a real
  one of its own rather than one image repeated. A set that is alike by design, a moulded
  pair of sculptures or panels on one rail at one tilt, writes `variation: "matched"`: it
  is not warned, the prompt says it is matched by design, and it is asked whether each
  sits in its own place with its own light and perspective rather than whether they
  differ. People cannot be matched.
- **A count counts the thing.** A name that lists contents across its count ("3 round
  woven bamboo baskets of bananas, pomelos and mangoes") is counted as the baskets, and
  each content is asked on its own ("Does one of the round woven bamboo baskets hold
  mangoes?"). In run 03 the fruit rode along in the count question, which passed on
  bananas, pomelos, bananas. A single thing whose name lists its parts is not split.
- **Every routed question carries a `measure`**, a structured statement of what a tool
  should find: `count` (entity, label, `is_person`, `detect_as`, expected), `finger_count`, `framing`
  (entity, `is_person`, shot), `camera_angle`, `horizon_band`, `eye_line` (the standing
  ids), `height_ratio` (a, b, expected), `viewpoint`, `horizon_fraction` (entity, relation,
  expected fraction from the feet), `undeclared` (expected people, declared ids), `glyphs`
  and `text`. A measuring tool maps its reading onto the question through this, never by
  parsing the id. A pose estimate counts only inside a box a detector called a person:
  a pose model fits a full skeleton to a frog. `detect_as` is a plain class noun, the
  `detect_as` field when the spec gives one, otherwise "person" for a person and the head
  noun of `short_name` for a thing, with a collective resolved to its members ("tent
  row" is "tent"). Role names as detector queries ("near vendor", "grandmother", "shared
  dishes") were counted 0 by both open-vocabulary detectors in run 01 on pictures that
  plainly showed them; the role is the reviewer's to check, the count the detector's.
  When a thing's short name is a rare or specific noun, give `detect_as` the word a photo
  caption would use, and keep the specific noun in the description: `boat`, not sampan;
  `pier`, not landing; `bowl`, not dish; `house`, not shophouse. Those are the nouns
  Grounding DINO and OWLv2 found in run 01, and the rare ones are what they missed.
- **The eye line is asked only where it exists**: a horizon in frame and at least one
  standing person. A horizon that is not visible or falls outside the frame gets
  no question about where it crosses anyone.

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

## Prompt compilation

Order matters, because a model weights the opening of a prompt most and drops what comes
late. The opening says the medium, the purpose and the viewpoint; the locale follows it
directly. Locale facts are the ones a common-world prior overrides: an independent audit
of rangsarn's 20 pictures found a Bangkok floating market drawn with Vietnamese conical
hats, a Thai pharmacy as a generic stock shop and figs as crabapples, all from facts that
sat late in the prompt. A person's distinguishing traits follow their identity in the same
sentence, before wardrobe and pose.

A drawn picture is told it is drawn from start to end. In rangsarn's run 10 all three
monochrome drawn styles (black ink line art with one warm wash, ink and charcoal with one
cold wash, ink-wash landscape) came back as full-colour painterly or near-photographic
pictures while the painterly styles held: the style sat only in the opening, and the
compiler's own sentences still spoke photography. For a drawn medium the light carries no
colour temperature in kelvin, lettering is "loosely indicated" rather than "out of focus",
the physics line speaks of one viewpoint rather than one camera, and the closing line
restates the medium and the look. A monochrome style has its light and shade described in
its own tones, and fills given as colours are left out.

The viewpoint is said in pictures, and only where it is true. A camera that looks down
shows the tops of heads, so that wording needs a downward tilt, a high angle or the lens
more than 0.5 m above a head, and never sits beside an eye-level angle. A level camera a
little above seated eyes is said as what it is: the horizon passes just above their heads
while their faces are seen straight on. The audit found the contradiction in rangsarn's
river market; it was in three of our own client prompts too.

When a viewpoint has to hold, write it into the scene as something only that viewpoint
can show. Said as an instruction ("from low, the lens below the panels' raised edge"),
it failed 4 of 4 times across two scenes, once drifting down and once up; written as
visible content (the underside and junction box of the nearest panel in a corner, which
exists only from below its edge), it held 2 of 2 (the sweep session, ringside and
sustainmap). Two lessons came with it. A viewpoint invariant written from the content
overclaims easily: "the panels beyond are seen edge-on" is false for a tilted panel that
faces the camera, and the review rightly said no, so say only what the content proves.
And the content must not land in the region `composition.negative_space` reserves: the
first content arm did, and its review made that the worst fault, so the validator now
warns on it.

Every clause carries a group and a priority tier. Groups come out in a fixed order: the
opening, then the locale, then the subjects and their action, because every model weights
the start of a prompt most heavily, and the physics line last so a length limit never
cuts it. Where the spec puts the horizon outside the frame, the prompt calls it the
eye-level line, so an indoor picture is not invited to grow a window or a skyline.

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

Some words that look like negations are what the picture shows, so the rule leaves them
alone: lettering in double quotes (a sign reading "No Smoking"), all-caps signage (NO
PARKING stencilled on the kerb), a number (the No. 9 bus), a hyphenated compound (a
no-frills canteen) and "not only". The booster ban works the same way. Words that are never
a fact about a scene ("masterpiece", "hyperrealistic", "trending on artstation") are refused
wherever they appear. Words that are a fact somewhere ("a perfect circle", "an award-winning
chef", "a Sony 4K camcorder", "The Epic Theatre", "the label in sharp focus") are refused
only as a bare list item, which is how a booster is written: "photorealistic, 8k, best
quality". These exemptions came out of the rangsarn session's independent review of its own
lint, which belongs to the same rule family.

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

`ocr` names the method, reading the lettering on the crops at full resolution, not an OCR
engine. Two were tried on rangsarn's run 01 and both were worse than a reviewer on 2x crops
at finding pseudo-lettering, which the reviewer got right on 5 of 5 pictures: PP-OCRv4
marked 22 regions of food, figs, a face and moss as text on four text-free pictures and
missed the pseudo-lettering on the pharmacy carton, and Florence-2-large invented digit
strings on every picture. An engine may answer `q_no_text` only when it reads real text
with confidence, which is useful for checking an overlay headline the pipeline rendered
itself; it never answers `q_malformed_glyphs`.

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

## Measuring the review

The review is measured the same way in rainmojo-so and in rangsarn, so the two numbers can
be compared. The definitions were agreed between the two projects.

| Measure | Definition | Target | Last measured |
|---|---|---|---|
| Recall | Faults the review answered `no`, over faults in the ground truth | 90% pooled, and **no group below its floor**: people 80% | 73% (40 of 55; objects 87%, places 83%, people 55%), 16 client scenes, before the `c2761f5` template fixes, on truth reconciled after reading the GPT review; **63.5% (40 of 63; people 41%) against the blind first reading alone**, which was itself wrong on 9 claims. Clean, against faults the human found and a reader who never saw a review confirmed: **65.9% (27 of 41; people 42%, objects 77%, places 75%)** |
| False-alarm rate | `no` answers on things that are correct, over all answers on correct things | 15% | Not yet measured as a rate on either side |
| Unanswerable rate | `cannot_tell`, counted only where the thing asked about is visible in the frame | Report it | Not yet measured |
| Attribution | Each miss and each false alarm traced to the question template that produced it | Every one | 12 of 15 misses traced to three templates |
| First-generation pass | Images that pass on their first generation | A goal, never a gate | Not tracked |

rangsarn measured the same table on its own five specs with this module, codex-imagegen
and a codex reviewer on 2x crops. Run 01 (050ea4e): recall 79.1%, people 68.4%, false
alarms 16.8% once rescored under the merge rule below. Run 02 (f88e7ef, after the run 01
template fixes): recall 91.3%, people 78.9%, every other group 100%, false alarms 17.8%,
unanswerable 12.0% of visible questions. The same run measured prompt length for the
first time: tier-1-only prompts about 30% shorter (689 to 1223 words against 946 to 1769)
drew 44 spec faults against 46 over about 400 visible checks each, so trimming tiers 2 and
3 cost no compliance there. Five specs is a small sample.

These rules make the numbers mean something:

- **Ground truth is read at the reviewer's magnification.** The first measurement read the
  full 1200 px frame while the reviewer had 2x crops, and 9 of the person's 63 claims were
  wrong; in 6 of those 9 the review had already answered correctly. At different
  magnifications the comparison measures the reader's screen, not the review.
- **Every visible hand gets its own crop at 6x or more, and Thai lettering is read by a
  native reader.** Magnification of the whole frame was not enough: a patient's fingers
  too long for the mirror handle she held passed two readings with 2x crops and was found
  by the owner at 8x, and a malformed Thai letter was softened to "close to correct" by a
  reader who does not read Thai.
- **Truth is never reconciled against one reviewer.** A fault a reviewer found and the human
  then adopted counts in that reviewer's favour twice, as truth and as a catch. rangsarn's
  runs 04 and 05, reviewed by GPT and by Claude on identical inputs: GPT 88.0% and Claude
  74.7% against truth that had adopted GPT's finds, but 71.8% and 65.9% against the blind
  reading alone. Our own 73% has the same property: nine first-reading claims were withdrawn
  after the reviews were read, six of them where the review was right, and against the blind
  reading alone the figure is 63.5%. So the base is the
  blind reading at the reviewer's magnification, and every reviewer's further claims are
  pooled and adjudicated by one procedure, without the adjudicator knowing which reviewer
  made them. A comparison between reviewers is valid only on truth built that way.
- **A pooled figure never stands alone.** Faults involving people are fewer than faults
  involving objects, so a pooled 90% can hide a people group at 60%. Each group is reported
  against its own floor.
- **A measurement that cannot decide does not override the reviewer.** Where a tool
  answers through `measure`, its answer wins only when it is firm, yes or no. An
  uncertain measurement falls back to the reviewer's answer. Under the first merge rule
  39 machine-uncertain answers sat on top of correct reviewer yeses in rangsarn's run 02,
  and that rule moved false alarms and unanswerable answers more than anything else.
- **Every proposed rule is run against the real-brief corpus before it lands.** A battery of
  mutations cannot see false positives, because every mutation starts from one scene that
  happens not to contain the phrase that the new rule wrongly refuses. One proposed rule
  that the battery had certified would have refused 12 of 16 real client briefs. A rule
  that no real brief reaches has been tested by nothing: it is reported as untested, not
  as passing.

### Two questions that ask for a list, not a judgement

A yes/no lets a reviewer stop at the first plausible reading. In rangsarn's anomaly-first test, fried rice with egg was
answered yes to "could it come from the dishes", and nobody counted the father's third spoon. So:

- **`q_<id>_contents`** asks identity, not possibility: "Is every food or other content in the plate one of these, as
  served from it: …? Name anything in it that is none of them, or that is cooked together rather than served beside."
- **`q_<id>_own_things`**, for a person with two or more things held or set at their place, asks the reviewer to list
  them, hands first, then the place in front of them, without saying how many. The expected list (their hands' held
  objects, objects held by them, objects positioned at their place) goes only to `measure`, and a comparison that finds
  fewer listed than expected scores it `incomplete`, not passed. Its yes/no asks whether each thing is in one place
  only, held or set down, never both.

## Learning from faults

A fixed question set finds only the failures someone already thought of. Two things keep
the set growing from what is actually found:

- **`q_anomalies` opens every review**, and the instructions say to answer it before
  reading the others: "Before reading any other question, look at the whole image and every
  crop: is it free of anything a careful viewer would find wrong or implausible?", with each
  thing and where it is listed in the evidence when the answer is no. The owner found clone
  faces in rangsarn's run 03 that no question asked about and every reader missed. Asked
  last, it answered no once in 28 reviewed pictures while seven known faults went unnamed,
  its evidence opening "apart from the issues identified above": a residual of the
  checklist, not a fresh look. It names what to look at by family (people, repeats, size
  and distance, support and physics, light, text, time and place) with each family's `look_for` phrases,
  and ends "and at anything else". It is told where and when the scene is (`location.locale`) and nothing else of
  the brief, so a garment from the wrong country can be seen without the checklist. Only classes a viewer can see without the brief carry
  `look_for`; a framing one step wide or a swapped hand needs the spec, and its own
  question asks it. A class added with a family and a `look_for` reaches the question
  without a code change.
- **`image-failure-classes.json` names every fault class** with its symptom, cause,
  prevention (a spec rule or prompt clause), detection (a question or rubric check) and
  regression (the contract-test section that keeps catching it). A class is closed only
  with all three and a prevention not measured to fail; C48 holds the file to that rule
  and checks every detection id against the compiler. Classes stay open while their
  prevention is measured not to work (pseudo-text, unwanted text, everything drawn sharp,
  scale drift, locale lost to the common prior, a dropped secondary action, framing one
  step wide) or while they have no prevention or regression yet (tiled stock, sitting
  cross-legged by default, gaze at the wrong target, and the meta class of uncovered
  faults); the file says which, class by class. A true answer to `q_anomalies` becomes a new class.
  `prevention_history` keeps every prevention tried for a case, newest last, as `state` (said in the
  prompt) or `restructure` (the scene changed so the generator's default produces the fact). A stated
  prevention measured to fail stays on record beside what followed it, and a class is closed only
  while the newest entry of every case is not a measured failure. The first entries, from rangsarn's
  runs 10 to 13, are five stated facts that lost twice: a bund's width to its noun, a backlight to
  lit faces, a soft cap to a chef's toque, bowls to an empty hob, and a leaf's shape to its name. rangsarn keeps its own copy of
  the file, in step, as it does of this module.

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
