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
    "q_pharmacist_hands_count",
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
check(
    "finger counts are routed to a counter",
    routes.get("q_pharmacist_hands_count") == "count",
    str(routes),
)
check(
    "the hands question is decomposed, not one question asking four things",
    {
        "q_pharmacist_hands_action",
        "q_pharmacist_hands_count",
        "q_pharmacist_hands_joints",
        "q_pharmacist_hands_thumb",
        "q_pharmacist_hands_proportion",
    }
    <= ids
    and "q_pharmacist_hands" not in ids,
    str(sorted(i for i in ids if "hands" in i)),
)
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
    "times the scale of the ears",
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

print("C31 state is required, and a support has to hold something up")
# Settled with the lite session after it tried a mechanism-word vocabulary and
# found it could not be validated against any corpus. A word list would reward
# "open" and refuse "the leaf swung back against its stop", which inverts this
# module's own rule that prose beats tokens. So: state is required of every
# object, and the judgement about whether the mechanism works stays with the
# reviewer, where the functional rubric check already asks it.

refuses(
    "every object says what state it is in",
    "state is required",
    lambda spec: spec["objects"][0].update({"state": ""}),
)
check(
    "any prose satisfies it, so it cannot fight a real brief",
    not [
        error
        for error in errors_for(
            lambda spec: spec["objects"][0].update(
                {"state": "the leaf swung back against its stop"}
            )
        )
        if "state is required" in error
    ],
)

refuses(
    "a shelf that hovers is the floating-object failure written into the brief",
    "does not hold anything up",
    lambda spec: spec["objects"][0]["support"].update({"by": "a hovering glass shelf"}),
)
refuses(
    "nor does thin air hold anything up",
    "does not hold anything up",
    lambda spec: spec["objects"][0]["support"].update({"by": "thin air"}),
)
check(
    "a named surface is left alone",
    not [
        error
        for error in errors_for(
            lambda spec: spec["objects"][0]["support"].update({"by": "the tiled floor"})
        )
        if "does not hold anything up" in error
    ],
)
check(
    "and something may still float in water",
    not [
        error
        for error in errors_for(
            lambda spec: spec["objects"][0].update(
                {"support": {"kind": "floats_in", "by": "the floating tank"}}
            )
        )
        if "does not hold anything up" in error
    ],
)

print("C32 a brief may not forbid outright what it also puts in the picture")
# Proposed by the rangsarn session as V-collision. The avoid list and the scene
# description go to different fields and nothing compared them.
#
# The first version of this section asserted that "a cluttered counter" and
# "the pharmacist looking away" were collisions. They are not: each constrains
# a declared thing rather than forbidding it, which is exactly what
# must_not_show is for. The tests were encoding the bug. Run against sixteen
# real client briefs, that version refused five correct entries across three
# specs; this one refuses none and still catches the real contradiction.

refuses(
    "forbidding a declared object outright",
    "which the spec also puts in the picture",
    lambda spec: spec["must_not_show"].append("a counter"),
)
refuses(
    "forbidding a declared subject outright",
    "which the spec also puts in the picture",
    lambda spec: spec["must_not_show"].append("the pharmacist"),
)
refuses(
    "the plural is still the thing itself",
    "which the spec also puts in the picture",
    lambda spec: spec["must_not_show"].append("counters"),
)

# Every one of these constrains a declared thing. Five of them were refused by
# the first version, on real client briefs.
LEGAL_CONSTRAINTS = (
    ("a cluttered counter", "a state of the thing"),
    ("the pharmacist looking away", "a state of the person"),
    ("pills loose on the counter", "the thing used as a place"),
    ("a queue in front of the counter", "the thing used as a place"),
    ("a second counter", "an extra instance"),
    ("two counters in the frame", "an extra instance"),
    ("readable words on the shelving or the counter", "coordinated objects of a preposition"),
    ("an open medicine box lid", "a configuration of the thing"),
    ("a counter with nothing on it", "a state of the thing"),
    ("a stethoscope round anyone's neck", "nothing declared at all"),
)
for phrase, why in LEGAL_CONSTRAINTS:
    check(
        f"{phrase!r} is legal: {why}",
        not [
            error
            for error in errors_for(lambda spec, p=phrase: spec["must_not_show"].append(p))
            if "also puts in the picture" in error
        ],
        phrase,
    )
