#!/usr/bin/env python3
"""Contract test for the image spec: the contradictions it must refuse.

Every case here is a brief a reader would see as wrong in the finished picture.
The spec catches it before an image is generated, so the failure costs a message
rather than a generation, a review and a reprint.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import image_spec

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = json.loads(
    (ROOT / "reference" / "content-production" / "defaults.json").read_text(
        encoding="utf-8"
    )
)
EXAMPLE = json.loads(
    (ROOT / "reference" / "content-production" / "image-spec.example.json").read_text(
        encoding="utf-8"
    )
)
WIDTH, HEIGHT = 1200, 630

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print("  PASS " + name)
    else:
        print("  FAIL " + name + (" :: " + detail if detail else ""))
        failures.append(name)


def errors_for(mutate) -> list[str]:
    spec = copy.deepcopy(EXAMPLE)
    mutate(spec)
    errors, _ = image_spec.validate_spec(spec, WIDTH, HEIGHT, DEFAULTS)
    return errors


def refuses(name: str, needle: str, mutate) -> None:
    errors = errors_for(mutate)
    check(
        name,
        any(needle in error for error in errors),
        f"expected an error containing {needle!r}, got {errors}",
    )


print("C1 the shipped example is a valid spec")
errors, warnings = image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)
check("example validates", not errors, "; ".join(errors))
check("example is warning-free", not warnings, "; ".join(warnings))

print("C2 the blank template is not a filled spec")
blank_errors, _ = image_spec.validate_spec(
    image_spec.blank_spec("photograph", 1), WIDTH, HEIGHT, DEFAULTS
)
check(
    "unanswered template questions are refused",
    any("template question" in error for error in blank_errors),
    "; ".join(blank_errors[:3]),
)

print("C3 camera geometry contradictions")
refuses(
    "horizon against a level camera",
    "contradicts tilt",
    lambda spec: spec["camera"].update({"horizon": "lower_third"}),
)
refuses(
    "a high angle cannot tilt up",
    "angle high with tilt up",
    lambda spec: spec["camera"].update(
        {"angle": "high", "tilt": "up", "horizon": "lower_third", "height_m": 2.4}
    ),
)
refuses(
    "eye level needs the lens near eye height",
    "near the eye height of the people",
    lambda spec: spec["camera"].update({"height_m": 0.6}),
)
refuses(
    "shot type against lens and distance",
    "contradicts the lens and distance",
    lambda spec: spec["camera"].update({"shot_type": "extreme_wide"}),
)
refuses(
    "the focus distance must match the focus subject",
    "disagrees with",
    lambda spec: spec["camera"].update({"subject_distance_m": 8.0}),
)


def _standing_person_too_large(spec: dict) -> None:
    spec["camera"].update(
        {"shot_type": "full", "focal_length_mm": 85, "subject_distance_m": 2.2}
    )


refuses(
    "a full shot must fit the person in frame",
    "does not fit",
    _standing_person_too_large,
)

print("C4 depth and plane ordering")
refuses(
    "a foreground entity cannot sit behind a background one",
    "plane order contradiction",
    lambda spec: spec["subjects"][1].update({"distance_m": 9.0}),
)
refuses(
    "a sharp background is impossible at this aperture",
    "background_focus sharp is impossible",
    lambda spec: spec.update({"background_focus": "sharp"}),
)

print("C5 light contradictions")
refuses(
    "shadows cannot fall toward the key light",
    "contradicts a key light",
    lambda spec: spec["lighting"].update({"shadow_direction": "left"}),
)
refuses(
    "the sun is not a night-time key light",
    "time_of_day is night",
    lambda spec: (
        spec["location"].update({"time_of_day": "night"}),
        spec["lighting"]["key"].update({"source": "direct sunlight"}),
    ),
)
refuses(
    "there is exactly one key light",
    "must be one light",
    lambda spec: spec["lighting"].update(
        {"key": [spec["lighting"]["key"], spec["lighting"]["key"]]}
    ),
)

print("C6 objects must be supported, sized and anchored")
refuses(
    "nothing floats",
    "support {kind, by} is required",
    lambda spec: spec["objects"][1].pop("support"),
)
refuses(
    "a held object is held by a person",
    "must be a subject id",
    lambda spec: spec["objects"][1]["support"].update({"by": "the air"}),
)
refuses(
    "every object carries a scale anchor",
    "scale_anchor is required",
    lambda spec: spec["objects"][0].pop("scale_anchor"),
)
refuses(
    "every object carries a real size",
    "give a real size",
    lambda spec: [
        spec["objects"][0].pop(key)
        for key in ("size", "height_m", "width_m")
        if key in spec["objects"][0]
    ],
)
refuses(
    "a relation names a real entity",
    "is not a known id",
    lambda spec: spec["objects"][0].update({"interacts_with": ["nobody"]}),
)

print("C7 people must be described well enough to draw")
refuses(
    "a person needs hands",
    "hands is required",
    lambda spec: spec["subjects"][0].pop("hands"),
)
refuses(
    "a person needs a height to anchor scale",
    "height_m (0.4-2.3) is required",
    lambda spec: spec["subjects"][0].pop("height_m"),
)
refuses(
    "a crowd is refused before anatomy fails",
    "the client limit is",
    lambda spec: spec["subjects"][0].update({"count": 9}),
)

print("C8 the quiet area and the text policy")
refuses(
    "the headline needs somewhere quiet",
    "negative_space is required",
    lambda spec: spec["composition"].pop("negative_space"),
)
refuses(
    "text in the image needs the client to enable it",
    "text_in_image must be none",
    lambda spec: spec.update({"text_in_image": "the clinic name"}),
)

print("C9 the compiled prompt carries the facts a correct picture needs")
compiled = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)
prompt = compiled["prompt"]
for needle, label in (
    ("50 mm", "focal length"),
    ("f/2.8", "aperture"),
    ("1.55 m above the floor", "camera height"),
    ("eye-level line", "horizon line"),
    ("front left", "key light direction"),
    ("contact shadow", "contact shadows"),
    ("quiet", "the quiet area for the headline"),
    ("too indistinct to read as words", "the text policy"),
    ("five fingers", "hands"),
):
    check(f"prompt states the {label}", needle in prompt, prompt[:200])
check(
    "the avoid list is separate for a model that takes one",
    compiled["negative_prompt"] and "extra, missing or fused fingers" in compiled["negative_prompt"],
    compiled["negative_prompt"][:120],
)
inline = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS, "inline_constraints")
check(
    "a model whose vendor prescribes inline exclusions gets a Constraints block",
    not inline["negative_prompt"] and "Constraints: no " in inline["prompt"],
    inline["prompt"][-200:],
)
check(
    "positive_only still resolves, as the old name for that target",
    image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS, "positive_only")["target"]
    == "inline_constraints",
)
silent = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS, "none")
check(
    "a model with no negative channel gets no exclusions at all",
    not silent["negative_prompt"]
    and "Constraints" not in silent["prompt"]
    and silent["avoid"],
    silent["prompt"][-120:],
)

print("C9b the prompt never describes the picture by what it is not")
for target in sorted(image_spec.PROMPT_TARGETS):
    result = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS, target)
    scene = result["prompt"].split("Constraints:")[0]
    check(
        f"target {target} emits a negation-free scene",
        not image_spec.negations(scene),
        str(image_spec.negations(scene)),
    )
refuses(
    "a spec field that says what the picture is not is refused",
    "says what the picture is not",
    lambda spec: spec["style"].update({"look": "editorial, no plastic skin"}),
)
check(
    "exclusions still travel, through must_not_show",
    "pills loose on the counter" in compiled["negative_prompt"],
    compiled["negative_prompt"][:120],
)
check(
    "the negation detector reads the words that matter",
    image_spec.negations("a street without cars and not a soul, never empty of light")
    == ["empty of", "never", "not", "without"],
    str(image_spec.negations("a street without cars and not a soul, never empty of light")),
)

print("C9c every number is paired with the words for its effect")
for needle, label in (
    ("a normal view, close to what the eye sees", "the focal length"),
    ("a shallow depth of field", "the aperture"),
    ("neutral daylight at about 5200 K", "the colour temperature"),
    ("framed from the waist up", "the shot size"),
):
    check(f"{label} carries its plain-language effect", needle in prompt, prompt[:160])

print("C9d the generator is capability data, not a table in code")
registry = image_spec.model_registry()
check("the registry loads", len(registry) >= 6, str(sorted(registry)))
check(
    "every entry declares where exclusions may go",
    all(
        entry.get("prompt_target") in image_spec.PROMPT_TARGETS
        for entry in registry.values()
    ),
    str({k: v.get("prompt_target") for k, v in registry.items()}),
)
check(
    "most current generators have no negative channel at all",
    sum(1 for e in registry.values() if e["prompt_target"] == "none") > len(registry) / 2,
    str([k for k, v in registry.items() if v["prompt_target"] == "none"]),
)


def for_model(name):
    config = copy.deepcopy(DEFAULTS)
    config["images"]["spec"]["target_model"] = name
    config["images"]["spec"].pop("prompt_target", None)
    config["images"]["spec"]["max_prompt_words"] = None
    return image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, config)


check(
    "a model with no negative field gets none",
    not for_model("gemini-image")["negative_prompt"],
)
check(
    "a model whose vendor wants inline exclusions gets them",
    "Constraints: no " in for_model("openai-gpt-image")["prompt"],
)
check(
    "a model with a real negative channel gets the field",
    for_model("stable-diffusion-3-5")["negative_prompt"],
)
mj = for_model("midjourney")
check(
    "the one generator that penalises detail carries its own tight budget",
    mj["dropped_clauses"]
    and any("could not be met" in warning for warning in mj["warnings"]),
    str(mj["warnings"])[:200],
)
check(
    "a budget that cannot be met says so rather than claiming a trim",
    any("626 words" in warning or "words" in warning for warning in mj["warnings"]),
    str(mj["warnings"])[:160],
)
unknown = copy.deepcopy(DEFAULTS)
unknown["images"]["spec"]["target_model"] = "a-model-that-does-not-exist"
try:
    image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, unknown)
except ValueError as exc:
    check("an unregistered model is refused", "not in image-model-registry.json" in str(exc), str(exc)[:120])
else:
    check("an unregistered model is refused", False, "it compiled")

print("C10 derived geometry")
derived = compiled["derived"]
check(
    "frame width at the subject plane is derived",
    abs(derived["frame_at_subject_m"]["width"] - 1.58) < 0.05,
    str(derived.get("frame_at_subject_m")),
)
check(
    "the field of view is derived from the lens",
    abs(derived["horizontal_fov_deg"] - 39.6) < 0.5,
    str(derived.get("horizontal_fov_deg")),
)
check(
    "depth of field is derived from lens, aperture and distance",
    0.9 < derived["depth_of_field_m"]["near"] < 2.2
    and derived["depth_of_field_m"]["far"] != "infinity",
    str(derived.get("depth_of_field_m")),
)
check(
    "the camera is recognised as standing at eye height",
    derived["camera_at_eye_height"] is True,
    str(derived.get("camera_at_eye_height")),
)
check(
    "entities outside the focus range are named",
    "customer" in derived["outside_focus"],
    str(derived.get("outside_focus")),
)
check(
    "apparent size ratios follow 1/distance",
    any(
        pair["a"] == "pharmacist"
        and pair["b"] == "customer"
        and abs(pair["a_to_b_apparent_height"] - 0.66) < 0.03
        for pair in derived["apparent_ratios"]
    ),
    json.dumps(derived["apparent_ratios"][:2]),
)

print("C11 the word budget trims the least load-bearing sentences first")
budgeted_config = copy.deepcopy(DEFAULTS)
budgeted_config["images"]["spec"]["max_prompt_words"] = 260
tight = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, budgeted_config)
check(
    "a budget drops lower-priority clauses",
    tight["dropped_clauses"] and tight["prompt_words"] < compiled["prompt_words"],
    f"{tight['prompt_words']} vs {compiled['prompt_words']}",
)
check(
    "the budget never drops the subject, the camera or the physics line",
    "50 mm" in tight["prompt"]
    and "pharmacist" in tight["prompt"]
    and "five fingers" in tight["prompt"],
    tight["prompt"][:200],
)
check(
    "a trimmed prompt says so",
    any("trimmed" in warning for warning in tight["warnings"]),
    str(tight["warnings"]),
)

print("C12 review questions are atomic and cover every entity and relation")
questions = compiled["questions"]
ids = {question["id"] for question in questions}
for required in (
    "q_pharmacist",
    "q_pharmacist_hands",
    "q_pharmacist_gaze",
    "q_medicine_box_support",
    "q_medicine_box_scale",
    "q_horizon",
    "q_eye_line",
    "q_shadows",
    "q_light",
    "q_no_text",
):
    check(f"question {required} is asked", required in ids, str(sorted(ids))[:200])
check(
    "every question ends in a single question mark",
    all(question["question"].count("?") == 1 for question in questions),
    str([q["id"] for q in questions if q["question"].count("?") != 1]),
)
check(
    "child questions name their parent entity",
    all(
        question["parent"] in ids
        for question in questions
        if question["parent"]
    ),
    "unknown parents",
)

print("C13 the prompt cannot drift from the spec")
item = {
    "id": "featured",
    "provenance": {"source_type": "generated"},
    "spec": copy.deepcopy(EXAMPLE),
    "prompt": compiled["prompt"],
    "negative_prompt": compiled["negative_prompt"],
    "spec_compiled": image_spec.compile_record(EXAMPLE, compiled, "2026-10-25T00:00:00Z"),
}
check("a freshly compiled item is clean", not image_spec.freshness_errors(item))
edited = copy.deepcopy(item)
edited["prompt"] = edited["prompt"] + " Also a dog."
check(
    "a hand-edited prompt is caught",
    any("edited by hand" in error for error in image_spec.freshness_errors(edited)),
    str(image_spec.freshness_errors(edited)),
)
changed = copy.deepcopy(item)
changed["spec"]["location"]["time_of_day"] = "sunset"
check(
    "a spec changed after compilation is caught",
    any("changed after compilation" in error for error in image_spec.freshness_errors(changed)),
    str(image_spec.freshness_errors(changed)),
)

print("C14 a passed plausibility review needs an answer and evidence for everything")
template = image_spec.review_template(item, DEFAULTS)
check(
    "the template asks every rubric check and every spec question",
    len(template["plausibility"]) == len(image_spec.rubric(DEFAULTS))
    and len(template["spec_answers"]) == len(compiled["questions"]),
    f"{len(template['plausibility'])} checks, {len(template['spec_answers'])} questions",
)
check(
    "a blank review cannot pass",
    image_spec.review_errors(template, item, DEFAULTS),
    "blank review passed",
)


def filled_review() -> dict:
    review = image_spec.review_template(item, DEFAULTS)
    review["reviewer"] = "contract test"
    review["notes"] = "Reviewed the full frame and every crop."
    review["crops_reviewed"] = 9
    for entry in review["plausibility"].values():
        entry["status"] = "passed"
        entry["evidence"] = "looked at the centre crop and the two lower crops"
    for entry in review["spec_answers"].values():
        entry["answer"] = "yes"
        entry["evidence"] = "visible in the centre crop at full resolution"
    return review


check("a fully answered review passes", not image_spec.review_errors(filled_review(), item, DEFAULTS))

no_evidence = filled_review()
first = next(iter(no_evidence["plausibility"]))
no_evidence["plausibility"][first]["evidence"] = ""
check(
    "a check without evidence does not pass",
    any("needs evidence" in error for error in image_spec.review_errors(no_evidence, item, DEFAULTS)),
    str(image_spec.review_errors(no_evidence, item, DEFAULTS))[:200],
)

failed_check = filled_review()
failed_check["plausibility"]["contact_shadows"]["status"] = "failed"
errors = image_spec.review_errors(failed_check, item, DEFAULTS)
check(
    "a failed physics check blocks the pass",
    any("contact_shadows" in error for error in errors),
    str(errors)[:200],
)
check(
    "the failing items are listed for the repair loop",
    "contact_shadows" in image_spec.failed_items(failed_check),
    str(image_spec.failed_items(failed_check)),
)

answered_no = filled_review()
answered_no["spec_answers"]["q_medicine_box_support"]["answer"] = "no"
check(
    "an image that does not match its spec cannot pass",
    any("q_medicine_box_support" in error for error in image_spec.review_errors(answered_no, item, DEFAULTS)),
    "spec mismatch passed",
)

too_few_crops = filled_review()
too_few_crops["crops_reviewed"] = 2
check(
    "the reviewer has to look at every crop",
    any("crops_reviewed" in error for error in image_spec.review_errors(too_few_crops, item, DEFAULTS)),
    "partial crop review passed",
)

wrong_image = filled_review()
check(
    "the review has to be of the image that shipped",
    any(
        "image_sha256" in error
        for error in image_spec.review_errors(wrong_image, item, DEFAULTS, "deadbeef")
    ),
    "stale image review passed",
)

bad_na = filled_review()
bad_na["plausibility"]["count_integrity"]["status"] = "not_applicable"
check(
    "a check that always applies cannot be stood down",
    any(
        "cannot be not_applicable" in error
        for error in image_spec.review_errors(bad_na, item, DEFAULTS)
    ),
    str(image_spec.review_errors(bad_na, item, DEFAULTS))[:200],
)

print("C16 object heights against code and convention")
refuses(
    "a kitchen counter is not 1.4 m high",
    "outside the",
    lambda spec: (
        spec["objects"][0].update({"name": "kitchen counter", "height_m": 1.4}),
    ),
)
refuses(
    "a door is not 1.5 m high",
    "outside the",
    lambda spec: spec["objects"][0].update({"name": "door", "height_m": 1.5}),
)
check(
    "a height inside the band is accepted",
    not any(
        "outside the" in error
        for error in errors_for(
            lambda spec: spec["objects"][0].update(
                {"name": "kitchen counter", "height_m": 0.91}
            )
        )
    ),
)
check(
    "an unnamed object is not second-guessed",
    image_spec.reference_height("sage-green medicine shelving") is None,
    str(image_spec.reference_height("sage-green medicine shelving")),
)

print("C17 eye height follows posture, not stature alone")
standing = {"height_m": 1.70, "posture": "standing"}
seated = {"height_m": 1.70, "posture": "sitting"}
toddler = {"height_m": 0.95, "posture": "standing"}
check(
    "a standing adult's eyes are at 0.93 of stature",
    abs(image_spec.eye_height(standing) - 1.581) < 0.002,
    str(image_spec.eye_height(standing)),
)
check(
    "a seated adult's eyes are set by the seat, not the stature",
    image_spec.eye_height(seated) < 1.3,
    str(image_spec.eye_height(seated)),
)
check(
    "a small child's larger head lowers the ratio",
    abs(image_spec.eye_height(toddler) - 0.855) < 0.002,
    str(image_spec.eye_height(toddler)),
)
refuses(
    "an eye-level camera cannot be at a seated person's eye height and a standing one's",
    "near the eye height of the people",
    lambda spec: spec["camera"].update({"height_m": 1.15}),
)

print("C18 the horizon crossing is stated as a measurable fraction")
crossings = {c["id"]: c for c in derived["horizon_crossings"]}
check(
    "every standing person gets a crossing",
    set(crossings) == {"pharmacist", "customer"},
    str(sorted(crossings)),
)
check(
    "the crossing is camera height over stature",
    abs(crossings["pharmacist"]["fraction_of_height_from_feet"] - 1.55 / 1.62) < 0.002,
    str(crossings["pharmacist"]),
)
check(
    "a camera taller than the subject puts the horizon above the head",
    all(
        c["above_head"]
        for c in image_spec.derive(
            {
                **EXAMPLE,
                "camera": {**EXAMPLE["camera"], "height_m": 2.4, "angle": "high"},
            },
            WIDTH,
            HEIGHT,
        )["horizon_crossings"]
    ),
    "a 2.4 m camera did not clear the heads",
)

print("C19 cross-entity questions, because that is where generators fail")
ids = {question["id"] for question in compiled["questions"]}
check(
    "shadows are compared between entities, not judged one at a time",
    any(question.startswith("q_pair_shadow_") for question in ids),
    str(sorted(ids))[:200],
)
check(
    "the figures are asked to share one ground plane",
    "q_pair_ground_plane" in ids,
    str(sorted(ids))[:200],
)
check(
    "only things that meet a surface are paired for shadows",
    not any("medicine_box" in question for question in ids if question.startswith("q_pair_shadow_")),
    "a held object was paired for shadow direction",
)
check(
    "the horizon crossing is asked per standing person",
    {"q_horizon_cut_pharmacist", "q_horizon_cut_customer"} <= ids,
    str(sorted(ids))[:200],
)

print("C20 the questions a tool answers better than a judge are routed to it")
routes = {
    question["id"]: question.get("verify_with")
    for question in compiled["questions"]
    if question.get("verify_with")
}
check(
    "entity counts are routed to a counter",
    routes.get("q_pharmacist") == "count" and routes.get("q_medicine_box") == "count",
    str(routes),
)
check("finger counts are routed to a counter", routes.get("q_pharmacist_hands") == "count", str(routes))
check("the text ban is routed to OCR", routes.get("q_no_text") == "ocr", str(routes))
check(
    "framing, angle and the horizon are measured, not judged",
    routes.get("q_camera_framing") == "geometry"
    and routes.get("q_camera_angle") == "geometry"
    and routes.get("q_horizon") == "geometry"
    and routes.get("q_horizon_cut_pharmacist") == "geometry",
    str(routes),
)
check(
    "framing and angle are asked separately, one fact each",
    "q_camera_framing" in ids and "q_camera_angle" in ids and "q_camera_shot" not in ids,
    str(sorted(i for i in ids if i.startswith("q_camera"))),
)
check(
    "a ratio is asked only where both things fit the frame and can be measured",
    all(
        compiled["derived"]["fits_in_frame"].get(a, True)
        and compiled["derived"]["fits_in_frame"].get(b, True)
        for a, b in (
            question["id"][len("q_ratio_"):].split("_", 1)
            for question in compiled["questions"]
            if question["id"].startswith("q_ratio_")
        )
    ),
    str(compiled["derived"]["fits_in_frame"]),
)
check(
    "the rubric routes its text and count checks too",
    {
        c["id"]: c.get("verify_with")
        for c in image_spec.rubric(DEFAULTS)
        if c.get("verify_with")
    }
    == {"text_free": "ocr", "hand_and_finger_count": "count", "count_integrity": "count"},
    str({c["id"]: c.get("verify_with") for c in image_spec.rubric(DEFAULTS) if c.get("verify_with")}),
)

print("C21 the rubric is weighted on measured failure rates")
groups = [c.get("group") for c in image_spec.rubric(DEFAULTS)]
for group in ("functional", "anatomy", "stylistic", "physics", "geometry", "sociocultural"):
    check(f"the rubric covers {group}", group in groups, str(sorted(set(groups))))
check(
    "functional and anatomical checks come before the physics ones",
    groups.index("functional") < groups.index("physics")
    and groups.index("anatomy") < groups.index("physics"),
    str(groups),
)

print("C22 realism battery: briefs that are wrong in ways a reader would see")
# Twenty-five mutations of a valid brief, run against the ported module in the
# lite edition. Twelve compiled. These cases hold the fixes in place for both
# editions, which carry image_spec.py byte for byte.

refuses(
    "only a person holds or wears something",
    "must be a subject id",
    lambda spec: spec["objects"][1]["support"].update({"by": "counter"}),
)

print("  proportion against the body the anchor names")
refuses(
    "a counter cannot reach the hip at 0.42 m",
    "scale_anchor says it reaches the hip",
    lambda spec: spec["objects"][0].update({"height_m": 0.42, "size": "0.42 m high"}),
)
refuses(
    "nor can the same counter reach it with a 2.25 m person",
    "scale_anchor says it reaches the hip",
    lambda spec: (
        spec["subjects"][0].update({"height_m": 2.25}),
        spec["camera"].update({"angle": "high", "tilt": "down", "horizon": "upper_third", "height_m": 2.4}),
    ),
)
refuses(
    "a 1.4 m carton is not held in one hand",
    "two-handed load at best",
    lambda spec: spec["objects"][1].update({"height_m": 1.4, "size": "about 1.4 m tall"}),
)
check(
    "the anchor takes the landmark it leads with, not the one it mentions second",
    any(
        "reaches the hip" in error
        for error in errors_for(lambda spec: spec["objects"][0].update({"height_m": 0.42}))
    ),
    str(errors_for(lambda spec: spec["objects"][0].update({"height_m": 0.42}))[:1]),
)
check(
    "mid-thigh is a landmark too, because that is what a desk top meets",
    abs(image_spec.BODY_LANDMARK_FRACTION["thigh"] * 1.7 - 0.714) < 0.01,
    str(image_spec.BODY_LANDMARK_FRACTION["thigh"]),
)

print("  a seated figure has an eye line as well")


def seated(spec):
    for subject in spec["subjects"]:
        subject["posture"] = "sitting"


seated_spec = copy.deepcopy(EXAMPLE)
seated(seated_spec)
seated_derived = image_spec.derive(seated_spec, WIDTH, HEIGHT)
check(
    "a seated scene still derives a horizon crossing",
    len(seated_derived["horizon_crossings"]) == 2,
    str(seated_derived["horizon_crossings"]),
)
check(
    "everyone with a known eye height counts, standing or not",
    len(image_spec.eye_line_people(seated_spec)) == 2
    and len(image_spec.standing_people(seated_spec)) == 0,
    f"{len(image_spec.eye_line_people(seated_spec))} / {len(image_spec.standing_people(seated_spec))}",
)
refuses(
    "eye level over a seated subject is not a standing lens height",
    "near the eye height of the people",
    lambda spec: (seated(spec), spec["camera"].update({"height_m": 1.52})),
)

print("  the frame has a width, and a lens has a nearest face")
refuses(
    "a 6 m counter cannot sit 2.1 m from a 50 mm lens",
    "where the lens frames",
    lambda spec: spec["objects"][0].update({"width_m": 6.0, "distance_m": 2.1}),
)
refuses(
    "a face 0.55 m from a 20 mm lens is the wide-angle portrait",
    "renders the nose larger than the ears",
    lambda spec: (
        spec["camera"].update(
            {"focal_length_mm": 20, "subject_distance_m": 0.55, "shot_type": "close_up"}
        ),
        spec["subjects"][0].update({"distance_m": 0.55}),
        spec["subjects"][1].update({"distance_m": 0.6}),
        spec["objects"][0].update({"distance_m": 0.5}),
        spec["objects"][1].update({"distance_m": 0.55}),
        spec["objects"][2].update({"distance_m": 1.2}),
    ),
)

print("  one light, and a sky the size of the sky")
refuses(
    "an overcast sky does not cast a hard-edged shadow",
    "the size of the sky",
    lambda spec: (
        spec["location"].update({"weather": "heavy overcast, rain on the pavement"}),
        spec["lighting"]["key"].update(
            {"source": "direct sunlight", "quality": "hard, crisp edged shadows"}
        ),
    ),
)
refuses(
    "a hard fill is a second key under another name",
    "second key",
    lambda spec: spec["lighting"].update(
        {"fill": ["a second hard spotlight at the same power from the right"]}
    ),
)
check(
    "a soft fill is still a fill",
    not any(
        "second key" in error
        for error in errors_for(
            lambda spec: spec["lighting"].update({"fill": ["a soft bounce from a white card"]})
        )
    ),
)

print("  a count of many things is still many things to draw")
_, count_warnings = image_spec.validate_spec(
    {**copy.deepcopy(EXAMPLE), "objects": [
        {**copy.deepcopy(EXAMPLE["objects"][0]), "count": 40},
        *copy.deepcopy(EXAMPLE["objects"][1:]),
    ]},
    WIDTH,
    HEIGHT,
    DEFAULTS,
)
check(
    "one entry with a count of 40 reaches the load limit",
    any("42 objects across" in warning for warning in count_warnings),
    str(count_warnings),
)

print("C23 lint rules from the reference study")
# A generator takes every word literally. These four come from rangsarn's
# prompt_lint (P01, P02, P04, B01), reached independently by several of the
# reference prompt systems, and the booster ban from the de-slop discipline.

refuses(
    "a simile puts the thing compared into the frame",
    "compares with",
    lambda spec: spec["subjects"][0].update(
        {"pose": "shoulders squared like a soldier on parade"}
    ),
)
check(
    "a word about a material is not a comparison",
    not image_spec.similes("lifelike skin with true-to-life colour"),
    str(image_spec.similes("lifelike skin with true-to-life colour")),
)
refuses(
    "a pose named by its effect is not a pose",
    "names the impression a pose gives",
    lambda spec: spec["subjects"][0].update({"pose": "a confident pose behind the counter"}),
)
refuses(
    "camera words in a brief for a drawing produce a photograph",
    "uses camera words in a brief for",
    lambda spec: (
        spec.update({"medium": "illustration"}),
        spec["style"].update({"look": "flat editorial illustration, shot on a 50 mm lens"}),
        spec["camera"].pop("focal_length_mm", None),
        spec["camera"].pop("aperture_f", None),
        spec["camera"].pop("subject_distance_m", None),
        spec["camera"].pop("height_m", None),
    ),
)
refuses(
    "a booster word is not a fact",
    "booster word",
    lambda spec: spec["style"].update({"look": "ultra-detailed photorealistic masterpiece"}),
)

print("C24 a photograph carries located imperfection")
refuses(
    "a photograph with no imperfections is a render",
    "needs at least",
    lambda spec: spec["realism"].update({"imperfections": []}),
)
check(
    "the imperfections reach the prompt, because the model beautifies by default",
    "marks of use" in compiled["prompt"],
    compiled["prompt"][-400:],
)
check(
    "and each one is asked at review",
    any(q["id"].startswith("q_imperfection_") for q in compiled["questions"]),
    str([q["id"] for q in compiled["questions"] if "imperf" in q["id"]]),
)

print("C25 identity comes from the reference image, not the text")
with_ref = copy.deepcopy(EXAMPLE)
with_ref["location"]["reference"] = {
    "place_is_real": True,
    "place_name": "the client's own dispensary",
    "sources": [
        {
            "url": "https://example.com/about",
            "publisher": "the client",
            "shows": "the dispensing counter from the customer side",
            "viewpoint": "interior_wide",
            "accessed": "2026-10-26",
            "rights": "client_owned",
        },
        {
            "url": "uploads/brand-assets/pharmacist.jpg",
            "publisher": "the client",
            "shows": "the pharmacist at the counter, the likeness this image is built on",
            "viewpoint": "staff_or_uniform",
            "accessed": "2026-10-26",
            "rights": "client_owned",
        },
    ],
    "verified_facts": ["the dispensing counter runs the width of the shop"],
}
with_ref["subjects"][0]["reference_image"] = "uploads/brand-assets/pharmacist.jpg"
with_ref["subjects"][0]["appearance"] = ""
errors, _ = image_spec.validate_spec(with_ref, WIDTH, HEIGHT, DEFAULTS)
check("a person with a reference image needs no appearance", not errors, str(errors[:2]))
ref_compiled = image_spec.compile_spec(with_ref, WIDTH, HEIGHT, DEFAULTS)
check(
    "the prompt points at the reference instead of describing the face",
    "the person from the reference image" in ref_compiled["prompt"]
    and "mid-thirties, medium build" not in ref_compiled["prompt"],
    ref_compiled["prompt"][:300],
)
check(
    "and carries an identity lock",
    "bone structure" in ref_compiled["prompt"],
    ref_compiled["prompt"][:400],
)
check(
    "the review asks whether it is the same person",
    any(q["id"].endswith("_identity") for q in ref_compiled["questions"]),
    str([q["id"] for q in ref_compiled["questions"] if "identity" in q["id"]]),
)
described = copy.deepcopy(with_ref)
described["subjects"][0]["appearance"] = "mid-thirties, medium build, black hair tied back"
check(
    "describing the face anyway is refused, not ignored",
    any(
        "appearance must be empty" in error
        for error in image_spec.validate_spec(described, WIDTH, HEIGHT, DEFAULTS)[0]
    ),
    str(image_spec.validate_spec(described, WIDTH, HEIGHT, DEFAULTS)[0][:1]),
)
no_provenance = copy.deepcopy(EXAMPLE)
no_provenance["subjects"][0]["reference_image"] = "uploads/brand-assets/pharmacist.jpg"
no_provenance["subjects"][0]["appearance"] = ""
check(
    "a likeness needs a recorded basis for using it",
    any(
        "not a free asset" in error
        for error in image_spec.validate_spec(no_provenance, WIDTH, HEIGHT, DEFAULTS)[0]
    ),
    str(image_spec.validate_spec(no_provenance, WIDTH, HEIGHT, DEFAULTS)[0][:1]),
)

print("C26 a real place is shipped as a worked example")
REAL_PLACE = json.loads(
    (ROOT / "reference" / "content-production" / "image-spec.real-place.example.json").read_text(
        encoding="utf-8"
    )
)
real_errors, real_warnings = image_spec.validate_spec(REAL_PLACE, WIDTH, HEIGHT, DEFAULTS)
check("the real-place example validates", not real_errors, "; ".join(real_errors[:2]))
check("and is warning-free", not real_warnings, "; ".join(real_warnings[:2]))
real_compiled = image_spec.compile_spec(REAL_PLACE, WIDTH, HEIGHT, DEFAULTS)
check(
    "its established facts reach the prompt",
    "a real place, and these things about it are established" in real_compiled["prompt"],
    real_compiled["prompt"][:200],
)
check(
    "and each one is asked at review",
    any(q["id"].startswith("q_reference_") for q in real_compiled["questions"]),
    str([q["id"] for q in real_compiled["questions"] if q["id"].startswith("q_reference")]),
)
hedged = copy.deepcopy(REAL_PLACE)
hedged["location"]["reference"]["verified_facts"].append("the ring is probably 6 metres across")
check(
    "a fact recorded with a hedge was never verified",
    any(
        "hedges with" in error
        for error in image_spec.validate_spec(hedged, WIDTH, HEIGHT, DEFAULTS)[0]
    ),
    str(image_spec.validate_spec(hedged, WIDTH, HEIGHT, DEFAULTS)[0][:1]),
)

print("C27 the scale anchor measures the right thing, against the right person")
# Three false positives the lite session's port review found in the anchor check.
# Each one refused a correct brief, which is worse than not checking at all,
# because the message named a person or a dimension the author never wrote.


def two_people(spec):
    """A child first in the list, the pharmacist renamed, the anchor naming her."""
    spec["subjects"][0].update(
        {"id": "child", "short_name": "child", "description": "child waiting with her father",
         "height_m": 1.02, "distance_m": 2.2}
    )
    spec["subjects"][1].update({"id": "pharmacist2", "short_name": "pharmacist2", "height_m": 1.68})
    spec["objects"][0]["scale_anchor"] = "its top meets the pharmacist2 just above the hip"
    spec["objects"][1]["support"]["by"] = "pharmacist2"
    spec["camera"]["focus_on"] = "pharmacist2"
    for group in ("subjects", "objects"):
        for item in spec[group]:
            item["interacts_with"] = [
                "pharmacist2" if ref == "pharmacist" else ref
                for ref in item.get("interacts_with", [])
            ]


def anchor_errors(mutate):
    return [e for e in errors_for(mutate) if "scale_anchor says it reaches" in e]


check(
    "the anchor is measured against the person it names, not the first in the list",
    not anchor_errors(two_people),
    str(anchor_errors(two_people)[:1]),
)
check(
    "and it still catches a real mismatch against that person",
    any(
        "pharmacist2" in error and "0.42" in error
        for error in anchor_errors(
            lambda spec: (two_people(spec), spec["objects"][0].update({"height_m": 0.42}))
        )
    ),
    str(anchor_errors(lambda spec: (two_people(spec), spec["objects"][0].update({"height_m": 0.42})))[:1]),
)
check(
    "an id that is a substring of a landmark does not count as naming someone",
    image_spec.anchor_person(
        "its top meets her just above the waist",
        [{"id": "a", "height_m": 1.6}, {"id": "b", "height_m": 1.7}],
    )
    is None,
)
check(
    "with one person in frame the anchor does not have to name them",
    image_spec.anchor_person("its top meets her at the hip", [{"id": "only", "height_m": 1.6}])
    is not None,
)
check(
    "a hanging object carries its own length, not a height above the floor",
    not anchor_errors(
        lambda spec: spec["objects"][0].update(
            {"support": {"kind": "hangs_from", "by": "the ceiling track"},
             "height_m": 1.2,
             "scale_anchor": "it hangs down to about the pharmacist's shoulder"}
        )
    ),
)
check(
    "a claim about width is not read as a claim about height",
    not anchor_errors(
        lambda spec: spec["objects"][0].update(
            {"height_m": 0.5, "scale_anchor": "it is about as wide as the pharmacist's shoulders"}
        )
    ),
)
check(
    "but a height claim on a floor-standing object is still checked",
    anchor_errors(lambda spec: spec["objects"][0].update({"height_m": 0.42})),
)

print("C28 every conditioning image carries its own rights")
REAL = json.loads(
    (ROOT / "reference" / "content-production" / "image-spec.real-place.example.json").read_text(
        encoding="utf-8"
    )
)


def real_errors(mutate):
    spec = copy.deepcopy(REAL)
    mutate(spec)
    return image_spec.validate_spec(spec, WIDTH, HEIGHT, DEFAULTS)[0]


def own_first(spec):
    spec["location"]["reference"]["sources"][0]["rights"] = "client_owned"


check(
    "an image with no source row at all is refused",
    any(
        "no source records where it came from" in error
        for error in real_errors(
            lambda spec: (
                own_first(spec),
                spec["location"]["reference"].update(
                    {"conditioning_images": ["https://elsewhere.example.com/x.jpg"]}
                ),
            )
        )
    ),
    "an unprovenanced image reached the generator",
)
check(
    "one owned source does not authorise a reference-only image",
    any(
        "may not be fed to the generator" in error
        for error in real_errors(
            lambda spec: (
                own_first(spec),
                spec["location"]["reference"].update(
                    {"conditioning_images": [spec["location"]["reference"]["sources"][1]["url"]]}
                ),
            )
        )
    ),
    "a reference-only image reached the generator",
)
check(
    "the owned image itself is still allowed",
    not [
        error
        for error in real_errors(
            lambda spec: (
                own_first(spec),
                spec["location"]["reference"].update(
                    {"conditioning_images": [spec["location"]["reference"]["sources"][0]["url"]]}
                ),
            )
        )
        if "conditioning" in error or "no source records" in error
    ],
)

print("C29 the template teaches the fields nobody guesses")
plain = image_spec.blank_spec("photograph", 1)
with_reference = image_spec.blank_spec("photograph", 1, reference=True)
check("the default template stays short", "reference" not in plain["location"])
check(
    "the reference scaffold is there on request",
    "reference" in with_reference["location"]
    and len(with_reference["location"]["reference"]["sources"]) == 2,
)
check(
    "and ground_height_m is scaffolded, since a subject may stand on something",
    "ground_height_m" in plain["subjects"][0],
)

print("C30 the shipped review example matches the generator that writes it")
REVIEW = json.loads(
    (ROOT / "reference" / "content-production" / "image-plausibility-review.example.json").read_text(
        encoding="utf-8"
    )
)
fresh_item = {
    "id": "featured",
    "provenance": {"source_type": "generated"},
    "spec": EXAMPLE,
    "prompt": compiled["prompt"],
    "negative_prompt": compiled["negative_prompt"],
    "spec_compiled": image_spec.compile_record(EXAMPLE, compiled, "2026-10-26T00:00:00Z"),
}
fresh = image_spec.review_template(fresh_item, DEFAULTS)
check(
    "the example asks exactly the questions the compiler now writes",
    set(REVIEW["spec_answers"]) == set(fresh["spec_answers"]),
    f"example {len(REVIEW['spec_answers'])} vs generated {len(fresh['spec_answers'])}; "
    f"only in example: {sorted(set(REVIEW['spec_answers']) - set(fresh['spec_answers']))[:4]}",
)
check(
    "and exactly the rubric checks the config now carries",
    set(REVIEW["plausibility"]) == set(fresh["plausibility"]),
    str(sorted(set(REVIEW["plausibility"]) ^ set(fresh["plausibility"]))[:4]),
)

print("C15 a thin client config still has a gate")
thin = {"images": {"plausibility": {"required": True, "checks": []}}}
check(
    "an empty checks list falls back to the shipped rubric",
    len(image_spec.rubric(thin)) == len(image_spec.rubric(DEFAULTS)),
    str(len(image_spec.rubric(thin))),
)

if failures:
    print(f"RESULT: {len(failures)} failures")
    raise SystemExit(1)
print("IMAGE_SPEC_CONTRACT_TEST_OK")
