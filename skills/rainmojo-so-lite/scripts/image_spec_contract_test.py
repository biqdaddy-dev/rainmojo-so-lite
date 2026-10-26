#!/usr/bin/env python3
"""Contract test for the image spec: the contradictions it must refuse.

Every case here is a brief a reader would see as wrong in the finished picture.
The spec catches it before an image is generated, so the failure costs a message
rather than a generation, a review and a reprint.
"""

from __future__ import annotations

import copy
import json
import re
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
negative = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS, "negative_prompt")
check(
    "the avoid list is separate for a model that takes one",
    negative["negative_prompt"] and "extra, missing or fused fingers" in negative["negative_prompt"],
    negative["negative_prompt"][:120],
)
check("unset, the exclusions go inline (owner decision)", compiled["target"] == "inline_constraints" and "Constraints: no " in compiled["prompt"])
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
    "pills loose on the counter" in negative["negative_prompt"],
    negative["negative_prompt"][:120],
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
    "a reference-only image may condition now, but is never silent about it",
    not any(
        "reference_only" in error
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
    "in the same order, with the same words",
    [(k, v.get("_question")) for k, v in REVIEW["spec_answers"].items()]
    == [(k, v.get("_question")) for k, v in fresh["spec_answers"].items()]
    and REVIEW["_instructions"] == fresh["_instructions"],
    str([k for k, v in REVIEW["spec_answers"].items() if fresh["spec_answers"].get(k, {}).get("_question") != v.get("_question")][:3]),
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
    "position", "crop_safety", "leaves_frame", "heading",
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
    and crossing["measure"]["relation"] in {"crosses", "above_head", "below_feet", "at_landmark"},
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
    "a person sitting on the floor has an eye line at about 0.78 m, scaled by stature",
    abs(image_spec.eye_height(floor["subjects"][1]) - 0.78 * floor["subjects"][1]["height_m"] / 1.65) < 1e-9,
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
check(
    "and one recorded as reference_only is accepted, with a warning",
    not [e for e in errors_for(lambda spec: fictional_with_legacy(spec, "reference_only")) if "subject" in e and "reference" in e],
    str(errors_for(lambda spec: fictional_with_legacy(spec, "reference_only"))[:2]),
)
check(
    "and one recorded as client_owned is accepted",
    not [e for e in errors_for(lambda spec: fictional_with_legacy(spec, "client_owned")) if "subject" in e and "reference" in e],
    str(errors_for(lambda spec: fictional_with_legacy(spec, "client_owned"))[:2]),
)

print("C43 every recorded reference may condition, and says so when it is reference_only")
# Owner decision 2026-10-26, the same in rangsarn: every reference is attachable.
check("all three rights values may condition", image_spec.CONDITIONING_RIGHTS == image_spec.REFERENCE_RIGHTS)
ref_only = copy.deepcopy(EXAMPLE)
ref_only["subjects"][0]["appearance"] = ""
ref_only["subjects"][0]["reference"] = {
    "path": "refs/street-vendor.jpg", "rights": "reference_only", "origin": "photo from a market visit",
}
ref_errors, ref_warnings = image_spec.validate_spec(ref_only, WIDTH, HEIGHT, DEFAULTS)
check("a reference_only likeness is accepted", not ref_errors, str(ref_errors[:2]))
check(
    "and warns that the source never reaches the published page",
    any("never this source" in w for w in ref_warnings),
    str(ref_warnings)[:200],
)
owned_only = copy.deepcopy(ref_only)
owned_only["subjects"][0]["reference"]["rights"] = "client_owned"
check(
    "an owned one does not warn",
    not any("never this source" in w for w in image_spec.validate_spec(owned_only, WIDTH, HEIGHT, DEFAULTS)[1]),
)
refuses(
    "provenance is still required: a likeness with no origin",
    "reference.origin is required",
    lambda spec: (
        spec["subjects"][0].update({"appearance": "", "reference": {"path": "x.jpg", "rights": "reference_only"}}),
    ),
)
refuses(
    "and a rights value that is not one",
    "reference.rights must be one of",
    lambda spec: (
        spec["subjects"][0].update(
            {"appearance": "", "reference": {"path": "x.jpg", "rights": "found_online", "origin": "web"}}
        ),
    ),
)

print("C44 run 03: ratios of things whose height is what they measure, an eye line on one floor")


def _ids(spec):
    return {q["id"]: q for q in image_spec.build_questions(spec, image_spec.derive(spec, WIDTH, HEIGHT))}


base44 = _ids(EXAMPLE)
wide44 = copy.deepcopy(EXAMPLE)
wide44["camera"].update({"shot_type": "wide", "focal_length_mm": 24})
ratio_ids = [q for q in _ids(wide44) if q.startswith("q_ratio")]
check(
    "a standing person whose whole height fits is compared",
    any("pharmacist" in q for q in ratio_ids),
    str(ratio_ids),
)
seated44 = copy.deepcopy(wide44)
seated44["subjects"][0]["posture"] = "seated"
check(
    "the same person seated is not compared by stature",
    not any(q.startswith("q_ratio") and "pharmacist" in q for q in _ids(seated44)),
    str([q for q in _ids(seated44) if q.startswith("q_ratio")]),
)
check("a held object is not compared", not any(q.startswith("q_ratio") and "medicine_box" in q for q in base44))
check("an upright standing object is", image_spec.ratio_ready(EXAMPLE["objects"][0], False))
lying = dict(EXAMPLE["objects"][0], width_m=6.0, height_m=0.6)
check("but not one much wider than tall", not image_spec.ratio_ready(lying, False))
check("nor one running past the frame", not image_spec.ratio_ready(dict(EXAMPLE["objects"][0], extends_beyond_frame=True), False))
check("nor a set of several", not image_spec.ratio_ready(dict(EXAMPLE["objects"][0], count=3), False))
check("nor a boat on the water", not image_spec.ratio_ready(dict(EXAMPLE["objects"][0], support={"kind": "floats_in", "by": "the canal"}), False))
check("an animal subject is compared by its height", image_spec.ratio_ready({"kind": "animal", "height_m": 0.7}, True))
eye44 = base44.get("q_eye_line", {})
check(
    "the eye line names the people on the camera's floor",
    "the pharmacist" in eye44.get("question", "") and "the older customer" in eye44.get("question", ""),
    eye44.get("question", ""),
)
raised44 = copy.deepcopy(EXAMPLE)
raised44["subjects"][1]["ground_height_m"] = 0.8
raised_eye = _ids(raised44).get("q_eye_line", {})
check(
    "and leaves out someone standing higher, whose eyes are above the horizon",
    "the pharmacist" in raised_eye.get("question", "") and "the older customer" not in raised_eye.get("question", "")
    and raised_eye.get("measure", {}).get("entities") == ["pharmacist"],
    raised_eye.get("question", ""),
)

print("C45 people do not look alike, repeats are not copies, contents are asked one by one")
# The owner's rule after rangsarn's run 03: two vendors came out with one face,
# three baskets were copies, and a count question passed the wrong fruit.
twins = copy.deepcopy(EXAMPLE)
twins["subjects"][1].update(
    {"description": twins["subjects"][0]["description"], "appearance": twins["subjects"][0]["appearance"],
     "wardrobe": twins["subjects"][0].get("wardrobe", "")}
)
check(
    "two people described with the same words are warned",
    any("described almost alike" in w for w in image_spec.validate_spec(twins, WIDTH, HEIGHT, DEFAULTS)[1]),
)
check(
    "two people described differently are not",
    not any("described almost alike" in w for w in image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)[1]),
)
check(
    "the shipped real place's two fighters are no longer twins",
    not any("described almost alike" in w for w in image_spec.validate_spec(REAL_PLACE, WIDTH, HEIGHT, DEFAULTS)[1]),
)
two_people_prompt = image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check("the prompt gives every person a face of their own", "a face, a build and an age of their own" in two_people_prompt)
q45 = {q["id"]: q for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))}
check("and the review compares their faces", "q_distinct_faces" in q45)
alone = copy.deepcopy(EXAMPLE)
alone["subjects"] = alone["subjects"][:1]
alone["camera"]["focus_on"] = "pharmacist"
alone_q = {q["id"] for q in image_spec.build_questions(alone, image_spec.derive(alone, WIDTH, HEIGHT))}
check("one person is not compared with nobody", "q_distinct_faces" not in alone_q)

baskets = copy.deepcopy(EXAMPLE)
baskets["objects"][1].update(
    {"name": "round woven bamboo baskets of bananas, pomelos and mangoes", "count": 3}
)
b_q = {q["id"]: q for q in image_spec.build_questions(baskets, image_spec.derive(baskets, WIDTH, HEIGHT))}
check(
    "the count counts the baskets, not the fruit",
    b_q["q_medicine_box"]["question"].startswith("Does the image show exactly 3 round woven bamboo baskets")
    and "mangoes" not in b_q["q_medicine_box"]["question"],
    b_q["q_medicine_box"]["question"],
)
check(
    "and each content is asked on its own",
    [b_q[f"q_medicine_box_holds_{i:02d}"]["question"] for i in (1, 2, 3)]
    == [f"Does one of the round woven bamboo baskets hold {f}, as the spec lists?" for f in ("bananas", "pomelos", "mangoes")],
)
check("repeated things are asked whether they are copies", "q_medicine_box_distinct" in b_q)
check("a single thing is not", "q_counter_distinct" not in b_q and "q_medicine_box_holds_01" not in q45)
_, b_warn = image_spec.validate_spec(baskets, WIDTH, HEIGHT, DEFAULTS)
check("three of a thing with no variation is warned", any("draws 3 copies" in w for w in b_warn), str(b_warn)[:200])
varied = copy.deepcopy(baskets)
varied["objects"][1]["variation"] = "one deeper and darker with age, one with a split rim, the mango basket half empty"
_, v_warn = image_spec.validate_spec(varied, WIDTH, HEIGHT, DEFAULTS)
check("and not once the variation is said", not any("draws 3 copies" in w for w in v_warn))
check(
    "and the prompt carries it",
    "Each of the 3 differs: one deeper and darker with age" in image_spec.compile_spec(varied, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)
one_ring = copy.deepcopy(EXAMPLE)
one_ring["objects"][0]["name"] = "boxing ring on a raised platform with red, white and blue ropes"
check(
    "a single thing whose name lists parts is not split into contents",
    not any("_holds_" in q["id"] for q in image_spec.build_questions(one_ring, image_spec.derive(one_ring, WIDTH, HEIGHT))),
)
check(
    "a name with one thing in it is not split",
    image_spec.listed_contents("small ceramic cup of iced black coffee") == ("small ceramic cup of iced black coffee", []),
)

print("C46 a matched set by design is not a copy")
# Found by the lite session: a solar array on one rail and a moulded pair of
# tiger sculptures were told to differ in size and angle.
pair = copy.deepcopy(EXAMPLE)
pair["objects"][1].update({"name": "moulded tiger sculptures", "count": 2, "variation": "matched, a moulded pair"})
pair_errors, pair_warn = image_spec.validate_spec(pair, WIDTH, HEIGHT, DEFAULTS)
check("a matched pair is not warned as copies", not any("copies" in w for w in pair_warn), str(pair_warn)[:200])
pair_q = {q["id"]: q for q in image_spec.build_questions(pair, image_spec.derive(pair, WIDTH, HEIGHT))}
check(
    "and is asked whether each sits in its own place, never whether they differ",
    "matched set that each sits in its own place" in pair_q["q_medicine_box_distinct"]["question"]
    and "differences" not in pair_q["q_medicine_box_distinct"]["question"],
    pair_q["q_medicine_box_distinct"]["question"],
)
check(
    "the prompt says it is matched by design",
    "a matched set, alike by design" in image_spec.compile_spec(pair, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)
unsaid = copy.deepcopy(pair)
unsaid["objects"][1].pop("variation")
unsaid_warn = image_spec.validate_spec(unsaid, WIDTH, HEIGHT, DEFAULTS)[1]
check(
    "with nothing said it is warned, and told it may write matched",
    any("copies" in w and 'write "matched"' in w for w in unsaid_warn),
    str(unsaid_warn)[:200],
)
for word in ("matched", "identical panels on one rail", "uniform", "alike by design", "a matched set"):
    check(f"{word!r} declares a matched set", image_spec.is_matched({"variation": word}))
check("a description of differences is not matched", not image_spec.is_matched({"variation": "one split, one newer"}))
crowd = copy.deepcopy(EXAMPLE)
crowd["subjects"][1].update({"count": 2, "variation": "matched"})
check(
    "people cannot be matched",
    any("people cannot be a matched set" in w for w in image_spec.validate_spec(crowd, WIDTH, HEIGHT, DEFAULTS)[1]),
)

print("C47 every review ends with an open question for what nothing else asks")
for spec_name, spec in (("example", EXAMPLE), ("real place", REAL_PLACE)):
    ids47 = [q["id"] for q in image_spec.build_questions(spec, image_spec.derive(spec, WIDTH, HEIGHT))]
    check(f"{spec_name}: the anomaly question is asked", "q_anomalies" in ids47)
q47 = {q["id"]: q for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))}
check(
    "it is judged, and its no carries the list in the evidence",
    not q47["q_anomalies"].get("verify_with") and "list each thing in the evidence" in q47["q_anomalies"]["question"],
)