check(
    "both shipped examples stay clean under the rule",
    not image_spec.collisions(EXAMPLE) and not image_spec.collisions(REAL_PLACE),
    str(image_spec.collisions(EXAMPLE) + image_spec.collisions(REAL_PLACE)),
)

print("C32b what X is really like is an idiom, not a simile")
for idiom in (
    "what the planning consultation is really like",
    "what a first clear-aligner appointment actually looks like",
    "what an evening at the night market is like",
):
    check(f"{idiom!r} is not refused as a simile", not image_spec.similes(idiom), idiom)
for simile in ("a smile is like sunshine", "hands like a pianist's", "a dog-like grin"):
    check(f"{simile!r} is still refused", bool(image_spec.similes(simile)), simile)

print("C33 validate_spec answers; it does not raise")
# Two UnboundLocalErrors in three days, both the same mistake: a check added to
# the reference block read a name bound ninety lines further down. A crash is
# the one failure an adversarial battery structurally cannot see, because a
# probe that raises is not a probe that fails, and an exception aborts the run
# so every probe behind it never runs and the sheet comes back clean.
#
# Two guards. The names every section reads are bound once at the top of
# validate_spec, and these cases assert the function RETURNS on malformed input
# of each shape rather than raising.

MALFORMED = {
    "an empty object": {},
    "a version and nothing else": {"version": 1},
    "a reference block with no subjects or objects": dict(
        copy.deepcopy(REAL_PLACE), subjects=[], objects=[]
    ),
    "a reference block and no camera": {
        k: v for k, v in copy.deepcopy(REAL_PLACE).items() if k != "camera"
    },
    "reference as a string": dict(
        copy.deepcopy(REAL_PLACE),
        location=dict(copy.deepcopy(REAL_PLACE)["location"], reference="yes"),
    ),
    "sources as a mapping": dict(
        copy.deepcopy(REAL_PLACE),
        location=dict(
            copy.deepcopy(REAL_PLACE)["location"],
            reference=dict(
                copy.deepcopy(REAL_PLACE)["location"]["reference"], sources={"a": 1}
            ),
        ),
    ),
    "subjects as a string": dict(copy.deepcopy(EXAMPLE), subjects="two people"),
    "objects as numbers": dict(copy.deepcopy(EXAMPLE), objects=[1, 2, 3]),
    "a likeness on a spec with no reference block": dict(
        copy.deepcopy(EXAMPLE),
        subjects=[dict(copy.deepcopy(EXAMPLE)["subjects"][0], reference_image="x.jpg")],
    ),
    "no lighting at all": {
        k: v for k, v in copy.deepcopy(EXAMPLE).items() if k != "lighting"
    },
    "every section a string": {
        "version": 1, "purpose": "x", "medium": "photograph", "location": "a",
        "camera": "b", "subjects": "c", "objects": "d", "lighting": "e",
        "composition": "f",
    },
}
for label, malformed in MALFORMED.items():
    try:
        returned_errors, _ = image_spec.validate_spec(malformed, WIDTH, HEIGHT, DEFAULTS)
        check(f"returns rather than raising: {label}", bool(returned_errors), "no errors either")
    except Exception as exc:  # noqa: BLE001 - the point of the test
        check(f"returns rather than raising: {label}", False, f"{type(exc).__name__}: {exc}")

check(
    "the shared reads are bound before any section runs",
    "Everything any section below may read, bound once, before any of them run"
    in (ROOT / "scripts" / "image_spec.py").read_text(encoding="utf-8"),
    "the hoist comment is gone; a later binding may have crept back in",
)

print("C34 a horizon outside the frame is not a position in it")
check(
    "only three of the six values put it in the picture",
    image_spec.HORIZON_IN_FRAME == {"upper_third", "middle", "lower_third"},
    str(sorted(image_spec.HORIZON_IN_FRAME)),
)
below = image_spec.compile_spec(REAL_PLACE, WIDTH, HEIGHT, DEFAULTS)
check(
    "below_frame reads as an edge, not as a band across the frame",
    "falls below the bottom edge" in below["prompt"]
    and "across the below frame" not in below["prompt"],
    [x for x in below["prompt"].split(". ") if "eye-level" in x][:1],
)
check(
    "and the reviewer is not asked to measure a line that is not there",
    not any(q["id"] == "q_horizon" for q in below["questions"])
    and any(q["id"].startswith("q_viewpoint_") for q in below["questions"]),
    str([q["id"] for q in below["questions"] if "horizon" in q["id"] or "viewpoint" in q["id"]]),
)
check(
    "a horizon that is in the frame still gets measured",
    any(q["id"] == "q_horizon" for q in compiled["questions"]),
)
check(
    "the real-place example's camera is below the canvas its invariant claims",
    all(c["below_feet"] for c in below["derived"]["horizon_crossings"]),
    str(below["derived"]["horizon_crossings"]),
)

