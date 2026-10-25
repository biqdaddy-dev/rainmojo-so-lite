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
    "near standing eye height",
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
    "near standing eye height",
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
    "shot size, horizon and scale ratios are measured, not judged",
    routes.get("q_camera_shot") == "geometry"
    and routes.get("q_horizon") == "geometry"
    and routes.get("q_horizon_cut_pharmacist") == "geometry",
    str(routes),
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

print("C15 a thin client config still has a gate")
thin = {"images": {"plausibility": {"required": True, "checks": []}}}
check(
    "an empty checks list falls back to the shipped rubric",
    len(image_spec.rubric(thin)) == len(image_spec.rubric(DEFAULTS)),
    str(len(image_spec.rubric(thin))),
)

print("C22 scale_anchor is a claim about two numbers, so it is checked")
check(
    "a landmark fraction is read off the stature",
    abs(image_spec.BODY_LANDMARK_FRACTION["hip"] * 1.62 - 0.8586) < 0.002,
    str(image_spec.BODY_LANDMARK_FRACTION["hip"] * 1.62),
)
check(
    "an anchor that brackets between two landmarks intersects their bands",
    (
        lambda window: abs(window[0] - 0.8586) < 0.01 and abs(window[1] - 0.972) < 0.01
    )(
        image_spec.landmark_window(
            image_spec.landmark_bands(
                "its top meets the pharmacist just above the hip, a little below her waist",
                1.62,
            )
        )
    ),
    str(
        image_spec.landmark_window(
            image_spec.landmark_bands(
                "its top meets the pharmacist just above the hip, a little below her waist",
                1.62,
            )
        )
    ),
)
refuses(
    "a counter at knee height anchored above the hip",
    "contradicts its scale_anchor",
    lambda spec: spec["objects"][0].update({"height_m": 0.42}),
)
refuses(
    "the same counter when the person grows to 2.25 m",
    "contradicts its scale_anchor",
    lambda spec: spec["subjects"][0].update({"height_m": 2.25}),
)
check(
    "an anchor naming no landmark is left alone",
    not image_spec.landmark_bands("about a third taller than she is", 1.62),
    "a stature comparison was read as a landmark",
)
check(
    "with several people and no name in the anchor, nothing is guessed",
    image_spec.anchor_person(
        "its top is at waist height", [{"id": "a", "height_m": 1.6}, {"id": "b", "height_m": 1.8}]
    )
    is None,
    "a referent was guessed from an anchor that names nobody",
)

print("C23 a held object is checked against the holder")
refuses(
    "a carton the size of a torso cannot fill a hand",
    "cannot be held the way the brief describes",
    lambda spec: spec["objects"][1].update(
        {"height_m": 1.4, "scale_anchor": "it sits in the pharmacist's palm"}
    ),
)
check(
    "a two-handed load is a warning, not a refusal, because it is possible",
    (
        lambda result: not any("cannot be held" in error for error in result[0])
        and any("two-handed load" in warning for warning in result[1])
    )(
        (
            lambda spec: image_spec.validate_spec(spec, WIDTH, HEIGHT, DEFAULTS)
        )(
            {
                **copy.deepcopy(EXAMPLE),
                "objects": [
                    {
                        **copy.deepcopy(EXAMPLE["objects"][1]),
                        "height_m": 1.2,
                        "width_m": 0.4,
                        "scale_anchor": "it reaches from her knee to her shoulder",
                    }
                ],
            }
        )
    ),
    "a 1.2 m held object against a 1.62 m holder was not reported as two-handed",
)

print("C24 support must be something that holds weight, and a holder must be a person")
refuses(
    "held_by must name a person, not another object",
    "must be a subject id",
    lambda spec: spec["objects"][1].update(
        {"support": {"kind": "held_by", "by": "counter"}}
    ),
)
refuses(
    "a support that hovers holds nothing up",
    "holds nothing up",
    lambda spec: spec["objects"][1].update(
        {"support": {"kind": "stands_on", "by": "a hovering glass shelf"}}
    ),
)
check(
    "floats_in is still allowed to float",
    not any(
        "holds nothing up" in error
        for error in errors_for(
            lambda spec: spec["objects"][1].update(
                {"support": {"kind": "floats_in", "by": "the floating tray of water"}}
            )
        )
    ),
    "floats_in was refused for floating",
)

print("C25 a seated figure has an eye line too")
seated_spec = copy.deepcopy(EXAMPLE)
for person in seated_spec["subjects"]:
    person["posture"] = "sitting"
    person["pose"] = "seated at the consultation desk, both feet on the floor"
