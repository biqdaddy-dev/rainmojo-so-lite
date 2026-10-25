# Changelog

## 2.7.0 (2026-10-26)

### สิ่งที่ผู้ใช้จะเห็น

- ทุกภาพถ่ายต้องระบุ "ตำหนิที่วางไว้" อย่างน้อยสองจุด เช่น รอยขูดที่ขอบเคาน์เตอร์ตรงใกล้แคชเชียร์
  หรือผมหลุดลงมาข้างขวา เพราะสิ่งนี้คือสิ่งที่ทำให้ภาพอ่านได้ว่าเป็นภาพถ่าย ไม่ใช่ภาพเรนเดอร์
- บรีฟห้ามใช้คำเปรียบเทียบอย่าง "มือเหมือนนักเปียโน" แล้ว เพราะโมเดลจะวาดสิ่งที่เอาไปเปรียบ
  เปียโนจะโผล่เข้ามาในภาพจริง ๆ
- เพิ่มตัวอย่างบรีฟสำหรับสถานที่จริงเต็มรูปแบบ (`image-spec.real-place.example.json`)
  และ `spec-template --reference` สร้างโครงบล็อกอ้างอิงสถานที่ให้ ซึ่งก่อนหน้านี้ไม่มีใครรู้ว่ามีอยู่
- รูปที่ใช้เป็นต้นแบบป้อนโมเดลต้องมีแถวสิทธิ์ของตัวเองทีละภาพ รวมถึงรูปใบหน้าคนที่ใช้อ้างอิง

### Under the hood

`image_spec.py`, `image_spec_contract_test.py`, `image-spec.example.json` and the new
`image-spec.real-place.example.json` are byte-identical to the full edition at `f632e00` on
`feat/dp-014-image-plausibility`; `image_production.py` takes that commit's
`spec-template --reference` flag. The contract test runs here unchanged at **169
assertions** and `regression.py` is 3/3.

`image-plausibility-review.example.json` is regenerated from this edition's own
`defaults.json` and `review_template` and comes out byte-identical to the full edition's,
which is the strongest parity statement available: the generator and the data agree in both
editions independently. The contract test now asserts that this file matches what the
compiler writes, so it cannot drift again.

Upstream carries the six findings this edition reported against `ad2e1ad`, three of which
were bugs that refused correct briefs:

- the scale anchor is resolved to the person it names, on word boundaries, declining to
  check when several people are in frame and none is named;
- the landmark check runs only for `stands_on` and `rests_on`, so a hanging or mounted
  object's own length is no longer compared with a height above the floor;
- an extent word before the landmark marks the anchor as a claim about width or length and
  the height check stands down;
- `conditioning_images` are matched to a source one by one, and an image matching no source
  is refused, so one client-owned photo no longer authorises feeding anything to a model;
- `spec-template --reference` scaffolds the reference block;
- and the shipped review example is asserted against the compiler.

Also from upstream in this port: `spec.realism.imperfections`, required with at least two
placed entries for a photographic medium, and four lint rules including a refusal of simile
in any spec field.

Then `041193e`, which closes the last two items this edition raised. `state` is required on
every object, so a thing with moving parts can no longer reach a generator with its
configuration unstated; the vocabulary is left to the reviewer, because a word list would
reward "open" and refuse "the leaf swung back against its stop", which inverts the rule
that prose beats tokens, and it could not be validated against any corpus since not one
object in any fixture is a mechanism. And `support.by` is scanned for supports that hold
nothing, for bearing kinds only, so a boat may still float in water. Contract test **175
assertions**, passing here unchanged.

Then `f808a4b`. Nine defects from a client sweep, every one a rule that refused a correct
brief; among them `extends_beyond_frame`, because the width check was making authors write
the visible run of an object instead of its real size, 18 m for a 120 m raft, and every
apparent-size ratio is computed from that number. The compound hands question is replaced by
five atomic ones. The crash class is closed structurally: the names every section of
`validate_spec` reads are bound once at the top, and the contract test asserts the function
returns rather than raises on twelve shapes of malformed input. And the shipped real-place
example no longer asks for a view its own numbers forbid, which exposed a compiler bug where
a horizon value meaning "outside the frame" was treated as a position in it. Contract test
**204 assertions**, passing here unchanged.

Then `7d4748a`, which fixes a rule that was wrong in principle. The rule refusing a brief
that forbids what it also puts in the picture fired on any shared word, so "readable words
on the printed sheet or the laptop" was read as forbidding the laptop, and "a tidy desk
with nothing on it" as forbidding the desk. It now fires only when an avoid entry reduces to
the declared name and nothing else. "What X is really like" is accepted as an idiom rather
than refused as a simile. Contract test **213 assertions**, passing here unchanged. Against
the sixteen real client briefs the sweep wrote, this edition's validator refused seven
before the fix and three after, and the three that remain are true positives: two
photographs without placed imperfections, and one real place shot from inside with no
source that shows the inside.