print("C35 a booster or a negation word that is a fact is left alone")
# Raised by the rangsarn session from an independent review of its own lint.
# Each phrase is a correct brief that the first version of these rules refused.
for phrase in (
    "a perfect circle chalked on the board",
    "an award-winning chef at the pass",
    "a Sony 4K camcorder on a tripod",
    "best quality coffee beans in a jute sack",
    "the marquee of The Epic Theatre",
    "a highly detailed brass engraving on the lid",
    "the label in sharp focus",
):
    check(f"{phrase!r} is not a booster", not image_spec.boosters(phrase), str(image_spec.boosters(phrase)))
for phrase, expected in (
    ("photorealistic, 8k, best quality", ["8k", "best quality", "photorealistic"]),
    ("a quiet pharmacy counter, perfect, epic", ["epic", "perfect"]),
    ("shot in 4K; highly detailed", ["4k", "highly detailed"]),
):
    check(f"{phrase!r} is still refused", image_spec.boosters(phrase) == expected, str(image_spec.boosters(phrase)))
for phrase in (
    'a sign on the door reading "No Smoking"',
    "a sign on the door reading \u201cNo Entry\u201d",
    "the No. 9 bus at the stop",
    "a no-frills canteen with steel tables",
    "NO PARKING stencilled on the kerb",
    "not only a pharmacy but a small clinic",
):
    check(f"{phrase!r} is not a negation", not image_spec.negations(phrase), str(image_spec.negations(phrase)))
for phrase, expected in (
    ("a counter with no boxes on it", ["no"]),
    ("No people in the aisle", ["no"]),
    ("a lane not yet lit", ["not"]),
):
    check(f"{phrase!r} is still a negation", image_spec.negations(phrase) == expected, str(image_spec.negations(phrase)))
inline = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS, target="inline_constraints")["prompt"]
check(
    "the Constraints block reads as English",
    "Constraints: " in inline and "no a " not in inline and "no an " not in inline
    and "no the " not in inline and "no no " not in inline,
    inline[inline.find("Constraints"):][:160],
)
check(
    "and still names the exclusion",
    "no doctor's long white coat" in inline,
    inline[inline.find("Constraints"):][:160],
)

print("C36 the sweep's template fixes are pinned, not just counted")
# c2761f5 and cfbdba3 changed six behaviours and C30 only saw the question count
# move. Raised by the lite session after C32 had encoded a bug as correct: the
# inverse risk is a change nothing encodes at all.
import copy as _copy


def _questions(spec):
    return {q["id"]: q for q in image_spec.build_questions(spec, image_spec.derive(spec, WIDTH, HEIGHT))}


def _prompt_text(spec):
    derived = image_spec.derive(spec, WIDTH, HEIGHT)
    policy = image_spec.policy_from_config(DEFAULTS)
    return " ".join(c["text"] for c in image_spec.build_clauses(spec, derived, WIDTH, HEIGHT, policy))