seated_spec["camera"]["height_m"] = 1.23
seated_derived = image_spec.derive(seated_spec, WIDTH, HEIGHT)
check(
    "standing_people does not claim them",
    not image_spec.standing_people(seated_spec) and len(image_spec.seated_people(seated_spec)) == 2,
    str(len(image_spec.seated_people(seated_spec))),
)
check(
    "every seated person still gets an eye line",
    {offset["id"] for offset in seated_derived["eye_line_offsets"]} == {"pharmacist", "customer"},
    str(seated_derived["eye_line_offsets"]),
)
check(
    "a lens at the seated eye height crosses the eyes",
    all(
        offset["relation"] == "at_eyes" for offset in seated_derived["eye_line_offsets"]
    ),
    str(seated_derived["eye_line_offsets"]),
)
check(
    "the offset is stated in head heights, which a reviewer can count on the image",
    all(
        offset["offset_head_heights"] is not None
        for offset in seated_derived["eye_line_offsets"]
    ),
    str(seated_derived["eye_line_offsets"]),
)
seated_questions = image_spec.build_questions(seated_spec, seated_derived)
check(
    "and it is asked as a measured question",
    [
        question
        for question in seated_questions
        if question["id"].startswith("q_eye_line_")
        and question.get("verify_with") == "geometry"
    ],
    "no measured eye-line question for a seated scene",
)
check(
    "the eye_level band tightens to one head height when nobody is standing",
    any(
        "with nobody standing" in error
        for error in image_spec.validate_spec(
            {**seated_spec, "camera": {**seated_spec["camera"], "height_m": 1.52}},
            WIDTH,
            HEIGHT,
            DEFAULTS,
        )[0]
    ),
    "a 1.52 m lens over a 1.23 m seated eye line passed as eye level",
)
check(
    "a mixed scene keeps the standing tolerance, because a seated eye line may sit lower",
    not any(
        "with nobody standing" in error
        for error in image_spec.validate_spec(
            {
                **copy.deepcopy(EXAMPLE),
                "subjects": [
                    copy.deepcopy(EXAMPLE["subjects"][0]),
                    {
                        **copy.deepcopy(EXAMPLE["subjects"][1]),
                        "posture": "sitting",
                        "pose": "seated on the waiting bench, both feet on the floor",
                    },
                ],
            },
            WIDTH,
            HEIGHT,
            DEFAULTS,
        )[0]
    ),
    "the seated-only rule fired on a scene that has someone standing",
)

print("C26 the focus subject of a whole-subject shot has to fit the frame")
refuses(
    "a full shot cannot show a 6 m counter from 5 m",
    "does not fit the 3.60 m frame width",
    lambda spec: (
        spec["camera"].update(
            {"shot_type": "full", "focus_on": "counter", "subject_distance_m": 5.0}
        ),
        spec["subjects"][0].update({"distance_m": 5.0}),
        spec["subjects"][1].update({"distance_m": 4.6}),
        spec["objects"][0].update({"distance_m": 5.0, "width_m": 6.0}),
    ),
)
check(
    "an object wider than the frame is legal when it is not the subject",
    not any(
        "does not fit" in error
        for error in errors_for(lambda spec: spec["objects"][0].update({"width_m": 6.0}))
    ),
    "a background object running out of frame was refused",
)

print("C27 how close the lens is to a face, which the focal length does not fix")
warnings_at = lambda mutate: image_spec.validate_spec(  # noqa: E731
    (lambda spec: (mutate(spec), spec)[1])(copy.deepcopy(EXAMPLE)), WIDTH, HEIGHT, DEFAULTS
)[1]
check(
    "under a metre from a face is reported whatever the lens",
    any(
        "from a face" in warning
        for warning in warnings_at(
            lambda spec: (
                spec["camera"].update(
                    {"focal_length_mm": 20, "subject_distance_m": 0.55, "shot_type": "close_up"}
                ),
                spec["subjects"][0].update({"distance_m": 0.55}),
            )
        )
    ),
    "a 0.55 m lens-to-face distance passed without a word",
)
check(
    "the shipped example, at 2.2 m, says nothing",
    not any("from a face" in warning for warning in warnings_at(lambda spec: None)),
    "the example picked up a face-distance warning",
)

print("C28 shadow hardness against the sky, and a fill that is really a second key")
refuses(
    "a clouded sky cannot cast a crisp shadow",
    "cannot cast a crisp shadow",
    lambda spec: (
        spec["location"].update({"weather": "heavy overcast, rain on the pavement"}),
        spec["lighting"]["key"].update(
            {
                "source": "direct sunlight through the shopfront",
                "quality": "hard, a small bright source with crisp edged shadows",
            }
        ),
    ),
)
check(
    "the example's overcast window stays legal, because its key is soft",
    not any(
        "crisp shadow" in error
        for error in image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)[0]
    ),
    "the example's own overcast daylight was refused",
)
refuses(
    "a fill with the key's power and hardness is a second key",
    "makes it a second key",
    lambda spec: spec["lighting"].update(
        {"fill": ["a second hard spotlight from the right at the same power"]}
    ),
)
check(
    "the example's own fills are not read as second keys",
    not any(
        "second key" in error
        for error in image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)[0]
    ),
    "a legitimate fill was refused",
)

print("C29 the object load limit counts items, not entries")
check(
    "one entry declaring forty cartons is reported",
    any(
        "across" in warning and "entries" in warning
        for warning in image_spec.validate_spec(
            (
                lambda spec: (spec["objects"][1].update({"count": 40}), spec)[1]
            )(copy.deepcopy(EXAMPLE)),
            WIDTH,
            HEIGHT,
            DEFAULTS,
        )[1]
    ),
    "forty objects in one entry passed a limit of eight",
)
check(
    "the example's own object list is quiet",
    not any(
        "entries" in warning
        for warning in image_spec.validate_spec(EXAMPLE, WIDTH, HEIGHT, DEFAULTS)[1]
    ),
    "the example picked up a load warning",
)

if failures:
    print(f"RESULT: {len(failures)} failures")
    raise SystemExit(1)
print("IMAGE_SPEC_CONTRACT_TEST_OK")