Then `c2761f5` and `cfbdba3`, from the sweep's review misses. Framing follows `focus_on`, the
soft-focus question asks how blurred, apparent-size ratios above 8 to 1 are no longer asked
because they cannot be measured on the image, the lighting question names the declared fill,
and two new questions ask about anything in the frame the brief did not declare and about
malformed lettering. The eye-line question is now asked only when the horizon is in frame
and someone in the picture is standing. A new warning flags a purpose that describes people
when the brief declares none, because the purpose opens the prompt and people tend to
appear. Contract test 213 assertions, passing here unchanged; the shipped review example
grows from 80 to 82 questions.

Then `6be1a7f`. Words like perfect, epic, 4k, award-winning, best quality and sharp focus
are refused only as a bare list item, since in a sentence they can be facts. Negation skips
quoted lettering, all-caps signage, "No. 9", hyphenated compounds and "not only". The inline
Constraints block no longer writes "no a ...". Contract test **234 assertions**, passing here
unchanged, and `image-spec.contract.md` taken from the full edition with its new section on
measuring the review.

This edition's own instructions for the image spec are corrected in the same commit. From
2.6.0 on, `content-production-lite`'s `SKILL.md` and `agent.json` described a design this
edition had replaced: anchors read by intersecting two landmark bands, a seated eye-level
band of one head height, a held object measured against its holder, and a face distance set
by the distance alone. The code checks only the first landmark an anchor names, within 12 cm
either way; uses 0.15 m for a seated eye line; measures a held object against the tallest
person in the frame; and refuses a face closer than a per-lens floor. The instructions now
say so, and a new test checks every number they quote against the code, so they cannot drift
silently again. Regression is 4 of 4.

Then `0eb7919`. The warning about a purpose that describes people now takes verbs only for
explain, consult and welcome, so "a technical explainer", "the consultation room" and "a
welcoming lobby" no longer trigger it, and the six template behaviours from the sweep plus
the eye-line gate are pinned by assertions for the first time. Contract test **258
assertions**, passing here unchanged. On the real briefs the warning now fires on the two
that would paint people the brief does not want, and no longer on the writing desk.

Then `569a7ae` and `050ea4e`. An object said to be held in a hand is now measured against
the person holding it, the one `support.by` names, rather than against the tallest person in
the frame, so an object half a child's height in her palm is refused even when an adult
stands beside her. The face-distance floor follows the physics: perspective is set by
distance alone, so a face closer than 0.9 m is refused on any lens, with more room on the
two widest, 1.2 m up to 20 mm and 1.0 m up to 28 mm; lenses above 85 mm had no floor before.
The error now states the distortion, for example the nose at 1.18 times the scale of the
ears. `interacts_with` leaves the blank template, since nothing reads it and `support.by`
already carries contact; it is still accepted. The contract doc gains a table of every rule
`validate_spec` refuses, its trigger and its reason. Every question a tool can measure now
carries a structured `measure`. Contract test **277 assertions**, passing here unchanged.

The version is frozen at 2.7.0 for the rest of this branch: the release is one release, not
one per commit, and two editions assigning versions from snapshots of a moving branch
collided twice.

## 2.6.0 (2026-10-26)

### สิ่งที่ผู้ใช้จะเห็น

- ฉากที่อ้างอิงสถานที่จริงทำได้แล้ว: ระบุชื่อและที่อยู่ พร้อมแหล่งอ้างอิงอย่างน้อยสองแหล่ง
  ที่บอกว่าเห็นอะไรจากมุมไหน ข้อเท็จจริงที่ยืนยันแล้วจะเข้าไปใน prompt และกลายเป็นคำถามตรวจของตัวเอง
  ภาพที่ใช้ป้อนโมเดลต้องมีสิทธิ์รองรับ ไม่ใช่รูปที่หาเจอบนเว็บ
- คนที่ยืนบนเวที บนแท่น หรือบนพื้นต่างระดับ คิดเส้นสายตาจากระดับพื้นที่เขายืนจริง
  ไม่เหมาะเอาระดับพื้นห้องมาใช้แล้ว
- คำถามตรวจรูปแยกเรื่องการจัดเฟรมออกจากมุมกล้อง และไม่ถามเรื่องเส้นขอบฟ้าเมื่อบรีฟบอกว่าไม่เห็นขอบฟ้า
  ทำให้คำถามที่ตอบไม่ได้ลดลงจาก 54 เปอร์เซ็นต์เหลือ 26

### Under the hood