base_q = _questions(EXAMPLE)
check(
    "framing names the person it frames, in body terms",
    "the pharmacist" in base_q["q_camera_framing"]["question"]
    and "waist" in base_q["q_camera_framing"]["question"],
    base_q["q_camera_framing"]["question"],
)
on_object = _copy.deepcopy(EXAMPLE)
on_object["camera"]["focus_on"] = "counter"
object_framing = _questions(on_object)["q_camera_framing"]["question"]
check(
    "framing an object asks about the shot, never a body fraction",
    "counter" in object_framing and "waist" not in object_framing and "figure" not in object_framing,
    object_framing,
)
soft = [q["question"] for qid, q in base_q.items() if qid.startswith("q_soft_")]
check(
    "depth of field asks how soft, not whether softer",
    soft and all("clearly out of focus" in q and "unreadable" in q and "softer than" not in q for q in soft),
    soft[:1],
)
derived = image_spec.derive(EXAMPLE, WIDTH, HEIGHT)
check(
    "every ratio asked is one a person can read off an image",
    all(
        1 / image_spec.MAX_MEASURABLE_RATIO <= r["a_to_b_apparent_height"] <= image_spec.MAX_MEASURABLE_RATIO
        for r in derived["apparent_ratios"]
        if f"q_ratio_{r['a']}_{r['b']}" in base_q
    ),
    str([qid for qid in base_q if qid.startswith("q_ratio_")]),
)
far = _copy.deepcopy(derived)
far["apparent_ratios"] = [{"a": "shelving", "b": "medicine_box", "a_to_b_apparent_height": 40.0}]
check(
    "a 40:1 ratio is not asked",
    not any(q["id"].startswith("q_ratio_") for q in image_spec.build_questions(EXAMPLE, far)),
)
check(
    "the light question names the declared fill, so it is not counted as a second key",
    "fill is declared" in base_q["q_light"]["question"]
    and EXAMPLE["lighting"]["fill"][0] in base_q["q_light"]["question"],
    base_q["q_light"]["question"][-200:],
)
no_fill = _copy.deepcopy(EXAMPLE)
no_fill["lighting"]["fill"] = []
check(
    "and says nothing of a fill when none is declared",
    "fill" not in _questions(no_fill)["q_light"]["question"],
)
check(
    "something undeclared in the frame is asked, and counted",
    base_q.get("q_undeclared", {}).get("verify_with") == "count",
)
check(
    "pseudo-lettering is asked, and read as text",
    base_q.get("q_malformed_glyphs", {}).get("verify_with") == "ocr",
)
for purpose, implied in (
    ("the moment a rental car is handed over", True),
    ("the truck as its customers meet it", True),
    ("a clinic where the doctor consults on a first visit", True),
    ("the desk a long technical explainer gets written at", False),
    ("the consultant's empty office before nine", False),
    ("the consultation room before the first appointment", False),
    ("a welcoming lobby with a stone floor", False),
    ("a self-service kiosk by the door", False),
):
    check(
        f"{purpose!r} {'implies' if implied else 'does not imply'} a person",
        bool(image_spec.PERSON_IMPLIED_RE.search(purpose)) == implied,
    )
empty = _copy.deepcopy(EXAMPLE)
empty["subjects"] = []
empty["purpose"] = "the moment a rental car is handed over"
_, empty_warnings = image_spec.validate_spec(empty, WIDTH, HEIGHT, DEFAULTS)
check(
    "a purpose that implies a person warns when nobody is declared",
    any("declares no people" in w for w in empty_warnings),
    str(empty_warnings)[:200],
)
check(
    "and quotes the word that fired, so a serving tray is dismissed at a glance",
    any('("handed")' in w for w in empty_warnings),
    str(empty_warnings)[:200],
)
_, base_warnings = image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)
check("and says nothing when people are declared", not any("declares no people" in w for w in base_warnings))
check(
    "a visible horizon and standing people: the eye line is asked and described",
    "q_eye_line" in base_q and "horizon line crosses their eyes" in _prompt_text(EXAMPLE),
)
seated = _copy.deepcopy(EXAMPLE)
for subject in seated["subjects"]:
    subject["posture"] = "seated"
check(
    "everyone seated: no question about the standing people",
    "q_eye_line" not in _questions(seated) and "the standing people" not in _prompt_text(seated),
)
for horizon in ("not_visible", "above_frame", "below_frame"):
    hidden = _copy.deepcopy(EXAMPLE)
    hidden["camera"]["horizon"] = horizon
    check(
        f"horizon {horizon}: no question about a line that is not in the picture",
        "q_eye_line" not in _questions(hidden) and "horizon line crosses their eyes" not in _prompt_text(hidden),
    )

print("C37 a hand is measured against its holder, a face against its distance")
# Both found by the lite session reading the code to write its docs.
refuses(
    "a child cannot hold in one hand what an adult could",
    "against the pharmacist, who is 1.02 m,",
    lambda spec: (
        spec["subjects"][0].update({"height_m": 1.02}),
        spec["objects"][1].update({"height_m": 0.65}),
    ),
)
check(
    "the shipped example names the holder, not the tallest person",
    not [e for e in errors_for(lambda spec: spec["objects"][1].update({"height_m": 1.10})) if "1.68 m" in e]
    and any(
        "the pharmacist, who is 1.62 m," in e
        for e in errors_for(lambda spec: spec["objects"][1].update({"height_m": 1.10}))
    ),
    str(errors_for(lambda spec: spec["objects"][1].update({"height_m": 1.10}))),
)
for focal, near, refused in (
    (85, 0.6, True),
    (135, 0.6, True),
    (50, 0.8, True),
    (20, 1.0, True),
    (50, 1.5, False),
    (85, 0.95, False),
    (20, 1.25, False),
):
    def set_lens(spec, focal=focal, near=near):
        spec["camera"]["focal_length_mm"] = focal
        spec["subjects"][1]["distance_m"] = near
    hit = any("times the scale of the ears" in e for e in errors_for(set_lens))
    check(
        f"a face {near} m from a {focal} mm lens is {'refused' if refused else 'allowed'}",
        hit == refused,
        str([e for e in errors_for(set_lens) if "ears" in e]),
    )