print("C48 the failure library holds itself to its own rule")
# Proposed by the rangsarn session: every fault anyone finds becomes a named
# class, closed only with a prevention, a detection and a regression.
LIBRARY = json.loads(
    (ROOT / "reference" / "content-production" / "image-failure-classes.json").read_text(encoding="utf-8")
)
classes = LIBRARY["classes"]


def _text_ok(value):
    return isinstance(value, str) and bool(value.strip())


check("class ids are unique", len({c["id"] for c in classes}) == len(classes))
SOURCE = (ROOT / "scripts" / "image_spec.py").read_text(encoding="utf-8")
TEST_SOURCE = (ROOT / "scripts" / "image_spec_contract_test.py").read_text(encoding="utf-8")
for c in classes:
    for field in ("id", "symptom", "cause", "found_by", "prevention", "detection", "regression", "status"):
        check(f"{c['id']} has {field}", field in c)
    history = c.get("prevention_history", [])
    for entry in history:
        check(
            f"{c['id']} history entry is well formed",
            _text_ok(entry.get("case")) and entry.get("kind") in {"state", "restructure"} and _text_ok(entry.get("text"))
            and isinstance(entry.get("runs"), int) and entry.get("effective") in {True, False, "unmeasured"},
            str(entry),
        )
    newest = {}
    for entry in history:
        newest[entry.get("case")] = entry
    should_close = (
        bool(c["prevention"]) and bool(c["detection"]) and bool(c["regression"])
        and c.get("prevention_effective") is not False
        and all(entry.get("effective") is not False for entry in newest.values())
    )
    check(
        f"{c['id']} is {'closed' if should_close else 'open'} by the rule",
        c["status"] == ("closed" if should_close else "open"),
        c["status"],
    )
    for question in c["detection"]:
        # A literal id must appear quoted; a template's fixed suffix must appear,
        # and q_<id> itself is the entity count every subject and object gets.
        if "<" not in question:
            found = f'"{question}"' in SOURCE
        elif question == "q_<id>":
            found = 'base = f"q_{' in SOURCE
        else:
            fixed = max((p.replace("_NN", "_") for p in re.split(r"<[^>]+>", question)), key=len)
            found = len(fixed.strip("_")) > 1 and fixed in SOURCE
        check(f"{c['id']} detection {question!r} is a question the compiler writes", found)
    for section in c["regression"]:
        check(f"{c['id']} regression {section} exists", f'print("{section} ' in TEST_SOURCE)

_closed = copy.deepcopy(next(c for c in classes if c["status"] == "closed"))
_closed["prevention_history"] = [{"case": "x", "kind": "state", "text": "x", "runs": 2, "effective": False}]
_newest = {e["case"]: e for e in _closed["prevention_history"]}
check(
    "a class whose newest prevention for a case failed cannot be closed",
    not all(e.get("effective") is not False for e in _newest.values()),
)
check(
    "a failed stated prevention is kept beside the restructure that follows it",
    any(e["kind"] == "state" and e["effective"] is False for c in classes for e in c.get("prevention_history", []))
    and any(e["kind"] == "restructure" for c in classes for e in c.get("prevention_history", [])),
)

print("C49 a level camera above seated heads does not look down; locale comes early")
# Found by rangsarn's independent audit: an eye-level spec compiled to "looks
# down: the tops of the head and shoulders are visible", beside "from an eye
# level angle".
def seated_scene(**camera):
    spec = copy.deepcopy(EXAMPLE)
    for subject in spec["subjects"]:
        subject["posture"] = "seated"
    spec["camera"].update(camera)
    return spec


level = seated_scene(angle="eye_level", tilt="level", height_m=1.5)
level_prompt = " ".join(c["text"] for c in image_spec.build_clauses(
    level, image_spec.derive(level, WIDTH, HEIGHT), WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))
check(
    "an eye-level camera above seated heads never says it looks down",
    "and looks down: the tops" not in level_prompt and "passes just above their heads" in level_prompt,
    str([x for x in level_prompt.split(". ") if "camera" in x.lower()][:2]),
)
for camera, why in (({"angle": "high", "tilt": "down", "height_m": 1.5}, "a downward tilt"),
                    ({"angle": "high", "tilt": "level", "height_m": 2.6}, "the lens far above their heads")):
    spec = seated_scene(**camera)
    text = " ".join(c["text"] for c in image_spec.build_clauses(
        spec, image_spec.derive(spec, WIDTH, HEIGHT), WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))
    check(f"but {why} does", "and looks down: the tops" in text, str([x for x in text.split(". ") if "camera" in x.lower()][:2]))
crossing49 = image_spec.derive(level, WIDTH, HEIGHT)["horizon_crossings"][0]
check("the crossing records how far the lens is above the head", "above_head_by_m" in crossing49, str(crossing49))
local = copy.deepcopy(EXAMPLE)
local["location"]["locale_details"] = ["the pharmacist wears a white pharmacy coat with a name badge"]
local_prompt = image_spec.compile_spec(local, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check(
    "locale facts come before the people, where a common-world prior cannot overwrite them",
    local_prompt.index("Local details that must be right") < local_prompt.index("One "),
    local_prompt[:300],
)

print("C50 the viewpoint sentence knows the tilt, and an unseen horizon is an eye-level line")
# Three findings from the lite session's port of fce4562.
def _prompt_of(spec):
    return " ".join(c["text"] for c in image_spec.build_clauses(
        spec, image_spec.derive(spec, WIDTH, HEIGHT), WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))


tipped = seated_scene(angle="eye_level", tilt="down", height_m=1.36, horizon="above_frame")
tipped_text = _prompt_of(tipped)
check(
    "eye level and tilted down is not called level",
    "The camera is level" not in tipped_text and "tips slightly down" in tipped_text,
    str([x for x in tipped_text.split(". ") if "camera" in x.lower()][:2]),
)
indoor = seated_scene(angle="eye_level", tilt="level", height_m=1.5, horizon="not_visible")
indoor_own = " ".join(
    c["text"] for c in image_spec.build_clauses(
        indoor, image_spec.derive(indoor, WIDTH, HEIGHT), WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS))
    if c["group"] in {"opening", "camera"}
)
check(
    "an indoor scene with no horizon in frame: the compiler's camera sentences never name one",
    not re.search(r"\bhorizon\b", indoor_own, re.I) and "eye-level line" in indoor_own,
    str([x for x in indoor_own.split(". ") if "horizon" in x.lower()][:2]),
)
check("a horizon in frame is still a horizon", "horizon" in _prompt_of(EXAMPLE).lower())
# A valid scene this time: the lite session found the first version used a raise
# validate_spec refuses, and passed on the old code too.
raised50 = copy.deepcopy(EXAMPLE)
raised50["subjects"][1]["ground_height_m"] = 0.3
check("the raised scene is valid", not image_spec.validate_spec(raised50, WIDTH, HEIGHT, DEFAULTS)[0],
      str(image_spec.validate_spec(raised50, WIDTH, HEIGHT, DEFAULTS)[0][:1]))
raised_text = _prompt_of(raised50)
check(
    "the eye-height sentence names the pharmacist on the camera's floor, and not the raised customer",
    "eye height of the pharmacist," in raised_text and "older customer, so that horizon" not in raised_text,
    str([x for x in raised_text.split(". ") if "eye height" in x][:1]),
)
low_head = copy.deepcopy(EXAMPLE)
# 1.4 m keeps the mean eye height within the band, so the sentence is written,
# while this person's own eyes sit 0.25 m below the lens.
low_head["subjects"].append(dict(copy.deepcopy(EXAMPLE["subjects"][1]), id="child", short_name="child",
                                 description="a teenager beside the counter", height_m=1.4, distance_m=2.3,
                                 plane="midground"))
check("the teenager scene is valid", not image_spec.validate_spec(low_head, WIDTH, HEIGHT, DEFAULTS)[0],
      str(image_spec.validate_spec(low_head, WIDTH, HEIGHT, DEFAULTS)[0][:1]))