`image_spec.py` and `image_spec_contract_test.py` are taken verbatim from the full edition
at `ad2e1ad` on `feat/dp-014-image-plausibility`, which restores byte-parity: the full
edition is the source of truth, because the MCP and Pro editions are thin pointers served
from its bundle and inherit whatever is in it. The contract test runs here unchanged at 135
assertions, so parity is proven rather than assumed.

That file now carries both the realism fixes this edition prototyped in 2.5.0 and the
reference-block work the full edition did alongside them:

- `spec.location.reference`: `place_is_real`, place name and address, at least two sources
  each with publisher, access date, what it shows, a viewpoint from a fixed list and a
  rights value, plus `verified_facts`, `conflicting_claims` and `conditioning_images`
  gated on rights. Facts reach the prompt and become their own review questions.
- `ground_height_m` per subject, carried into eye height and the horizon crossing, so a
  figure on a stage or a platform no longer inherits a floor-standing eye line.
- `eye_line_people` covers everyone whose eye height is known, measuring the crossing
  against the height the pose gives rather than the stature, which is what finally gives
  seated and kneeling figures an eye line.
- `fits_in_frame` in the derivation, so an apparent-size ratio is only asked about where
  both entities are in the frame. On the worked example this drops seven unanswerable
  ratio questions.
- framing and camera angle are separate questions, horizon questions are suppressed when
  the spec puts the horizon out of shot, and a viewpoint clause opens the prompt.
- `thigh` and `mid-thigh` at 0.420 join the landmark table, the midpoint of knee and hip,
  because that is the height a desk or a counter actually meets.

The 2.5.0 implementation of the realism checks was this edition's own and is superseded by
the upstream file; nothing it caught has been lost, and `regression.py` stays 3/3. The
regenerated `image-plausibility-review.example.json` drops from 73 spec questions to 68.

## 2.5.0 (2026-10-25)

### สิ่งที่ผู้ใช้จะเห็น

- ระบบตรวจสัดส่วนของวัตถุกับร่างกายคนในฉากได้แล้ว ถ้าบอกว่า "ขอบบนอยู่เหนือสะโพก"
  ระบบจะคำนวณความสูงสะโพกจากส่วนสูงของคนคนนั้นแล้วเทียบให้จริง เคาน์เตอร์ 0.42 ม.
  ที่อ้างว่าอยู่เหนือสะโพกคนสูง 1.62 ม. จะถูกปฏิเสธ รวมถึงของชิ้นใหญ่เกินกว่าจะถือด้วยมือเดียว
- ฉากที่คนนั่งหรือคุกเข่าได้รับการตรวจเส้นสายตาเหมือนคนยืนแล้ว ซึ่งครอบคลุมฉากสัมภาษณ์
  ฉากโต๊ะทำงาน และฉากร้านอาหารเกือบทั้งหมด พร้อมบอกเป็นหน่วย "ความสูงหัว" ที่นับบนรูปได้เลย
- ตรวจแสงเพิ่ม: ท้องฟ้าที่มีเมฆปิดจะบังดวงอาทิตย์ จึงทอดเงาคมไม่ได้ และไฟเสริมที่แรงและแข็ง
  เท่าไฟหลักถือเป็นดวงอาทิตย์ดวงที่สอง ทั้งสองกรณีถูกปฏิเสธก่อนสั่งสร้างรูป

### Under the hood

Driven by a 25-case realism battery against a scene that validated with 0 errors: it
started at 12 caught, 1 warned, 12 missed and now stands at 20 caught, 3 warned, 3 missed,
where the 3 remaining misses are a guard case that must stay legal, a valid scene, and the
one text contradiction left to the review rubric on purpose.

- Fixed: `support.by` for `held_by` and `worn_by` accepted an object id, although the error
  message said it had to be a subject, so a carton held by a counter compiled.
- New `BODY_LANDMARK_FRACTION`, the standard stature fractions of Drillis and Contini (1966)
  as tabulated in Winter figure 4.1, the same measured family `EYE_FRACTION` comes from.
  A `scale_anchor` naming a body landmark is now checked against the person's `height_m`,
  reading each landmark with the hedge before it so an anchor that brackets between two of
  them intersects both bands. With several people and no name in the anchor, no check runs.
- The same table bounds a held object against its holder: above 0.30 of stature it cannot
  fill a hand (refused when the brief says it does), above 0.60 it is a two-handed load
  (a warning, because a person really can carry a ladder).
- Seated and kneeling figures now derive `eye_line_offsets`, stated in head heights on the
  7.5-head canon so a reviewer can count them on the image, with a prompt clause and a
  `verify_with: geometry` question each. The `eye_level` band tightens from 0.35 m to one
  head height where nobody is standing, since 0.35 m is the standing-population spread.
- The `focus_on` entity of a `full`, `wide` or `extreme_wide` shot must fit the frame in
  both width and height, not only standing people in height. An object that merely runs out
  of frame is still legal.