check(
    "the blank template no longer asks for interacts_with, which nothing reads",
    "interacts_with" not in json.dumps(image_spec.blank_spec("photograph", 1)),
)
check(
    "and a brief that still carries it is accepted",
    not errors_for(lambda spec: spec["objects"][1].update({"interacts_with": ["pharmacist"]})),
)

print("C38 every measurable question says what a tool should find")
# Asked for by the rangsarn session, so a measuring tool maps its reading onto a
# question without parsing the id.
MEASURE_KINDS = {
    "count", "finger_count", "framing", "camera_angle", "horizon_band", "eye_line",
    "height_ratio", "viewpoint", "horizon_fraction", "undeclared", "glyphs", "text",
    "position", "crop_safety", "leaves_frame",
}
for spec_name, spec in (("example", EXAMPLE), ("real place", REAL_PLACE)):
    questions = image_spec.build_questions(spec, image_spec.derive(spec, WIDTH, HEIGHT))
    routed = [q for q in questions if q.get("verify_with")]
    check(
        f"{spec_name}: every routed question carries a measure of a known kind",
        routed and all(q.get("measure", {}).get("kind") in MEASURE_KINDS for q in routed),
        str([q["id"] for q in routed if q.get("measure", {}).get("kind") not in MEASURE_KINDS]),
    )
    check(
        f"{spec_name}: and judgement questions carry none",
        not [q["id"] for q in questions if not q.get("verify_with") and "measure" in q],
    )
by_id = {q["id"]: q for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))}
check(
    "a count names the entity, its label and the number",
    by_id["q_pharmacist"]["measure"] == {
        "kind": "count", "entity": "pharmacist", "label": "pharmacist", "is_person": True,
        "detect_as": "person", "expected": 1,
    },
    str(by_id["q_pharmacist"].get("measure")),
)
check(
    "framing names the focus entity and the shot",
    by_id["q_camera_framing"]["measure"] == {
        "kind": "framing", "entity": "pharmacist", "is_person": True, "expected": "medium",
    },
    str(by_id["q_camera_framing"].get("measure")),
)
crossing = next(q for qid, q in by_id.items() if qid.startswith("q_horizon_cut_"))
check(
    "a horizon crossing carries the fraction the prompt states",
    crossing["measure"]["kind"] == "horizon_fraction"
    and 0 < crossing["measure"]["expected"] < 1.2
    and crossing["measure"]["relation"] in {"crosses", "above_head", "below_feet"},
    str(crossing.get("measure")),
)
check(
    "text expects what text_in_image says",
    by_id["q_no_text"]["measure"] == {"kind": "text", "expected": "none"},
)

print("C39 four correct briefs the rangsarn session wrote, no longer refused")
floor = copy.deepcopy(EXAMPLE)
floor["subjects"][1]["posture"] = "floor_seated"
check(
    "a person sitting on the floor has an eye line at about 0.78 m",
    abs(image_spec.eye_height(floor["subjects"][1]) - 0.78) < 1e-9,
    str(image_spec.eye_height(floor["subjects"][1])),
)
check(
    "and is not measured as if on a chair",
    image_spec.eye_height(floor["subjects"][1]) < image_spec.EYE_ABSOLUTE_M["seated"] - 0.4,
)
below = copy.deepcopy(EXAMPLE)
below["subjects"][1]["ground_height_m"] = -1.2
check(
    "a person below the camera's floor is allowed, and their eye line drops with it",
    not [e for e in errors_for(lambda spec: spec["subjects"][1].update({"ground_height_m": -1.2})) if "ground_height_m" in e]
    and abs(image_spec.eye_height(below["subjects"][1]) - (image_spec.eye_height(EXAMPLE["subjects"][1]) - 1.2)) < 1e-9,
)
_, odd = image_spec.validate_spec(
    {**copy.deepcopy(EXAMPLE), "subjects": [{**EXAMPLE["subjects"][0], "posture": "perched"}, EXAMPLE["subjects"][1]]},
    WIDTH, HEIGHT, DEFAULTS,
)
check("an unknown posture says its eye line is not checked", any("'perched' is not one the geometry knows" in w for w in odd))