check("the scene does put the camera at eye height", image_spec.derive(low_head, WIDTH, HEIGHT)["camera_at_eye_height"])
eyes = [p["id"] for p in image_spec.eyes_on_horizon(low_head)]
check(
    "someone whose eyes are far below the lens is not said to have the horizon through them",
    "child" not in eyes and "pharmacist" in eyes,
    str(eyes),
)
low_text = _prompt_of(low_head)
check(
    "and the prompt does not name them in the eye-height sentence",
    not [x for x in low_text.split(". ") if "eye height of" in x and "child" in x],
    str([x for x in low_text.split(". ") if "eye height of" in x][:1]),
)
platform = copy.deepcopy(EXAMPLE)
platform["subjects"][1]["ground_height_m"] = 0.8
check(
    "a level camera at the floor people's eye height is not refused because someone stands on a platform",
    not [e for e in image_spec.validate_spec(platform, WIDTH, HEIGHT, DEFAULTS)[0] if "angle eye_level" in e],
    str(image_spec.validate_spec(platform, WIDTH, HEIGHT, DEFAULTS)[0][:2]),
)

print("C51 run 04: counts scoped to their container, crossings on cropped figures, real sizes")
q51 = {q["id"]: q for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))}
check(
    "a thing held by a declared person is counted there",
    q51["q_medicine_box"]["question"].endswith("held by the pharmacist?"),
    q51["q_medicine_box"]["question"],
)
check(
    "a thing on a surface named only in words is counted in the whole frame",
    q51["q_counter"]["question"].endswith("counter?") and "standing on" not in q51["q_counter"]["question"],
    q51["q_counter"]["question"],
)
cut = q51["q_horizon_cut_pharmacist"]
check(
    "a figure the frame cuts is measured against a landmark, never from hidden feet",
    "at about the eyes" in cut["question"] and "from the feet" not in cut["question"]
    and cut["measure"]["relation"] == "at_landmark",
    cut["question"],
)
whole = copy.deepcopy(EXAMPLE)
whole["camera"].update({"shot_type": "wide", "focal_length_mm": 24})
whole_q = {q["id"]: q for q in image_spec.build_questions(whole, image_spec.derive(whole, WIDTH, HEIGHT))}
check(
    "a whole figure is still measured from the feet",
    "from the feet" in whole_q["q_horizon_cut_pharmacist"]["question"],
    whole_q["q_horizon_cut_pharmacist"]["question"],
)
check("a crossing between landmarks is not forced onto one", image_spec.nearest_landmark(0.45) == "")
check("eye level snaps to the eyes", image_spec.nearest_landmark(0.957) == "eyes")
check(
    "scale is judged in real size, not as drawn",
    "Judge real sizes, not how large each looks at its distance" in q51["q_counter_scale"]["question"],
)
item51 = {"id": "x", "spec_compiled": {"questions": []}}
check(
    "the reviewer is told a child is skipped only when its parent thing is absent",
    "still answer every question below it" in image_spec.review_template(item51, DEFAULTS)["_instructions"],
)

print("C52 a landmark must be in the picture, and the frame must hold the head")
# Found by the lite session porting ab09d23, and checking its low-angle case.
check("a landmark below the frame's lower edge is never used", image_spec.nearest_landmark(0.53, 0.7) == "")
check("one above it is", image_spec.nearest_landmark(0.95, 0.7) == "eyes")
check(
    "the landmark table is built from the body table, not repeated",
    dict(image_spec.CROSSING_LANDMARKS)["hips"] == image_spec.BODY_LANDMARK_FRACTION["hip"],
)
low52 = copy.deepcopy(EXAMPLE)
low52["camera"].update({"height_m": 0.86, "angle": "low"})
d52 = image_spec.derive(low52, WIDTH, HEIGHT)
c52 = [c for c in d52["horizon_crossings"] if c["id"] == "pharmacist"][0]
check("each crossing records the lowest part the frame shows", c52.get("lowest_visible_fraction") is not None, str(c52))
low_text52 = " ".join(c["text"] for c in image_spec.build_clauses(low52, d52, WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))
low_q52 = {q["id"]: q for q in image_spec.build_questions(low52, d52)}["q_horizon_cut_pharmacist"]["question"]
landmark52 = image_spec.crossing_landmark(c52)
check(
    "the prompt and the question describe a cut figure's crossing the same way",
    bool(landmark52) and f"at about the {landmark52}" in low_text52 and f"at about the {landmark52}" in low_q52
    and "crosses the pharmacist about" not in low_text52,
    str([x for x in low_text52.split(". ") if "crosses the pharmacist" in x]),
)
_, low_warn52 = image_spec.validate_spec(low52, WIDTH, HEIGHT, DEFAULTS)
check(
    "a lens so low that the frame cuts the focus person's head is warned",
    any("is out of the picture" in w for w in low_warn52),
    str(low_warn52)[:200],
)
check(
    "and the shipped framing is not",
    not any("is out of the picture" in w for w in image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)[1]),
)

print("C53 a level camera's frame is known indoors, and a person outside it is warned")
# Two findings from the lite session's port of 457f9cc.
indoor53 = copy.deepcopy(EXAMPLE)
indoor53["camera"].update({"height_m": 0.86, "angle": "low", "horizon": "not_visible"})
check(
    "a level indoor camera too low for the focus person's head is warned",
    any("is out of the picture" in w for w in image_spec.validate_spec(indoor53, WIDTH, HEIGHT, DEFAULTS)[1]),
)
check("a level camera with the horizon hidden has its frame centred on the lens", image_spec.horizon_band({"tilt": "level", "horizon": "not_visible"}) == 0.5)
check("a tilted one does not", image_spec.horizon_band({"tilt": "up", "horizon": "not_visible"}) is None)
outside53 = copy.deepcopy(EXAMPLE)
outside53["subjects"].append(dict(copy.deepcopy(EXAMPLE["subjects"][1]), id="child", short_name="child",
                                  description="a small child", height_m=1.02, distance_m=2.2,
                                  plane="midground"))
check("the out-of-frame scene is valid", not image_spec.validate_spec(outside53, WIDTH, HEIGHT, DEFAULTS)[0],
      str(image_spec.validate_spec(outside53, WIDTH, HEIGHT, DEFAULTS)[0][:1]))
check(
    "a declared person wholly below the frame is warned",
    any("lies wholly below it" in w and "child" in w for w in image_spec.validate_spec(outside53, WIDTH, HEIGHT, DEFAULTS)[1]),
    str([w for w in image_spec.validate_spec(outside53, WIDTH, HEIGHT, DEFAULTS)[1] if "wholly" in w][:1]),
)
inside53 = copy.deepcopy(outside53)
inside53["subjects"][-1]["height_m"] = 1.6
check(
    "the same person tall enough to reach into the frame is not",
    not any("lies wholly" in w for w in image_spec.validate_spec(inside53, WIDTH, HEIGHT, DEFAULTS)[1]),
)

print("C54 a seated child is not an adult's seated height")
check("a 1.65 m adult seated on a chair keeps 1.23 m", abs(image_spec.posture_eye_m("seated", 1.65) - 1.23) < 1e-9)
check("a taller adult sits a little higher, on the same seat", 1.23 < image_spec.posture_eye_m("seated", 1.85) < 1.35)
check(
    "a 1.02 m child seated scales with stature",
    abs(image_spec.posture_eye_m("seated", 1.02) - (0.45 + 0.78 * 1.02 / 1.65)) < 1e-9,
)
check("lying flat does not scale", image_spec.posture_eye_m("lying", 1.02) == 0.25)
seated_child = copy.deepcopy(outside53)
seated_child["subjects"][-1]["posture"] = "seated"
check("the seated-child scene is valid", not image_spec.validate_spec(seated_child, WIDTH, HEIGHT, DEFAULTS)[0],
      str(image_spec.validate_spec(seated_child, WIDTH, HEIGHT, DEFAULTS)[0][:1]))
check(
    "a seated child wholly below the frame is warned",
    any("lies wholly below it" in w and "child" in w for w in image_spec.validate_spec(seated_child, WIDTH, HEIGHT, DEFAULTS)[1]),
    str([w for w in image_spec.validate_spec(seated_child, WIDTH, HEIGHT, DEFAULTS)[1] if "child" in w][:1]),
)

print("C55 the viewpoint question and the prompt use one looks-down test")
# Found by the lite session: an indoor eye-level scene told the generator the
# face is seen straight on, then asked whether the top of the head shows.
def _viewpoint(spec):
    d = image_spec.derive(spec, WIDTH, HEIGHT)
    text = " ".join(c["text"] for c in image_spec.build_clauses(spec, d, WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))
    q = {x["id"]: x for x in image_spec.build_questions(spec, d)}
    return text, q


indoor55 = seated_scene(angle="eye_level", tilt="level", height_m=1.36, horizon="not_visible")
check("the indoor eye-level scene is valid", not image_spec.validate_spec(indoor55, WIDTH, HEIGHT, DEFAULTS)[0],
      str(image_spec.validate_spec(indoor55, WIDTH, HEIGHT, DEFAULTS)[0][:1]))
text55, q55 = _viewpoint(indoor55)
views = {k: v["measure"]["expected"] for k, v in q55.items() if k.startswith("q_viewpoint_")}
check(
    "a level camera a little above seated eyes asks for the face straight on, never the top of the head",
    views and all(v == "straight_on" for v in views.values()) and "and looks down: the tops" not in text55,
    str(views),
)
tipped55 = seated_scene(angle="high", tilt="down", height_m=1.6, horizon="not_visible")
text_t, q_t = _viewpoint(tipped55)
views_t = {k: v["measure"]["expected"] for k, v in q_t.items() if k.startswith("q_viewpoint_")}
check(
    "a camera tilted down asks from above, and the prompt says it looks down",
    views_t and all(v == "from_above" for v in views_t.values()) and "and looks down: the tops" in text_t,
    str(views_t),
)
check(
    "one function decides both",
    image_spec.camera_looks_down({"angle": "eye_level", "tilt": "down"}, {"above_head": True, "above_head_by_m": 0.3}) is False
    and image_spec.camera_looks_down({"angle": "high", "tilt": "level"}, {"above_head": True, "above_head_by_m": 0.1}) is True,
)

print("C56 an eye-level label is the standing people's; a head far below is seen from above")
# Found by the lite session porting 86cf0d1: a floor-seated vendor 0.74 m below
# an eye-level lens was told "level and a little above the eyes".
vendor56 = copy.deepcopy(EXAMPLE)
vendor56["camera"].update({"focal_length_mm": 35, "shot_type": "medium_wide", "horizon": "not_visible"})
vendor56["subjects"].append(dict(copy.deepcopy(EXAMPLE["subjects"][1]), id="vendor", short_name="vendor",
                                 description="a vendor sitting on the floor", height_m=1.55, distance_m=3.0,
                                 posture="floor_seated", plane="background"))
check("the vendor scene is valid", not image_spec.validate_spec(vendor56, WIDTH, HEIGHT, DEFAULTS)[0],
      str(image_spec.validate_spec(vendor56, WIDTH, HEIGHT, DEFAULTS)[0][:1]))