- A face closer than 1 m is reported whatever the focal length, since perspective
  distortion follows the distance alone, and a tight shot inside 1.5 m is reported too.
- `location.weather` against the key's quality: a clouded sky cannot cast a crisp shadow.
  A `fill` claiming the key's power and hardness is refused as a second key.
- The object load limit counts declared items, not entries, so one entry of forty cartons
  no longer passes a limit of eight; `support.by` is scanned for supports that hold nothing.
- `image_spec_contract_test.py` grows from 118 to 146 assertions, with a case per fix and a
  guard per fix against the false positive it could cause.

## 2.4.0 (2026-10-25)

### สิ่งที่ผู้ใช้จะเห็น

- รูปปกและรูปประกอบในบทความถูกออกแบบจาก "ใบสั่งถ่ายภาพ" ที่มีระยะ ขนาด มุมกล้อง และทิศแสงเป็นตัวเลขจริง
  ระบบตรวจความขัดแย้งทางฟิสิกส์ให้ก่อนสั่งสร้างรูป เช่น เส้นขอบฟ้าไม่เข้ากับการก้มกล้อง เงาทอดผิดทางจากไฟดวงหลัก
  ของลอยไม่มีอะไรรองรับ หรือเคาน์เตอร์สูงผิดจากมาตรฐานอาคาร
- ทุกรูปต้องผ่านการตรวจทีละข้อก่อนใช้งาน ครอบคลุมจำนวนนิ้วมือ สัดส่วนร่างกาย ใบหน้าและดวงตา ของที่ใช้งานได้จริง
  ผิวที่ไม่เป็นพลาสติก ขนาดตามระยะใกล้ไกล เงา และเส้นขอบฟ้า โดยต้องดูรูปเต็มและทุกชิ้นส่วนที่ซูมแล้ว
  พร้อมบันทึกหลักฐานว่าเห็นอะไรตรงไหน
- prompt ไม่ถูกพิมพ์ด้วยมืออีกต่อไป แต่คอมไพล์จากใบสั่งถ่ายภาพ แก้ prompt เองแล้วระบบจะปฏิเสธและให้กลับไปแก้ใบสั่ง
  ทำให้รูปที่ได้ตรงกับสิ่งที่ตรวจเสมอ

### Under the hood

- New `image_spec.py`, ported from the full edition at parity: validates a per-image shot
  spec (camera, lens, distances, lights, every person and object with size, position and
  support), derives the geometry it implies, compiles it into the prompt and avoid list, and
  builds the reviewer's questions. Pure standard library.
- Validator catches cross-entity contradictions before generation: horizon against tilt,
  shot type against lens and distance, shadow direction against the key light, plane
  ordering against distance, a standing person against frame height, `background_focus:
  sharp` against the computed depth of field, posture-aware eye height against an
  `eye_level` camera, and object heights against ADA/IRC/IBC bands and settled conventions.
- Prompt compiler: priority-tiered clauses with a word budget that never cuts the picture
  and says when it cannot be met; every camera number emitted next to the words for its
  effect (Kelvin, f-number, focal length, shot size); and a hard ban on negation in the
  positive prompt, enforced at both spec validation and compile time.
- `image-model-registry.json` carries per-generator capability data (8 generators), so the
  compiler knows which models have a negative-prompt field at all. An unregistered
  `images.spec.target_model` is refused.
- `images.plausibility.checks` is a 30-item rubric ordered on measured failure prevalence,
  leading with functional, anatomical and stylistic checks and asking the physics ones
  across pairs of entities. `verify_with` routes counting to a counter, text to OCR, and
  camera, horizon and scale to measurement.
- New `image_production.py` subcommands: `spec-template`, `compile-spec`, `review-crops`,
  `review-template`. `image_specs_ready`, `process` and `mark-reviewed` are all gated on a
  fresh compiled spec and a complete, evidence-backed plausibility review tied to the exact
  image file.
- New `image_spec_contract_test.py` (118 assertions), new `content_pipeline_selftest.py`
  (end to end from a filled spec to `publish_ready`, with the three refusals), and a new
  `regression.py` entry point that runs all three packaged tests.
- Reference: `image-spec.contract.md`, `image-spec.example.json`,
  `image-plausibility-review.example.json`, `image-model-registry.json`. The two example
  JSON files are generated from lite's own `defaults.json` and compiler.
- The image instructions live in `content-production-lite`, since the lite edition has no
  separate `seo-image-production` skill.

## 2.3.1 (2026-10-13)

- Repository moved to biqdaddy-dev: the manifests, the marketplace entry and the README
  install commands use https://github.com/biqdaddy-dev/rainmojo-so-lite (was biqdaddy/rainmojo-so-lite).