def hard_sun(weather):
    def mutate(spec):
        spec["location"]["weather"] = weather
        spec["lighting"]["key"]["quality"] = "hard, crisp-edged shadows"
    return [e for e in errors_for(mutate) if "key.quality is hard" in e]


check("hard sun on a clear morning with haze in the distance", not hard_sun("a clear sunny morning, a light haze in the distant canopy"))
check("hard light under an overcast sky is still refused", bool(hard_sun("overcast")))
check("and in haze with no sun", bool(hard_sun("thick haze over the river")))
for anchor_text, held in (
    ("its top is a hand's width above the pharmacist's head", False),
    ("its top is a hand width below the shelf", False),
    ("a palm tree beside it is twice its height", False),
    ("it sits in the pharmacist's palm", True),
    ("held in one hand at her side", True),
    ("her fingers wrap round it", True),
):
    check(
        f"{anchor_text!r} is {'held' if held else 'not held'} in a hand",
        bool(image_spec.HAND_HELD_RE.search(anchor_text)) == held,
    )
for fact, hedged in (
    ("the landing is about as wide as two boats", False),
    ("the stalls stand around the square", False),
    ("the hall is roughly square in plan", False),
    ("the ring is probably 6 metres across", True),
    ("the roof is reportedly corrugated iron", True),
    ("a green-ish roof", True),
):
    check(f"{fact!r} {'hedges' if hedged else 'does not hedge'}", bool(image_spec.HEDGE_RE.search(fact)) == hedged)