text56, q56 = _viewpoint(vendor56)
vendor_q = q56.get("q_viewpoint_vendor", {})
check(
    "the review asks whether she is seen from above",
    vendor_q.get("measure", {}).get("expected") == "from_above",
    str(vendor_q.get("question", "(none)"))[:120],
)
check(
    "and the prompt says the camera looks down on her, not that it is a little above her eyes",
    "higher than the vendor and looks down" in text56 and "a little above the eyes of the vendor" not in text56,
    str([x for x in text56.split(". ") if "vendor" in x][:2]),
)
check(
    "a head just below an eye-level lens is still seen straight on",
    image_spec.camera_looks_down({"angle": "eye_level", "tilt": "level"}, {"above_head": True, "above_head_by_m": 0.1}) is False,
)

print("C57 run 05: one hand at a time, contents from their source, nothing said twice")
# Three faults the owner found in rangsarn's run 05 that every reader missed.
check(
    "both phrasings of two hands are read",
    image_spec.hand_items("a spoon in the right hand and a fork in the left") == {"right": "a spoon", "left": "a fork"}
    and image_spec.hand_items("right hand holds a spoon, left hand holds a fork") == {"right": "a spoon", "left": "a fork"},
)
check("one hand's action is not split", image_spec.hand_items("both hands cup the bowl") == {})


def diner(position):
    spec = copy.deepcopy(EXAMPLE)
    spec["subjects"][1].update({"hands": "a spoon in the right hand and a fork in the left", "position": position})
    return spec


away = diner("right of centre, nearer the camera, back to the camera")
away_q = {q["id"]: q["question"] for q in image_spec.build_questions(away, image_spec.derive(away, WIDTH, HEIGHT))}
check(
    "each hand is asked on its own, from the person's side, with the picture side when they face away",
    "own right, which is on the right of the picture" in away_q.get("q_customer_hand_right", "")
    and "own left, which is on the left of the picture" in away_q.get("q_customer_hand_left", ""),
    str({k: v for k, v in away_q.items() if "_hand_" in k}),
)
toward = diner("right of centre, facing the camera")
toward_q = {q["id"]: q["question"] for q in image_spec.build_questions(toward, image_spec.derive(toward, WIDTH, HEIGHT))}
check(
    "and the sides swap for someone facing the camera",
    "own right, which is on the left of the picture" in toward_q.get("q_customer_hand_right", ""),
    toward_q.get("q_customer_hand_right", ""),
)
away_text = image_spec.compile_spec(away, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check(
    "the prompt binds hands to picture sides for someone with their back to the camera",
    "own right hand is on the right of the picture" in away_text,
)

plates = copy.deepcopy(EXAMPLE)
plates["objects"][1]["filled_from"] = ["counter"]
plates_q = {q["id"]: q["question"] for q in image_spec.build_questions(plates, image_spec.derive(plates, WIDTH, HEIGHT))}
check(
    "a thing filled from declared sources is asked to hold only what they provide",
    "one of these, as served from it: the counter" in plates_q.get("q_medicine_box_contents", ""),
    plates_q.get("q_medicine_box_contents", "(none)"),
)
check(
    "and the prompt says so",
    "only what comes from the counter" in image_spec.compile_spec(plates, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)
refuses("filled_from must name declared things", "filled_from 'nowhere' is not a known id",
        lambda spec: spec["objects"][1].update({"filled_from": ["nowhere"]}))


def doubled(state):
    spec = diner("right of centre, nearer the camera")
    spec["objects"][0]["state"] = state
    return [w for w in image_spec.validate_spec(spec, WIDTH, HEIGHT, DEFAULTS)[1] if "draws it twice" in w]


check(
    "an object whose state names what a hand already holds is warned",
    any('"spoon"' in w and '"fork"' in w for w in doubled("a spoon and fork laid on each place")),
    str(doubled("a spoon and fork laid on each place")),
)
check("and one whose state does not is not", not doubled("wiped clean, with a glass jar of cotton buds at one end"))
check("plural stock is not the held one drawn again", not doubled("a tray of clean spoons and forks at one end"))
check("a pronoun is not a held thing", image_spec.held_things("holds her fork beside it") == {"fork"},
      str(image_spec.held_things("holds her fork beside it")))
check("the filled_from clause carries no negation", not image_spec.negations("holds only what comes from the counter"))
hers = copy.deepcopy(EXAMPLE)
hers["subjects"][1].update({"hands": "her spoon in the right hand and her fork in the left",
                            "position": "right of centre, back to the camera"})
hers_q = {q["id"]: q["question"] for q in image_spec.build_questions(hers, image_spec.derive(hers, WIDTH, HEIGHT))}
check(
    "the hand questions use the subject's own possessive",
    "her own right" in hers_q.get("q_customer_hand_right", ""),
    hers_q.get("q_customer_hand_right", "(none)"),
)
check(
    "and so does the facing sentence",
    "has her back to the camera, so her own right hand" in image_spec.compile_spec(hers, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)
check("nor is a word used as a modifier", not doubled("a spoon rest and a fork holder at one end"))

print("C58 an invariant is checked part by part, and a size comparison in real size")
# rangsarn run 08: a serving spoon's invariant passed on its bowl alone while
# the handle rested on another plate.
inv58 = {q["id"]: q["question"] for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))}
first = inv58["q_invariant_01"]
check(
    "every invariant is checked part by part, each part named in the evidence",
    "Check each part on its own and answer yes only if every part holds" in first,
    first[-160:],
)
sized58 = copy.deepcopy(EXAMPLE)
sized58["physical_invariants"] = ["the serving spoon's bowl is about 1.5 times an eating spoon's bowl"]
sized_q = {q["id"]: q["question"] for q in image_spec.build_questions(sized58, image_spec.derive(sized58, WIDTH, HEIGHT))}
check(
    "a size comparison in an invariant is judged in real size",
    "Judge real sizes" in sized_q["q_invariant_01"],
)
check(
    "one without a comparison is not told to",
    not image_spec.SIZE_COMPARE_RE.search("the counter separates the two people"),
)
for phrase in ("twice as long as the fork", "larger than the plate", "as wide as the shoulders", "1.5 times an eating spoon"):
    check(f"{phrase!r} is a size comparison", bool(image_spec.SIZE_COMPARE_RE.search(phrase)))

print("C59 a hand that rests or gestures is asked about too; facing and pronouns read right")
# From the sweep session and the lite session.
check(
    "a hand that rests is its own clause",
    image_spec.hand_clauses("her right hand holds a round hand mirror and her left rests on the chair arm")
    == {"right": "holds a round hand mirror", "left": "rests on the chair arm"},
)
check(
    "so is a raised hand",
    image_spec.hand_clauses("his right hand is raised, his left hand rests on his knee")["right"] == "is raised",
)
check(
    "a single held thing names its own item",
    image_spec.hand_clauses("the woman carries a plastic cup in her right hand") == {"right": "holds a plastic cup"},
)
check(
    "from behind the head of the bed is a place, not a back to the camera",
    image_spec.facing({"position": "leaning in from behind the head of the bed"}) == "",
)
check("seen from behind still is", image_spec.facing({"position": "seen from behind"}) == "away")
check("the pronoun before the person's own hand decides", image_spec.possessive({"hands": "his left hand rests on her shoulder"}) == "his")
one_hand = copy.deepcopy(EXAMPLE)
one_hand["subjects"][1]["hands"] = "the phone in her left hand"
one_q = {q["id"]: q["question"] for q in image_spec.build_questions(one_hand, image_spec.derive(one_hand, WIDTH, HEIGHT))}
check(
    "one named hand gets its own question",
    "q_customer_hand_left" in one_q and "that holds the phone" in one_q["q_customer_hand_left"],
    str({k: v for k, v in one_q.items() if "_hand_" in k}),
)
check(
    "a real-size sentence stays out of a foreshortening rule",
    not (image_spec.SIZE_COMPARE_RE.search("the far page reads shorter than the near one")
         and not image_spec.APPEARANCE_RE.search("the far page reads shorter than the near one")),
)
check("or a position", not image_spec.SIZE_COMPARE_RE.search("the scale hangs higher than the shelf top"))
check("or an event", not image_spec.SIZE_COMPARE_RE.search("the bell has rung twice"))
check("and still marks a real comparison", bool(image_spec.SIZE_COMPARE_RE.search("twice the length of the fork")))

print("C60 a drawing is not told it is a photograph")
drawn60 = copy.deepcopy(EXAMPLE)
drawn60.update({"medium": "illustration"})
drawn60["style"]["look"] = "flat editorial illustration with soft grain"
for key in ("focal_length_mm", "aperture_f", "subject_distance_m", "height_m"):
    drawn60["camera"].pop(key, None)
drawn_text = " ".join(c["text"] for c in image_spec.build_clauses(
    drawn60, image_spec.derive(drawn60, WIDTH, HEIGHT), WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))
check(
    "an illustration's marks of use do not call it a photograph",
    "The scene carries the marks of use" in drawn_text and "This is a photograph" not in drawn_text,
    str([x for x in drawn_text.split(". ") if "marks of use" in x][:1]),
)
check(
    "a photograph still is one",
    "This is a photograph of a real place" in image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)

print("C61 backs to the camera, whole clauses, and the member whose hand it is")
# Three defects the sweep session found in 00bf8dc's per-hand questions.
check("their backs to the camera is facing away", image_spec.facing({"pose": "side by side with their backs to the camera"}) == "away")
check("viewed from behind is too", image_spec.facing({"position": "viewed from behind"}) == "away")
parts = image_spec.hand_clause_parts("his right hand holds a resin nose model upright between thumb and two fingers")
check(
    "an and inside a clause stays in it",
    len(parts) == 1 and parts[0]["doing"].endswith("between thumb and two fingers"),
    str(parts),
)
pinch = image_spec.hand_clause_parts("her right thumb and index finger pinch the edge of a tray and her left index finger steadies the jaw")
check(
    "a clause naming a finger is asked as whose, and a new side starts a new clause",
    [p["side"] for p in pinch] == ["right", "left"] and all(p["whose"] for p in pinch)
    and pinch[0]["doing"].startswith("thumb and index finger pinch"),
    str(pinch),
)
group61 = copy.deepcopy(EXAMPLE)
group61["subjects"][1].update({
    "count": 2, "variation": "an older man in grey and a younger woman in green",
    "hands": "the man holds a phone low in his right hand and the woman lets her hands hang at her sides",
    "pose": "side by side with their backs to the camera",
})
g_q = {q["id"]: q["question"] for q in image_spec.build_questions(group61, image_spec.derive(group61, WIDTH, HEIGHT))}
right61 = g_q.get("q_customer_hand_right", "")
check(
    "a group's question names the member and their pronoun, and the side flips for backs to the camera",
    "the right hand of the man among" in right61 and "his own right, which is on the right of the picture" in right61,
    right61,
)
check("a clause with no side asks nothing", "q_customer_hand_left" not in g_q)

print("C62 a drawn picture is told it is drawn, start to end")
# rangsarn run 10: all three monochrome drawn styles came back in full colour.
ink = copy.deepcopy(drawn60)
ink["style"]["look"] = "black ink line art on cream paper with one warm wash"
ink["lighting"]["color_temperature_k"] = 4800
ink_text = " ".join(c["text"] for c in image_spec.build_clauses(
    ink, image_spec.derive(ink, WIDTH, HEIGHT), WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))
ink_prompt = image_spec.compile_spec(ink, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check(
    "a drawing's last line restates its medium",
    ink_prompt.rstrip(" .").endswith("drawn as black ink line art on cream paper with one warm wash, in that palette only"),
    ink_prompt[-160:],
)
check(
    "and stays last after an inline Constraints block",
    "Constraints: no " in ink_prompt and ink_prompt.index("Constraints: no ") < ink_prompt.index("Every part of the picture is drawn as"),
    ink_prompt[-200:],
)
check("it carries no colour temperature in kelvin", not re.search(r"[0-9]+ ?K[.,; ]", ink_prompt), ink_prompt[:200])
check("its light is described within the style's tones", "shown only in the tones of black ink line art" in ink_text)
check("a colour fill is left out of a monochrome drawing", "Fill:" not in ink_text)
check("its physics line speaks of one viewpoint, not one camera", "one camera viewpoint" not in ink_text and "one viewpoint" in ink_text)
check("its lettering is loosely indicated, not out of focus", "out of focus" not in ink_text)
gouache = copy.deepcopy(drawn60)
gouache["style"]["look"] = "gouache illustration in warm saturated colour"
g_text = " ".join(c["text"] for c in image_spec.build_clauses(
    gouache, image_spec.derive(gouache, WIDTH, HEIGHT), WIDTH, HEIGHT, image_spec.policy_from_config(DEFAULTS)))
check("a painterly colour style keeps its fills", "Fill:" in g_text and "shown only in the tones" not in g_text)
check("a photograph keeps its camera words", "one camera viewpoint" in image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)["prompt"])
check(
    "a locale detail about the text itself is warned",
    any("talks about the text" in w for w in image_spec.validate_spec(
        dict(copy.deepcopy(EXAMPLE), location=dict(EXAMPLE["location"], locale_details=["the species is named exactly, and its field marks are written out"])),
        WIDTH, HEIGHT, DEFAULTS)[1]),
)
check(
    "and one about the picture is not",
    not any("talks about the text" in w for w in image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)[1]),
)

