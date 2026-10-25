# Changelog

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