print("C40 four questions rangsarn's run 01 answered no on correct pictures")
run01 = {q["id"]: q for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))}
hands = run01["q_pharmacist_hands_count"]["question"]
check(
    "fingers are counted where they can be, and a grip is not a fault",
    "hidden behind another" not in hands and "covered by what the hand holds are fine" in hands
    and "cannot_tell" in hands,
    hands,
)
check(
    "position asks where a person is placed, not whether they stand",
    "placed here in the frame" in run01["q_pharmacist_position"]["question"]
    and "stand here" not in run01["q_pharmacist_position"]["question"],
)
landing = copy.deepcopy(EXAMPLE)
landing["subjects"][0]["ground_height_m"] = 1.0
on_landing = {q["id"]: q for q in image_spec.build_questions(landing, image_spec.derive(landing, WIDTH, HEIGHT))}
check(
    "someone on a raised landing is not asked to share a floor with the rest",
    "the pharmacist" not in on_landing.get("q_pair_ground_plane", {}).get("question", "")
    and "the older customer" in on_landing.get("q_pair_ground_plane", {}).get("question", ""),
    str({k: v["question"] for k, v in on_landing.items() if k.startswith("q_pair_ground")}),
)
in_boat = copy.deepcopy(EXAMPLE)
in_boat["objects"][0]["support"] = {"kind": "rests_on", "by": "shelving"}
in_boat_q = {q["id"]: q for q in image_spec.build_questions(in_boat, image_spec.derive(in_boat, WIDTH, HEIGHT))}
check(
    "a thing resting on another declared thing is not on the floor",
    "the counter" not in in_boat_q.get("q_pair_ground_plane", {}).get("question", ""),
    in_boat_q.get("q_pair_ground_plane", {}).get("question", ""),
)
check(
    "everyone on the same floor is still asked about it",
    all(n in run01["q_pair_ground_plane"]["question"] for n in ("the pharmacist", "the older customer", "the counter")),
    run01["q_pair_ground_plane"]["question"],
)
blur = image_spec.derive(EXAMPLE, WIDTH, HEIGHT)["blur_circle_mm"]
check(
    "the blur circle is the thin-lens figure",
    abs(image_spec.blur_circle_mm(50, 2.8, 2.2, 1.5) - 2500 / (2.8 * 2150) * 700 / 1500) < 1e-9,
)
check(
    "a thing just past the depth-of-field limit is not asked to be clearly soft",
    blur["medicine_box"] < 3 * image_spec.CIRCLE_OF_CONFUSION_MM
    and "q_soft_medicine_box" not in run01 and "q_soft_counter" not in run01,
    str(blur),
)
check(
    "a thing well past it still is",
    blur["customer"] >= 3 * image_spec.CIRCLE_OF_CONFUSION_MM and "q_soft_customer" in run01,
    str(blur),
)
for entity, expected in (
    ({"name": "medicine box of paracetamol tablets"}, "box"),
    ({"name": "wooden longtail boat with an outboard"}, "boat"),
    ({"name": "woven baskets"}, "basket"),
    ({"name": "shared dishes"}, "dish"),
    ({"name": "berries"}, "berry"),
    ({"name": "shophouses"}, "shophouse"),
    ({"name": "vases"}, "vase"),
    ({"name": "glasses"}, "glass"),
    ({"name": "boxes"}, "box"),
    ({"name": "houses"}, "house"),
    ({"name": "vases"}, "vase"),
    ({"name": "cases"}, "case"),
    ({"name": "horses"}, "horse"),
    ({"name": "roses"}, "rose"),
    ({"name": "buses"}, "bus"),
    ({"name": "lenses"}, "lens"),
    ({"name": "gases"}, "gas"),
    ({"name": "canvases"}, "canvas"),
    ({"name": "cookies"}, "cookie"),
    ({"name": "movies"}, "movie"),
    ({"name": "shelves"}, "shelf"),
    ({"name": "knives"}, "knife"),
    ({"name": "leaves"}, "leaf"),
    ({"name": "tomatoes"}, "tomato"),
    ({"name": "shoes"}, "shoe"),
    ({"name": "cities"}, "city"),
    ({"name": "batteries"}, "battery"),
    ({"name": "dishes"}, "dish"),
    ({"name": "benches"}, "bench"),
    ({"name": "glasses"}, "glass"),
    ({"name": "chairs"}, "chair"),
    ({"name": "glass"}, "glass"),
    ({"name": "children"}, "child"),
    ({"name": "water buffaloes"}, "buffalo"),
    ({"name": "mosquitoes"}, "mosquito"),
    ({"name": "smoothies"}, "smoothie"),
    ({"name": "brownies"}, "brownie"),
    ({"name": "octopuses"}, "octopus"),
    ({"name": "olives"}, "olive"),
    ({"name": "sleeves"}, "sleeve"),
    ({"name": "gloves"}, "glove"),
    ({"name": "canoes"}, "canoe"),
    ({"name": "babies"}, "baby"),
    ({"name": "ring ropes", "detect_as": "Rope"}, "rope"),
    ({"short_name": "tent row", "name": "row of identical white peaked tents"}, "tent"),
    ({"short_name": "the array", "name": "row of framed photovoltaic panels tilted south"}, "panel"),
    ({"short_name": "scooters", "name": "row of parked scooters nose-in to the kerb"}, "scooter"),
    ({"short_name": "whiteboard", "name": "wall-mounted whiteboard wiped clean"}, "whiteboard"),
):
    check(f"{entity} is detected as {expected!r}", image_spec.detect_as(entity) == expected, image_spec.detect_as(entity))
check("a person is detected as a person, whatever their role", image_spec.detect_as({"short_name": "grandmother"}, person=True) == "person")

print("C41 run 02: questions a correct picture cannot answer, and misses on position")


def _q(spec):
    return {q["id"]: q for q in image_spec.build_questions(spec, image_spec.derive(spec, WIDTH, HEIGHT))}


base41 = _q(EXAMPLE)
check(
    "a stature is not asked of people the medium shot cuts at the waist",
    "q_pharmacist_height" not in base41 and "q_customer_height" not in base41,
)
full = copy.deepcopy(EXAMPLE)
full["camera"].update({"shot_type": "wide", "focal_length_mm": 24})
full_q = _q(full)
fits = image_spec.derive(full, WIDTH, HEIGHT)["fits_in_frame"]
check(
    "and is asked of a standing person whose whole height fits",
    fits.get("pharmacist") and "q_pharmacist_height" in full_q,
    str(fits),
)
seated_full = copy.deepcopy(full)
seated_full["subjects"][0]["posture"] = "seated"
check("but not of the same person seated", "q_pharmacist_height" not in _q(seated_full))
out = copy.deepcopy(EXAMPLE)
out["objects"][2]["support"] = {"kind": "fixed_in", "by": "the back wall, out of frame to the right"}
out_q = _q(out)["q_shelving_support"]
check(
    "a support outside the picture is asked as leaving the frame toward it",
    "run out of the frame toward its support" in out_q["question"]
    and out_q.get("verify_with") == "geometry" and "contact shadow" not in out_q["question"],
    out_q["question"],
)
check(
    "a support in the picture is still asked for contact",
    "contact shadow" in base41["q_shelving_support"]["question"],
)
for qid in ("q_pharmacist_position", "q_counter_position", "q_crop_safety"):
    check(
        f"{qid} is measured, in fractions of the frame",
        base41[qid].get("verify_with") == "geometry" and "measure" in base41[qid],
        str(base41[qid].get("verify_with")),
    )