print("C63 colour words out of a monochrome drawing; the medium asked; where a front points")
# rangsarn run 12.
check("colour words come out", image_spec.decolour("faded green fabric shade over a steel frame") == "fabric shade over a steel frame")
check("a colour compound comes out whole", image_spec.decolour("a red-and-white checked cloth") == "a checked cloth")
check("the ink palette's own black and white stay", image_spec.decolour("white dispensing coat, black hair") == "white dispensing coat, black hair")
ink63 = copy.deepcopy(ink)
ink63["subjects"][0]["wardrobe"] = "faded green apron over a red shirt"
ink_prompt63 = image_spec.compile_spec(ink63, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check(
    "a monochrome drawing's people, things and layout carry no colour words",
    "green apron" not in ink_prompt63 and "red shirt" not in ink_prompt63 and "sage-green shelving" not in ink_prompt63,
)
check("its own palette is kept as the author wrote it", "Color palette:" in ink_prompt63)
check("and the spec itself is left as written", ink63["subjects"][0]["wardrobe"] == "faded green apron over a red shirt")
gouache63 = copy.deepcopy(gouache)
gouache63["subjects"][0]["wardrobe"] = "faded green apron over a red shirt"
check("a colour style keeps them", "faded green apron" in image_spec.compile_spec(gouache63, WIDTH, HEIGHT, DEFAULTS)["prompt"])
drawn_q = {q["id"]: q["question"] for q in image_spec.build_questions(ink63, image_spec.derive(ink63, WIDTH, HEIGHT))}
check("every drawn spec is asked about its medium", "drawn as black ink line art" in drawn_q.get("q_medium", ""))
check("a photograph is not", "q_medium" not in {q["id"] for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))})
boat = copy.deepcopy(EXAMPLE)
boat["objects"][0]["heading_toward"] = "pharmacist"
boat_q = {q["id"]: q["question"] for q in image_spec.build_questions(boat, image_spec.derive(boat, WIDTH, HEIGHT))}
check("a heading is asked", boat_q.get("q_counter_heading") == "Does the front of the counter point toward the pharmacist?", boat_q.get("q_counter_heading", "(none)"))
check("and said", "The front of the counter points toward the pharmacist" in image_spec.compile_spec(boat, WIDTH, HEIGHT, DEFAULTS)["prompt"])

print("C64 sizes pinned by the horizon for things; seats paired with tables; pouring")
# The owner: sizes are very wrong in every picture. From rangsarn's audit.
car = copy.deepcopy(wide44)
car["objects"].append({
    "id": "car", "short_name": "car", "name": "compact white hatchback", "count": 1,
    "material": "painted steel and glass", "state": "parked, clean", "height_m": 1.5, "width_m": 4.0,
    "scale_anchor": "its roof is level with the pharmacist's chin", "support": {"kind": "stands_on", "by": "the road"},
    "position": "far right, beyond the counter", "distance_m": 9.0, "plane": "background",
})
car_derived = image_spec.derive(car, WIDTH, HEIGHT)
car_x = [c for c in car_derived["object_horizon_crossings"] if c["id"] == "car"]
check(
    "a grounded thing gets a crossing at camera height over its height",
    car_x and abs(car_x[0]["fraction_of_height_from_base"] - round(1.55 / 1.5, 3)) < 1e-9,
    str(car_x),
)
car_q = {q["id"]: q["question"] for q in image_spec.build_questions(car, car_derived)}
check("and a question", "q_horizon_cut_car" in car_q, str([k for k in car_q if "horizon_cut" in k]))
far = copy.deepcopy(car)
far["objects"][-1]["distance_m"] = 45.0
check("a thing far beyond 30 m gets none", not [c for c in image_spec.derive(far, WIDTH, HEIGHT)["object_horizon_crossings"] if c["id"] == "car"])
tall = copy.deepcopy(car)
tall["objects"][-1].update({"height_m": 12.0, "name": "shophouse block"})
check("nor does a building", not [c for c in image_spec.derive(tall, WIDTH, HEIGHT)["object_horizon_crossings"] if c["id"] == "car"])
check("a held thing gets none", not [c for c in image_spec.derive(EXAMPLE, WIDTH, HEIGHT)["object_horizon_crossings"] if c["id"] == "medicine_box"])
check("a tuk-tuk has a height band", image_spec.reference_height("blue tuk-tuk")[:2] == (1.65, 1.95))
check("a name is matched on its head noun", image_spec.reference_height("folding steel tables with plastic stools") is None)


def seating(stool, table):
    spec = copy.deepcopy(EXAMPLE)
    spec["objects"].extend([
        {"id": "stool", "short_name": "stool", "name": "red plastic stool", "count": 1, "material": "moulded plastic",
         "state": "empty", "height_m": stool, "scale_anchor": "its seat meets the pharmacist's knee",
         "support": {"kind": "stands_on", "by": "the floor"}, "position": "lower left", "distance_m": 2.6, "plane": "midground"},
        {"id": "table", "short_name": "table", "name": "steel folding table", "count": 1, "material": "steel",
         "state": "wiped clean", "height_m": table, "scale_anchor": "its top meets the pharmacist's hip",
         "support": {"kind": "stands_on", "by": "the floor"}, "position": "lower left", "distance_m": 2.7, "plane": "midground"},
    ])
    return [w for w in image_spec.validate_spec(spec, WIDTH, HEIGHT, DEFAULTS)[1] if "seat has no table" in w]


check("a stool with no table at a usable height above it is warned", bool(seating(0.45, 0.33)))
check("a stool with its folding table is not", not seating(0.45, 0.72))
check("an adult stool at a child's table is warned (0.20 m above a 0.40 m seat)", bool(seating(0.40, 0.60)))
check("and one too high above it (0.37 m above a 0.45 m seat)", bool(seating(0.45, 0.82)))
check("a child's stool at its own table is not (EN size mark 2)", not seating(0.31, 0.53))
check("the band follows EN 1729-1 at size mark 6", image_spec.seat_to_table_m(0.46) == (0.26, 0.34))
ladle = copy.deepcopy(EXAMPLE)
ladle["subjects"][0]["action"] = "ladles broth from the pot into a bowl"
ladle_q = {q["id"] for q in image_spec.build_questions(ladle, image_spec.derive(ladle, WIDTH, HEIGHT))}
check("a scene that pours is asked where the liquid leaves", "q_pour" in ladle_q)
check("and told", image_spec.POUR_RULE in image_spec.compile_spec(ladle, WIDTH, HEIGHT, DEFAULTS)["prompt"])
check("one that does not, is not", "q_pour" not in {q["id"] for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))})

print("C65 an inventory of openings and practicals closes the scene's light")
# Agreed with the rangsarn session: a second lit window appeared where one was allowed.
def lit_room(**overrides):
    spec = copy.deepcopy(EXAMPLE)
    spec["openings"] = [
        {"id": "shop_window", "kind": "window", "wall": "left", "state": "open", "lit": True, "light": "daylight"},
        {"id": "back_door", "kind": "door", "wall": "back", "state": "closed", "lit": False},
    ]
    spec["practicals"] = [{"id": "ceiling_fluorescent", "kind": "ceiling tube", "lit": True, "position": "overhead"}]
    spec.update(overrides)
    return spec


room = lit_room()
room_errors, room_warnings = image_spec.validate_spec(room, WIDTH, HEIGHT, DEFAULTS)
check("an inventory whose key and fill are lit entries is valid and unwarned",
      not room_errors and not [w for w in room_warnings if "inventory" in w or "openings" in w],
      str(room_errors[:1] + room_warnings[:2]))
room_prompt = image_spec.compile_spec(room, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check(
    "the prompt closes the scene's light",
    "The only light comes from the window in the left wall and the ceiling tube overhead" in room_prompt
    and "every other window and doorway is closed and dark" in room_prompt,
    [x for x in room_prompt.split(". ") if "only light" in x][:1],
)
room_q = {q["id"]: q["question"] for q in image_spec.build_questions(room, image_spec.derive(room, WIDTH, HEIGHT))}
check("the review asks which sources are lit", "q_light_sources" in room_q and "the window in the left wall" in room_q["q_light_sources"])
check("and each stated opening's state", room_q.get("q_back_door_state", "").startswith("Is the door in the back wall closed, and dark"))
dark_key = lit_room()
dark_key["openings"][0]["lit"] = False
refuses_text = image_spec.validate_spec(dark_key, WIDTH, HEIGHT, DEFAULTS)[0]
check("a key light from no lit entry is refused", any("none of the lit openings" in e for e in refuses_text), str(refuses_text[:1]))
unlisted = lit_room(practicals=[])
check(
    "a fill that is a source of its own and not listed is warned",
    any("does not list" in w for w in image_spec.validate_spec(unlisted, WIDTH, HEIGHT, DEFAULTS)[1]),
)
facing_walls = lit_room()
facing_walls["openings"].append({"id": "far_window", "kind": "window", "wall": "right", "state": "open", "lit": True})
facing_walls["lighting"]["fill"] = []
check(
    "lit openings facing each other with one key and no fill are warned",
    any("face each other" in w for w in image_spec.validate_spec(facing_walls, WIDTH, HEIGHT, DEFAULTS)[1]),
)
check("a spec without an inventory behaves as before", "q_light_sources" not in {q["id"] for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))})

