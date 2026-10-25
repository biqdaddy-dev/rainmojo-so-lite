# Changelog

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