def warns(mutate, needle):
    spec = copy.deepcopy(EXAMPLE)
    mutate(spec)
    return any(needle in w for w in image_spec.validate_spec(spec, WIDTH, HEIGHT, DEFAULTS)[1])


check(
    "an avoid entry naming an origin nobody can see is warned",
    warns(lambda s: s["must_not_show"].append("plants from outside Southeast Asia"), "no reviewer can see"),
)
check(
    "an avoid entry naming something visible is not",
    not warns(lambda s: s["must_not_show"].append("potted plants on the counter"), "no reviewer can see"),
)


def on_counter(spec):
    spec["subjects"][1]["position"] = "standing on the counter, right of centre"


check("a person placed on a raised declared thing at floor level is warned", warns(on_counter, "ground_height_m is 0"))
check(
    "and is not once their floor is given",
    not warns(lambda s: (on_counter(s), s["subjects"][1].update({"ground_height_m": 0.9})), "ground_height_m is 0"),
)
check(
    "nor when they only stand beside it",
    not warns(lambda s: s["subjects"][1].update({"position": "standing beside the counter"}), "ground_height_m is 0"),
)

print("C42 a likeness carries its own provenance, in a fictional place too")
# Asked for by the rangsarn session: a recurring character from an approved lock
# sheet, in a place that does not exist.
locked = copy.deepcopy(EXAMPLE)
locked["subjects"][0]["appearance"] = ""
locked["subjects"][0]["reference"] = {
    "path": "cast/pim/lock-v3.png", "rights": "client_owned", "origin": "lock sheet cast/pim v3",
}
check(
    "a client-owned lock sheet on the subject is accepted with no real place",
    not image_spec.validate_spec(locked, WIDTH, HEIGHT, DEFAULTS)[0],
    str(image_spec.validate_spec(locked, WIDTH, HEIGHT, DEFAULTS)[0][:2]),
)
locked_prompt = image_spec.compile_spec(locked, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check("and is prompted as a reference, with the identity lock", "the person from the reference image" in locked_prompt and "bone structure" in locked_prompt)
for field, value, needle in (
    ("rights", "reference_only", "may not be fed to the generator"),
    ("rights", "found_online", "reference.rights must be one of"),
    ("origin", "", "reference.origin is required"),
    ("path", "", "reference.path is required"),
):
    def mutate(spec, field=field, value=value):
        spec["subjects"][0]["appearance"] = ""
        spec["subjects"][0]["reference"] = {
            "path": "cast/pim/lock-v3.png", "rights": "client_owned", "origin": "lock sheet v3",
        }
        spec["subjects"][0]["reference"][field] = value
    refuses(f"a subject reference with {field} {value!r} is refused", needle, mutate)


def fictional_with_legacy(spec, rights=None):
    spec["subjects"][0]["appearance"] = ""
    spec["subjects"][0]["reference_image"] = "uploads/cast/pim.png"
    spec["location"]["reference"] = {
        "place_is_real": False,
        "sources": [] if rights is None else [{
            "url": "uploads/cast/pim.png", "publisher": "studio", "shows": "the character",
            "viewpoint": "staff_or_uniform", "accessed": "2026-10-26", "rights": rights,
        }],
    }


refuses(
    "a legacy likeness in a fictional place with no source row is refused, where it used to pass",
    "no source records where it came from",
    fictional_with_legacy,
)
refuses(
    "and one recorded as reference_only is refused",
    "may not be fed to the generator",
    lambda spec: fictional_with_legacy(spec, "reference_only"),
)
check(
    "and one recorded as client_owned is accepted",
    not [e for e in errors_for(lambda spec: fictional_with_legacy(spec, "client_owned")) if "subject" in e and "reference" in e],
    str(errors_for(lambda spec: fictional_with_legacy(spec, "client_owned"))[:2]),
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