print("C66 lit means true; names match whole words; sun from a lit wall counts")
# Three findings from the lite session's port of d0e241a.
loose = lit_room()
loose["openings"][1]["lit"] = "false"
loose_errors, loose_warn = image_spec.validate_spec(loose, WIDTH, HEIGHT, DEFAULTS)
check("a lit that is not true or false is warned", any("not true or false" in w for w in loose_warn))
check(
    "and read as dark",
    "the door in the back wall" not in [x for x in image_spec.compile_spec(loose, WIDTH, HEIGHT, DEFAULTS)["prompt"].split(". ") if "only light" in x][0],
)
outdoor = lit_room()
outdoor["openings"][0]["lit"] = False
outdoor["practicals"] = []
outdoor["openings"].append({"id": "side_door", "kind": "door", "wall": "right", "state": "open", "lit": True})
outdoor["lighting"]["key"]["source"] = "flat outdoor daylight"
outdoor["lighting"]["key"]["direction"] = "front_left"
check(
    "a key that names no lit entry is refused even when a substring would match",
    any("none of the lit openings" in e for e in image_spec.validate_spec(outdoor, WIDTH, HEIGHT, DEFAULTS)[0]),
)
sunlit = lit_room()
sunlit["lighting"]["key"]["source"] = "low afternoon sun"
sunlit["lighting"]["key"]["direction"] = "front_left"
check(
    "sun from the side a lit daylight window is on counts as that window",
    not [e for e in image_spec.validate_spec(sunlit, WIDTH, HEIGHT, DEFAULTS)[0] if "none of the lit openings" in e],
    str(image_spec.validate_spec(sunlit, WIDTH, HEIGHT, DEFAULTS)[0][:1]),
)

print("C67 physical checks by trigger; support capacity; a fresh look first")
# Settled in debate with the rangsarn session.
def checked(*entries):
    spec = copy.deepcopy(EXAMPLE)
    spec["physical_checks"] = list(entries)
    derived = image_spec.derive(spec, WIDTH, HEIGHT)
    return (
        spec,
        {q["id"]: q for q in image_spec.build_questions(spec, derived)},
        image_spec.compile_spec(spec, WIDTH, HEIGHT, DEFAULTS)["prompt"],
    )


LABEL = {"check": "A printed label faces the person reading it", "trigger": r"\blabel\b"}
BUFFALO = {"check": "A buffalo stands with all four hooves on the ground it is on", "trigger": r"\bbuffalo", "prompt": True}
_, q67, p67 = checked(LABEL, BUFFALO)
check("a triggered check is asked, in a group of its own", q67.get("q_check_01", {}).get("group") == "check", str([k for k in q67 if "check" in k]))
check("but not said, unless prompt is true", LABEL["check"] not in p67)
check("an untriggered check is neither asked nor said", len([k for k in q67 if k.startswith("q_check_")]) == 1 and "buffalo" not in p67.lower())
_, q67b, p67b = checked(dict(LABEL, prompt=True, ask=False))
check("prompt true says it; ask false does not ask it", LABEL["check"] in p67b and not [k for k in q67b if k.startswith("q_check_")])
refuses("a trigger that is not a pattern is refused", "not a valid pattern", lambda s: s.update(physical_checks=[{"check": "x", "trigger": "("}]))
refuses("ask must be true or false", "must be true or false", lambda s: s.update(physical_checks=[{"check": "x", "ask": "yes"}]))
refuses("a check needs its words", "needs a check", lambda s: s.update(physical_checks=[{"trigger": "label"}]))


def loaded(on_counter, step_width=None):
    spec = copy.deepcopy(EXAMPLE)
    for oid, width, count in on_counter:
        spec["objects"].append({
            "id": oid, "short_name": oid.replace("_", " "), "name": "stacked " + oid.replace("_", " "), "count": count,
            "material": "moulded plastic", "state": "empty", "height_m": 0.79, "width_m": width,
            "scale_anchor": "its top reaches the pharmacist's wrist", "support": {"kind": "stands_on", "by": "counter"},
            "position": "on the counter, left of centre", "distance_m": 1.95, "plane": "midground",
            "variation": "each a little different in wear",
        })
    if step_width:
        spec["objects"].append({
            "id": "step", "short_name": "step", "name": "wooden step", "count": 1, "material": "wood",
            "state": "worn", "height_m": 0.2, "width_m": step_width, "scale_anchor": "it reaches the customer's ankle",
            "support": {"kind": "stands_on", "by": "the tiled floor"}, "position": "right of centre", "distance_m": 1.5,
            "plane": "foreground",
        })
        spec["subjects"][1]["position"] = "on the step, " + spec["subjects"][1]["position"]
    errors, warnings = image_spec.validate_spec(spec, WIDTH, HEIGHT, DEFAULTS)
    return errors, [w for w in warnings if "side by side" in w], image_spec.derive(spec, WIDTH, HEIGHT)["support_loads"]


over_errors, over, over_loads = loaded([("basket", 0.45, 5), ("till", 0.5, 1)])
check("things on a declared supporter wider than it are warned", bool(over) and "2.75 m in all" in over[0], str(over or over_errors[:1]))
check("things that fit it are not", not loaded([("basket", 0.45, 2), ("till", 0.5, 1)])[1])
check("a person standing on a declared supporter counts 0.5 m", bool(loaded([], step_width=0.4)[1]) and not loaded([], step_width=0.6)[1])
check(
    "derive reports what was checkable",
    over_loads["on_declared_supporter"] == 2 and over_loads["resting"] == over_loads["on_declared_supporter"] + 3,  # the counter and two people
    str({k: v for k, v in over_loads.items() if k != "loads"}),
)
_rest = copy.deepcopy(EXAMPLE)
_rest["objects"].append({
    "id": "stock", "name": "small white medicine cartons", "short_name": "cartons", "count": 40, "width_m": 0.08,
    "height_m": 0.12, "distance_m": 3.6, "plane": "background", "position": "on the shelves",
    "support": {"kind": "rests_on", "by": "shelving"}, "state": "squared up in rows on five shelves",
    "material": "printed card", "scale_anchor": "each about the size of the pharmacist's hand",
})
check(
    "things resting on a surface are never summed: they sit in two dimensions and on tiers",
    not [w for w in image_spec.validate_spec(_rest, WIDTH, HEIGHT, DEFAULTS)[1] if "cannot hold" in w],
)
_lean = copy.deepcopy(EXAMPLE)
_lean["subjects"][1]["position"] = "foreground right, leaning on the counter with both elbows"
check(
    "leaning on a counter is not standing on it",
    not [r for load in image_spec.support_loads(_lean)["loads"] for r in load["items"] if r["id"] == "customer"],
    str({k: v for k, v in over_loads.items() if k != "loads"}),
)

first = image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))
check("q_anomalies is asked first", first[0]["id"] == "q_anomalies", first[0]["id"])
check("and names what a viewer can see without the brief", "people (two people with one face;" in first[0]["question"] and "framing" not in first[0]["question"],
      first[0]["question"])
check("the instructions say to answer it first", "Answer q_anomalies first" in image_spec.review_template(item, DEFAULTS)["_instructions"])
saved_reference = image_spec.REFERENCE_DIR
image_spec.REFERENCE_DIR = saved_reference / "missing"
try:
    bare = image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))[0]["question"]
finally:
    image_spec.REFERENCE_DIR = saved_reference
check(
    "the fresh look is told where the scene is, and nothing else of the brief",
    f"The scene is in {EXAMPLE['location']['locale'].rstrip('.')}." in first[0]["question"]
    and EXAMPLE["purpose"] not in first[0]["question"]
    and "time and place (a garment" in first[0]["question"],
    first[0]["question"][:300],
)
check("without the library it asks with no vocabulary", "Look at" not in bare and bare.startswith("Before reading any other question"))

print("C68 the lite session's fourteen open findings")
# dp-016-lite-open-findings.md; each reproduced before it was fixed.
def _hand_qs(hands):
    spec = copy.deepcopy(EXAMPLE)
    spec["subjects"][0]["hands"] = hands
    return [q["question"] for q in image_spec.build_questions(spec, image_spec.derive(spec, WIDTH, HEIGHT)) if "_hand_" in q["id"] and "count" not in q["id"]]


_group = copy.deepcopy(EXAMPLE)
_group["subjects"][1].update(count=2, pose="side by side with their backs to the camera", hands="the left hand holds a ticket", variation="one older man, one young woman with short hair")
_group_prompt = image_spec.compile_spec(_group, WIDTH, HEIGHT, DEFAULTS)["prompt"]
check("A1 a group with its backs to the camera is plural", "have their backs to the camera" in _group_prompt and " has his back" not in _group_prompt and " has her back" not in _group_prompt)
_a2 = _hand_qs("the left hand rests on her shoulder, his right hand holds the stethoscope to her back")
check("A2 a hand's pronoun is the one before that hand", _a2 and all("his own" in q for q in _a2), str(_a2))
_a3 = _hand_qs("her right hand in her lap, her left hand on the armrest")
check("A3 a verbless hand clause gets its verb", _a3 and all("that is in" in q or "that is on" in q for q in _a3), str(_a3))
check(
    "A4 turned away from something else is not a back to the camera",
    image_spec.facing({"pose": "turned away from the shelves"}) != "away"
    and image_spec.facing({"pose": "head turned away from the glare of the window"}) != "away"
    and image_spec.facing({"pose": "turned away from the camera"}) == "away"
    and image_spec.facing({"pose": "standing, turned away"}) == "away",
)
_cut = copy.deepcopy(EXAMPLE)
_cut["objects"].append({
    "id": "truck", "short_name": "truck", "name": "box delivery truck", "count": 1, "material": "painted steel",
    "state": "parked, engine off", "height_m": 3.0, "width_m": 6.0,
    "scale_anchor": "its cargo box stands well above the pharmacist's head", "support": {"kind": "stands_on", "by": "the road"},
    "position": "far right, beyond the counter, running out of the frame", "distance_m": 3.5, "plane": "background",
})
check("B1 the truck is cut by the frame", image_spec.derive(_cut, WIDTH, HEIGHT)["fits_in_frame"].get("truck") is False)
check(
    "B1 a thing the frame cuts gets no per-cent crossing in the prompt",
    "crosses the truck about" not in image_spec.compile_spec(_cut, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)
_pours = {a: image_spec.pours({"subjects": [{"action": a}]}) for a in (
    "waters the potted basil", "tips the kettle over the cup", "tipping the cart forward to unload",
    "sprinkles salt over the grilled squid",
)}
check("B2 pours() reads watering and a tipped kettle, not a tipped cart or salt",
      _pours == {"waters the potted basil": True, "tips the kettle over the cup": True,
                 "tipping the cart forward to unload": False, "sprinkles salt over the grilled squid": False}, str(_pours))
_names = ("a can of Red Bull", "the Blue Mosque", "a glass of green tea", "a bowl of brown rice", "a pot of red curry")
check("B3 decolour() keeps names and dishes", all(image_spec.decolour(n) == n for n in _names), str([image_spec.decolour(n) for n in _names]))
check("and still takes a plain colour out", image_spec.decolour("a red plastic stool") == "a plastic stool", image_spec.decolour("a red plastic stool"))
_matched = copy.deepcopy(EXAMPLE)
_matched["objects"][1].update(count=4, variation="identical model, one with a cracked corner")
_matched_prompt = image_spec.compile_spec(_matched, WIDTH, HEIGHT, DEFAULTS)["prompt"]
_matched_q = {q["id"]: q["question"] for q in image_spec.build_questions(_matched, image_spec.derive(_matched, WIDTH, HEIGHT))}
check("D1 a matched set keeps the difference it names", "matched set" in _matched_prompt and "one with a cracked corner" in _matched_prompt)
check("and the review asks it", "one with a cracked corner" in _matched_q.get("q_medicine_box_distinct", ""), _matched_q.get("q_medicine_box_distinct", ""))
refuses("D2 people are never a matched set", "never a matched set", lambda s: s["subjects"][1].update(count=2, variation="matched"))
check(
    "D3 a counted arrangement counts its members: one row of 3, not 3 rows",
    image_spec.counted_name(3, "row of parked scooters") == "a row of 3 parked scooters"
    and image_spec.counted_name(2, "pair of moulded tigers") == "a pair of moulded tigers"
    and image_spec.counted_name(3, "row of parked scooters", one=True) == "3 parked scooters, in one row"
    and image_spec.counted_name(3, "row of parked scooters", each=True) == "3 parked scooters",
)
check("and a container is counted itself", image_spec.counted_name(3, "box of mangoes") == "3 boxes of mangoes")
check("A3 a participle hand clause gets its verb", all("that is holding" in q or "that is resting" in q for q in _hand_qs("her left hand holding a coffee cup, her right hand resting on the table")),
      str(_hand_qs("her left hand holding a coffee cup, her right hand resting on the table")))
check("but a count of one in a question keeps its number", image_spec.counted_name(1, "pale wood counter", one=True) == "1 pale wood counter")
_lib = json.loads((ROOT / "reference" / "content-production" / "image-failure-classes.json").read_text(encoding="utf-8"))
check("D4 F-unwanted-text cites the sections that test text", "C9c" not in next(c["regression"] for c in _lib["classes"] if c["id"] == "F-unwanted-text"))
_plat = copy.deepcopy(EXAMPLE)
_plat["subjects"][1].update(posture="seated", pose="seated on a stool")
_plat["subjects"][0]["ground_height_m"] = 0.8
_plat["camera"]["height_m"] = round(image_spec.eye_height(_plat["subjects"][1]) + 0.30, 2)
refuses("D5 a standing person on a platform does not widen the eye-level band for the seated", "eye_level", lambda s: s.update(copy.deepcopy(_plat)))

print("C69 a small thing's width said against what it sits on, behind a switch")
# rangsarn's experiment: the relation, not the metres, and the same number for the check.
_bowls = copy.deepcopy(EXAMPLE)
_bowls["objects"].append({
    "id": "bowls", "short_name": "bowl", "name": "white melamine bowls", "count": 3, "material": "melamine",
    "state": "empty, stacked apart", "height_m": 0.08, "width_m": 0.8,
    "scale_anchor": "each about as wide as the pharmacist's forearm is long",
    "support": {"kind": "rests_on", "by": "counter"}, "position": "on the counter, right of centre",
    "distance_m": 1.9, "plane": "midground", "variation": "one with a chipped rim, one faintly stained",
})
_bowls["objects"][-1]["width_m"] = 0.2
_rel = image_spec.derive(_bowls, WIDTH, HEIGHT)["relative_widths"]
check("derive gives the width ratio against the supporter", _rel == [{"id": "bowls", "supporter": "counter", "ratio": round(0.2 / 2.4, 3), "said_as": 0.1, "words": "a tenth"}], str(_rel))
check("off by default: the prompt says nothing", "as wide as the counter" not in image_spec.compile_spec(_bowls, WIDTH, HEIGHT, DEFAULTS)["prompt"])
_bowls["relative_size_clause"] = True
check("on, the prompt says it as a fraction", "Each bowl is about a tenth as wide as the" in image_spec.compile_spec(_bowls, WIDTH, HEIGHT, DEFAULTS)["prompt"])
refuses("the switch must be true or false", "relative_size_clause must be true or false", lambda s: s.update(relative_size_clause="yes"))

print("C70 seated landmarks for scale anchors; an anchor in a pose its person is not in")
# The sweep session: "the mid-thigh of the surgeon standing" for a seated surgeon (s45).
def _seated_with(anchor, height):
    spec = copy.deepcopy(EXAMPLE)
    spec["subjects"][1].update(posture="seated", pose="seated on a stool, leaning in")
    spec["camera"]["height_m"] = round(
        (image_spec.eye_height(spec["subjects"][0]) + image_spec.eye_height(spec["subjects"][1])) / 2, 2
    )
    spec["objects"].append({
        "id": "side_table", "short_name": "side table", "name": "small round side table", "count": 1,
        "material": "pale wood", "state": "bare", "height_m": height, "width_m": 0.5, "scale_anchor": anchor,
        "support": {"kind": "stands_on", "by": "the tiled floor"}, "position": "right of centre, beside the customer",
        "distance_m": 1.5, "plane": "foreground",
    })
    return spec


_ok = _seated_with("its top is level with the customer's elbow", 0.66)
_ok_errors, _ok_warn = image_spec.validate_spec(_ok, WIDTH, HEIGHT, DEFAULTS)
check("a seated landmark is measured from the seat", not [e for e in _ok_errors if "side_table" in e], str(_ok_errors[:2]))
check("and a wrong height against it is refused", any("side_table" in e and "seated" in e for e in image_spec.validate_spec(_seated_with("its top is level with the customer's elbow", 0.40), WIDTH, HEIGHT, DEFAULTS)[0]))
check("a seated elbow sits about 0.68 m above the floor for a 1.68 m adult", abs(image_spec.landmark_height_m({"height_m": 1.68, "posture": "seated"}, "elbow") - (0.45 + 0.23 * 1.68 / 1.65)) < 1e-9)
_pose = _seated_with("its top sits at about the mid-thigh of the customer standing", 0.71)
_pose_errors, _pose_warn = image_spec.validate_spec(_pose, WIDTH, HEIGHT, DEFAULTS)
check("an anchor in a pose its person is not in is warned", any("side_table" in w and "measures" in w and "standing" in w for w in _pose_warn), str(_pose_warn[-2:]))
check("and left out of the prompt", "mid-thigh of the customer standing" not in image_spec.compile_spec(_pose, WIDTH, HEIGHT, DEFAULTS)["prompt"])
_pose_q = {q["id"]: q["question"] for q in image_spec.build_questions(_pose, image_spec.derive(_pose, WIDTH, HEIGHT))}
check("and out of its scale question", "standing" not in _pose_q.get("q_side_table_scale", "standing"), _pose_q.get("q_side_table_scale", ""))
_both = _seated_with("its top sits at about the mid-thigh of either of them standing", 0.71)
_both["subjects"][0].update(posture="seated", pose="seated behind the counter on a high stool")
_both["camera"]["height_m"] = round(
    (image_spec.eye_height(_both["subjects"][0]) + image_spec.eye_height(_both["subjects"][1])) / 2, 2
)
check(
    "a group reference is about everyone: 'either of them standing' when both sit is warned",
    any("side_table" in w and "everyone in the scene standing" in w for w in image_spec.validate_spec(_both, WIDTH, HEIGHT, DEFAULTS)[1]),
    str([w for w in image_spec.validate_spec(_both, WIDTH, HEIGHT, DEFAULTS)[1] if "side_table" in w]),
)
check("and kept out of the prompt", "either of them standing" not in image_spec.compile_spec(_both, WIDTH, HEIGHT, DEFAULTS)["prompt"])
check("commas do not hide the pose", image_spec.anchor_posture_mismatch("its top meets the customer, standing, at mid-thigh", {"id": "customer", "posture": "seated"}) == "standing")
check("but not when one of them stands", not image_spec.group_posture_mismatch("the mid-thigh of either of them standing", [{"posture": "seated"}, {"posture": "standing"}]))
check("a posture word about a thing is not about a person", not image_spec.anchor_posture_mismatch("about the size of an egg standing on end", None))

print("C71 a style reference, checked as a likeness is")
_styled = copy.deepcopy(EXAMPLE)
_styled["style"]["reference"] = {"path": "brand/ink-style-v2.png", "rights": "client_owned", "origin": "approved channel brand art v2"}
check("a style reference with path, rights and origin is valid", not image_spec.validate_spec(_styled, WIDTH, HEIGHT, DEFAULTS)[0])
check(
    "the prompt takes its style, never its subject (the example sets its own palette)",
    image_spec.STYLE_LOCK_OWN_PALETTE in image_spec.compile_spec(_styled, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)
check("and it is listed with the images the generator is fed", {"role": "style", "path": "brand/ink-style-v2.png", "rights": "client_owned"} in image_spec.conditioning_references(_styled))
refuses("its origin is required", "style.reference.origin is required", lambda s: s["style"].update(reference={"path": "x.png", "rights": "client_owned"}))
refuses("and its rights", "style.reference.rights must be one of", lambda s: s["style"].update(reference={"path": "x.png", "rights": "found online", "origin": "x"}))
check("reference_only warns", any("reference_only" in w for w in image_spec.validate_spec(
    {**copy.deepcopy(EXAMPLE), "style": {**EXAMPLE["style"], "reference": {"path": "x.png", "rights": "reference_only", "origin": "lock sheet v1"}}},
    WIDTH, HEIGHT, DEFAULTS)[1]))
_own = copy.deepcopy(_styled)
_own["style"]["color_palette"] = "one amber wash on cream"
_own_errors, _own_warn = image_spec.validate_spec(_own, WIDTH, HEIGHT, DEFAULTS)
check(
    "a spec with its own palette takes only line, texture and finish from the reference",
    image_spec.STYLE_LOCK_OWN_PALETTE in image_spec.compile_spec(_own, WIDTH, HEIGHT, DEFAULTS)["prompt"]
    and image_spec.STYLE_LOCK not in image_spec.compile_spec(_own, WIDTH, HEIGHT, DEFAULTS)["prompt"],
)
check("and is warned that the image still carries its colours", any("still carries its own colours" in w for w in _own_warn))
_nopal = copy.deepcopy(_styled)
_nopal["style"].pop("color_palette", None)
check("without its own palette, the reference gives the palette too", image_spec.STYLE_LOCK in image_spec.compile_spec(_nopal, WIDTH, HEIGHT, DEFAULTS)["prompt"]
      and not any("still carries" in w for w in image_spec.validate_spec(_nopal, WIDTH, HEIGHT, DEFAULTS)[1]))
_plural = copy.deepcopy(_bowls)
_plural["objects"][-1]["short_name"] = "bowls"
check("a plural short name after Each takes 'of the'", "Each of the bowls is about a tenth as wide as the" in image_spec.compile_spec(_plural, WIDTH, HEIGHT, DEFAULTS)["prompt"])

print("C72 plate contents asked as identity; what each person has, listed")
# rangsarn's anomaly-first test: fried rice "could come from" the dishes, and the
# father's extra spoon went uncounted.
_meal = copy.deepcopy(EXAMPLE)
_meal["objects"].extend([
    {"id": "curry", "short_name": "curry", "name": "bowl of green curry", "count": 1, "material": "glazed stoneware",
     "state": "half full", "height_m": 0.08, "width_m": 0.18, "scale_anchor": "about as wide as the pharmacist's hand is long",
     "support": {"kind": "rests_on", "by": "counter"}, "position": "on the counter, left of centre", "distance_m": 2.0, "plane": "midground"},
    {"id": "plate", "short_name": "plate", "name": "plate of rice", "count": 1, "material": "white melamine",
     "state": "rice with a spoonful of curry beside it", "height_m": 0.03, "width_m": 0.24, "filled_from": ["curry"],
     "scale_anchor": "about as wide as the pharmacist's forearm is long", "support": {"kind": "rests_on", "by": "counter"},
     "position": "on the counter in front of the pharmacist", "distance_m": 2.0, "plane": "midground"},
])
_meal["subjects"][0]["hands"] = "her right hand holds a spoon, her left hand holds a fork"
_meal_q = {q["id"]: q for q in image_spec.build_questions(_meal, image_spec.derive(_meal, WIDTH, HEIGHT))}
check(
    "plate contents are asked as identity, with cooked-together named",
    "one of these, as served from it" in _meal_q["q_plate_contents"]["question"]
    and "cooked together rather than served beside" in _meal_q["q_plate_contents"]["question"]
    and "could come from" not in _meal_q["q_plate_contents"]["question"],
    _meal_q["q_plate_contents"]["question"],
)
_own = _meal_q.get("q_pharmacist_own_things", {})
check("a person with two or more things is asked to list them, hands first", _own.get("question", "").startswith("Hands first, then the place in front of them"), str(_own)[:200])
check("without being told how many", not re.search(r"\b(?:2|3|two|three|exactly)\b", _own.get("question", "")))
check("the expected list goes to the comparison, and fewer is incomplete",
      _own.get("measure", {}).get("expected") == ["spoon", "fork", "box", "plate"] and _own["measure"].get("fewer_listed") == "incomplete",
      str(_own.get("measure")))
check(
    "the expected list holds objects, not body parts, parts or adjectives",
    image_spec.own_held("her right hand holds a long steel ladle in the wok and her left grips the wok handle through a folded cloth") == ["ladle", "wok"]
    and image_spec.own_held("her right hand grips the handpiece with the thumb along its top, her left hand holds the client cheek taut with two fingertips") == ["handpiece"]
    and image_spec.own_held("his right hand holds the model upright, his left hand holds the pen loosely") == ["model", "pen"],
    str(image_spec.own_held("her right hand grips the handpiece with the thumb along its top, her left hand holds the client cheek taut with two fingertips")),
)
_rs = {
    "his right hand holds a spoon with rice near his mouth; his left hand holds a fork resting on his plate": ["spoon", "fork"],
    "her right hand holds her spoon resting on her plate; her left hand holds her fork beside the plate": ["spoon", "fork"],
    "her right hand tosses the vegetables with a steel spatula; her left hand holds the wok's long handle": ["spatula", "wok"],
    "her right hand lifts a ladle of broth from the pot; her left hand holds a bowl": ["ladle", "bowl"],
    "her right hand holds the omelette's large serving spoon over the girl's plate; her left hand rests on her folded knees": ["spoon"],
    "her right hand holds the large serving spoon in the bowl; her left hand steadies her plate": ["spoon", "plate"],
    "his right hand holds a pair of chopsticks over the bowl": ["chopstick"],
    "a spoon in her right hand and a fork in her left": ["spoon", "fork"],
    "her right hand holds a cup of tea, her left a saucer": ["cup", "saucer"],
    "raises a glass of water": ["glass"],
    "her right hand holds a spoonful of rice to the child's mouth": ["spoon"],
    "she holds a bowlful of soup in both hands": ["bowl"],
    "her right hand holds out a bunch of bananas by its stem toward the buyer; her left hand rests on the boat's gunwale": ["banana"],
}
_rs_got = {k: image_spec.own_held(k) for k in _rs}
check("rangsarn's hand texts give the things in the hands", all(_rs_got[k] == v for k, v in _rs.items()),
      str({k[:40]: v for k, v in _rs_got.items() if v != _rs[k]}))
_place = copy.deepcopy(_meal)
_place["objects"][-1].update(position="one at the table edge in front of each family member")
check("a place set in front of each person is everyone's", "plate" in image_spec.own_things(_place, _place["subjects"][1]))
_left = copy.deepcopy(_meal)
_left["objects"][-1].update(position="on the counter at the pharmacist's left")
_counter = copy.deepcopy(EXAMPLE)
_counter["objects"][0]["position"] = "across the lower third, in front of the pharmacist"
check("furniture in front of a person is not their place: it stands, a setting rests", "counter" not in image_spec.own_things(_counter, _counter["subjects"][0]))
check("'at her left' says where, not whose", "plate" not in image_spec.own_things(_left, _left["subjects"][0]))
check("one thing held is not listed", "q_pharmacist_own_things" not in {q["id"] for q in image_spec.build_questions(EXAMPLE, image_spec.derive(EXAMPLE, WIDTH, HEIGHT))})

print("C73 a thing placed in the reserved negative space is warned")
# The sweep session's minimal run (sustainmap-rooftop-visible).
check("a reserved region is read from the negative space's opening phrase", image_spec.frame_region("the upper left quarter") == {"v": "top", "h": "left"})
check("'right of centre' is not the right edge", "h" not in image_spec.frame_region("right of centre, behind the counter"))
_ns = copy.deepcopy(EXAMPLE)
_ns["composition"]["negative_space"] = "the upper left quarter, where the plain wall reads as an even field"
_ns["objects"][2]["position"] = "overhangs the top left corner, close and soft"
check("a thing in the reserved region is warned", any("shelving" in w and "negative_space" in w for w in image_spec.validate_spec(_ns, WIDTH, HEIGHT, DEFAULTS)[1]))
_ns["objects"][2]["position"] = "across the upper left of the counter"
_ns["objects"][0]["position"] = "centre of the frame, running across it"
check(
    "a part of a centred thing is placed by its offset (the sweep session: papayiw's pen)",
    any("shelving" in w and "negative_space" in w for w in image_spec.validate_spec(_ns, WIDTH, HEIGHT, DEFAULTS)[1]),
)
_ns["objects"][0]["position"] = "lower right of the frame"
check(
    "and a part of a placed thing is where that thing is",
    not [w for w in image_spec.validate_spec(_ns, WIDTH, HEIGHT, DEFAULTS)[1] if "negative_space" in w and "shelving" in w],
)
_ns["objects"][2]["position"] = "across the upper left background"
_ns["composition"]["negative_space"] = "the upper left quarter, where the plain wall above the shelving reads as an even field"
check(
    "a thing the quiet field is written around is warned, more softly (the sweep session: drivehub's canopy)",
    any("shelving" in w and "described around it" in w for w in image_spec.validate_spec(_ns, WIDTH, HEIGHT, DEFAULTS)[1]),
)
_ns["objects"][2]["position"] = "upper right background beyond the counter"
check("one elsewhere is not", not [w for w in image_spec.validate_spec(_ns, WIDTH, HEIGHT, DEFAULTS)[1] if "negative_space" in w and "shelving" in w])

print("C74 the registry decides where exclusions go, unless a target is given")
# Found answering the owner on hosts: the shipped prompt_target overrode the
# registry, so a gpt-image client lost its exclusions to negative_prompt.
check("the shipped default leaves the target to the registry", image_spec.policy_from_config(DEFAULTS)["spec"].get("prompt_target") == "")
_gpt = copy.deepcopy(DEFAULTS)
_gpt["images"]["spec"]["target_model"] = "openai-gpt-image"
check("a gpt-image client compiles its exclusions inline", image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, _gpt, "")["target"] == "inline_constraints")
_gem = copy.deepcopy(DEFAULTS)
_gem["images"]["spec"]["target_model"] = "gemini-image"
check("a Gemini client describes the positive state only", image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, _gem, "")["target"] == "none")
check("with neither set, the fallback is inline (owner decision)", image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS, "")["target"] == "inline_constraints")
_saved_registry = image_spec.MODEL_REGISTRY_PATH
image_spec.MODEL_REGISTRY_PATH = _saved_registry.with_name("missing-registry.json")
try:
    image_spec.target_model_policy(_gpt)
    _registry_error = ""
except ValueError as exc:
    _registry_error = str(exc)
finally:
    image_spec.MODEL_REGISTRY_PATH = _saved_registry
check("a registry that cannot be read is named as the cause, not the model", "could not be read" in _registry_error and "is not in" not in _registry_error, _registry_error)
check("an explicit target still wins", image_spec.compile_spec(EXAMPLE, WIDTH, HEIGHT, _gpt, "none")["target"] == "none")

print("C75 a hanging thing's height is its vertical size")
# The sweep session's clean scoring: hanging pairs 3 true, 1 false, 0 unmeasurable.
check("a hanging projector is ratio-ready", image_spec.ratio_ready({"support": {"kind": "hangs_from", "by": "the ceiling"}, "height_m": 0.3, "width_m": 0.4}, False))
check("a wide platform people stand on is not", not image_spec.ratio_ready({"support": {"kind": "stands_on", "by": "the hall floor"}, "height_m": 1.1, "width_m": 6.1}, False))
check("nor a row of desks", not image_spec.ratio_ready({"support": {"kind": "stands_on", "by": "the floor"}, "height_m": 0.75, "width_m": 1.2, "count": 6}, False))

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
