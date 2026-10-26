#!/usr/bin/env python3
"""Every number the lite docs quote about the image spec, checked against the code.

The lite edition carries two files of its own about the image spec: the
content-production-lite SKILL.md and its agent.json. Nothing upstream overwrites
them, so when the module changes underneath, they go stale and nothing says so.
That happened: from 2.6.0 on, both described a design this edition had replaced,
anchors read by intersecting two bands and a seated eye-level band of one head
height, while the code took the first landmark named and used 0.15 m. Ported
files were checked byte for byte; the prose about them was checked by nothing.

So each claim here pairs the sentence the docs actually contain with the fact in
image_spec.py it describes. A claim fails when the code moves, and also when the
sentence is edited away, so the pairing cannot drift in either direction.

Every claim is pinned to a constant or to a behaviour, never to its own presence
alone. A presence check proves a sentence was not deleted and says nothing about
whether it is true. The first version of this file checked "compared with the
tallest person in the frame" only for presence, and when the full edition moved
the hand-held rule to measure against the holder, the sentence became false and
this file stayed green. The same was true of the 0.35 m standing band. Both are
now tested by behaviour: a scene is built where the doc's claim and the opposite
claim give different answers, and the code has to give the doc's.

Scope. Pinning every claim IN this file is not the same as pinning every claim IN
the docs, and for a while only the numbers were here: the qualitative rules about
what the anchor check leaves alone, and the lighting rule, were true when written,
checked by hand once, and then pinned by nothing. D7 and D8 cover them. The aim is
every behavioural sentence the two lite files say about the image spec; a new
sentence there wants a check here in the same commit.

A check that something PASSES can pass for the wrong reason, because the scene may
be fine whatever the exemption. So each "is left alone" claim has a twin that
differs only in the exempting feature and must be refused; if the twin passes too,
the claim's check proved nothing.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import image_spec

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT.parent
SKILL_MD = (SKILLS / "content-production-lite" / "SKILL.md").read_text(encoding="utf-8")
AGENT = json.loads(
    (SKILLS / "content-production-lite" / "agent.json").read_text(encoding="utf-8")
)
RULES = " ".join(AGENT["configuration"]["image_spec"]["binding_rules"])
DOCS = SKILL_MD + " " + RULES
CONFIG = json.loads(
    (ROOT / "reference" / "content-production" / "defaults.json").read_text(encoding="utf-8")
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


def said(phrase: str) -> bool:
    """The docs still contain this claim, collapsing the line wraps in SKILL.md."""
    return phrase in " ".join(DOCS.split())


def errors_for(mutate) -> list[str]:
    spec = copy.deepcopy(EXAMPLE)
    mutate(spec)
    return image_spec.validate_spec(spec, WIDTH, HEIGHT, CONFIG)[0]


print("D1 the scale-anchor tolerance the docs quote")
check(
    "the docs say 12 cm either way",
    said("within 12 cm either way"),
    "the sentence is gone from SKILL.md and agent.json",
)
check(
    "and the code uses 0.12 m",
    image_spec.LANDMARK_TOLERANCE_M == 0.12,
    str(image_spec.LANDMARK_TOLERANCE_M),
)

print("D2 only the first landmark an anchor names is checked")
check(
    "the docs say the first landmark is the one checked",
    said("Only the first landmark the anchor names is checked"),
)
# A counter at the WAIST of a 1.62 m person, 0.97 m. Named hip-first, the hip
# (0.86 m) is the claim and 0.97 m is within 12 cm of it; named waist-first, the
# waist is the claim. Both pass, so the order shows only in the message. Instead
# put the counter at the waist and name a landmark it misses first.
miss_first = errors_for(
    lambda s: s["objects"][0].update(
        {
            "height_m": 0.97,
            "scale_anchor": "its top meets the pharmacist at the knee, and at her waist",
        }
    )
)
check(
    "naming the knee first checks the knee, though the waist is also named and true",
    any("knee" in e for e in miss_first),
    f"expected a knee refusal, got {miss_first}",
)

print("D3 the hand-held fractions the docs quote, and whom they are measured against")
check("the docs say three tenths warns", said("above three tenths of that height it is a warning"))
check("and six tenths refuses", said("above six tenths it is refused"))
check(
    "and the code uses 0.30 and 0.60",
    (image_spec.ONE_HAND_FRACTION, image_spec.TWO_HAND_FRACTION) == (0.30, 0.60),
    str((image_spec.ONE_HAND_FRACTION, image_spec.TWO_HAND_FRACTION)),
)
check(
    "the docs say it is measured against the person holding it",
    said("compared with the person holding it"),
)


def holder_scene(spec):
    # The holder is a 1.02 m child and an adult of 1.68 m is also in frame. A
    # 0.70 m object is 0.69 of the child, past six tenths, and 0.42 of the
    # adult, under it. Measured against the holder it is refused; measured
    # against the tallest it would only warn. So this scene can tell the two
    # claims apart, which a presence check never could.
    spec["subjects"][0].update(
        {"height_m": 1.02, "description": "a child of about four", "appearance": "about four years old"}
    )
    spec["subjects"][1]["height_m"] = 1.68
    spec["objects"][1].update({"height_m": 0.70, "scale_anchor": "it sits in her palm"})


refused_by_holder = [e for e in errors_for(holder_scene) if "two-handed load" in e]
check(
    "and the code measures against the holder, not the tallest person in frame",
    bool(refused_by_holder),
    "a 0.70 m object in a 1.02 m child's palm was not refused, so the code is "
    "measuring against someone taller than the holder",
)

print("D4 the eye-level bands the docs quote")
check(
    "the docs say 0.15 m seated and 0.35 m standing",
    said("the eye_level band is 0.15 m, not the 0.35 m standing spread"),
)


def seated(lens_height: float):
    def mutate(spec):
        for person in spec["subjects"]:
            person["posture"] = "sitting"
            person["pose"] = "seated at the consultation desk, both feet on the floor"
        spec["camera"]["height_m"] = lens_height
    return mutate


def eye_level_errors(mutate):
    return [e for e in errors_for(mutate) if "eye_level" in e or "eye level" in e]


# Measured from the seated people's own mean eye height, not the 1.23 m constant:
# since 015d13b a seated eye height scales with stature, and the constant held
# only because the example's two statures happen to average the 1.65 m adult.
seated_scene = copy.deepcopy(EXAMPLE)
seated(0.0)(seated_scene)
seated_eyes = [image_spec.eye_height(s) for s in seated_scene["subjects"]]
seated_eye = sum(seated_eyes) / len(seated_eyes)
inside = eye_level_errors(seated(seated_eye + 0.14))
outside = eye_level_errors(seated(seated_eye + 0.16))
check("a lens 0.14 m above a seated eye line is still eye level", not inside, str(inside))
check("a lens 0.16 m above it is not", bool(outside), "0.16 m above a seated eye line passed")

# The standing band was quoted but only checked for presence. Pin it the same
# way: everyone standing, the lens 0.34 m and then 0.36 m from their mean eye.
standing_eyes = [image_spec.eye_height(s) for s in EXAMPLE["subjects"]]
mean_standing_eye = sum(standing_eyes) / len(standing_eyes)


def lens_at(height_m):
    def mutate(spec):
        spec["camera"]["height_m"] = height_m
    return mutate


check(
    "a lens 0.34 m from the standing eye line is still eye level",
    not eye_level_errors(lens_at(mean_standing_eye + 0.34)),
    "0.34 m from the standing eye line was refused",
)
check(
    "a lens 0.36 m from it is not",
    bool(eye_level_errors(lens_at(mean_standing_eye + 0.36))),
    "0.36 m from the standing eye line passed",
)

print("D5 the face-distance floors the docs quote")
check(
    "the docs say 0.9 m on any lens",
    said("closer than 0.9 m on any lens"),
)
check(
    "and the code's perspective floor is 0.9 m",
    image_spec.FACE_PERSPECTIVE_FLOOR_M == 0.9,
    str(image_spec.FACE_PERSPECTIVE_FLOOR_M),
)
check(
    "the docs give the two wide lenses more room",
    said("1.2 m up to 20 mm and 1.0 m up to 28 mm"),
)


def face_errors(focal_mm, distance_m):
    def mutate(spec):
        spec["camera"].update({"focal_length_mm": focal_mm, "subject_distance_m": distance_m})
        spec["subjects"][0]["distance_m"] = distance_m
        spec["subjects"][1]["distance_m"] = distance_m
    return [e for e in errors_for(mutate) if "nose" in e]


# Each floor pinned by behaviour on both sides of it, including above 85 mm,
# where the table has no row and the perspective floor alone decides.
for focal_mm, floor_m in ((20, 1.2), (28, 1.0), (50, 0.9), (135, 0.9)):
    check(
        f"{focal_mm} mm refuses a face at {floor_m - 0.05:.2f} m",
        bool(face_errors(focal_mm, floor_m - 0.05)),
        f"a face {floor_m - 0.05:.2f} m from a {focal_mm} mm lens passed",
    )
    check(
        f"{focal_mm} mm accepts a face at {floor_m + 0.05:.2f} m",
        not face_errors(focal_mm, floor_m + 0.05),
        f"a face {floor_m + 0.05:.2f} m from a {focal_mm} mm lens was refused",
    )

print("D7 what the scale-anchor check leaves alone, each in a scene that would be refused if it were checked")
# Every claim below was true when it was written and was checked by hand once,
# then pinned by nothing, which is the state the hand-held claim was in when it
# went false. Each scene is built so the claim and its opposite disagree: the
# object is wrong for the landmark it names, so a check that ran would refuse it.


def anchor_errors(mutate):
    return [e for e in errors_for(mutate) if "scale_anchor" in e]


check(
    "the docs give the 0.42 m counter at the hip as refused",
    said('a 0.42 m counter "at the hip" is refused'),
)
check(
    "and the code refuses it",
    bool(anchor_errors(lambda s: s["objects"][0].update(
        {"height_m": 0.42, "scale_anchor": "its top meets the pharmacist at the hip"}
    ))),
    "a 0.42 m counter at a 1.62 m person's hip passed",
)

check("the docs say above or below is not part of the check", said('"above" or "below" is not part of the check'))
# 0.80 m is below a 1.62 m person's 0.86 m hip but inside 12 cm of it. Read as a
# hedge, "just above the hip" would refuse a counter that sits below the hip;
# read as a symmetric band, it passes.
check(
    "and a counter just below the hip passes though the anchor says just above it",
    not anchor_errors(lambda s: s["objects"][0].update(
        {"height_m": 0.80, "scale_anchor": "its top meets the pharmacist just above the hip"}
    )),
    "the anchor's 'above' was read as part of the check",
)

check("the docs say no check runs without a named person", said("Name the person when more than one is in frame, or no check runs"))
check(
    "and with two people and none named, a counter at knee height passes",
    not anchor_errors(lambda s: s["objects"][0].update(
        {"height_m": 0.42, "scale_anchor": "its top is at hip height"}
    )),
    "an anchor naming nobody was checked against someone",
)

check("the docs say an anchor about width is left alone", said('"as wide as her shoulders", is left alone'))
check(
    "and a width anchor that would miss the shoulder height passes",
    not anchor_errors(lambda s: s["objects"][0].update(
        {"height_m": 0.95, "scale_anchor": "it is as wide as the pharmacist's shoulders"}
    )),
    "an anchor about width was read as a claim about height",
)

check("the docs say a hanging or mounted object is left alone", said("anything that hangs or is mounted"))
check(
    "and a mounted object that would miss the shoulder height passes",
    not anchor_errors(lambda s: s["objects"][0].update(
        {
            "height_m": 0.95,
            "scale_anchor": "its top is at the pharmacist's shoulder",
            "support": {"kind": "mounted_on", "by": "the back wall"},
        }
    )),
    "a mounted object's own length was compared with a height above the floor",
)

# A check that something PASSES can pass for the wrong reason: the scene might be
# fine whatever the exemption. So each exemption above has a twin that differs
# only in the exempting feature and must be refused. If a twin passes, the
# exemption check beside it was vacuous and proved nothing.
check(
    "twin: 0.70 m 'just above the hip' is refused, so the band is real and 0.80 m passed inside it",
    bool(anchor_errors(lambda s: s["objects"][0].update(
        {"height_m": 0.70, "scale_anchor": "its top meets the pharmacist just above the hip"}
    ))),
    "0.70 m passed too, so the 0.80 m check above proved nothing about the band",
)
check(
    "twin: the same counter at knee height, with the pharmacist named, is refused",
    bool(anchor_errors(lambda s: s["objects"][0].update(
        {"height_m": 0.42, "scale_anchor": "its top is at the pharmacist's hip height"}
    ))),
    "naming the person did not trigger the check, so the unnamed case proved nothing",
)
check(
    "twin: the same height phrased as a height, not a width, is refused",
    bool(anchor_errors(lambda s: s["objects"][0].update(
        {"height_m": 0.95, "scale_anchor": "its top is at the pharmacist's shoulders"}
    ))),
    "the height phrasing was not refused either, so the width case proved nothing",
)
check(
    "twin: the same object standing on the floor is refused",
    bool(anchor_errors(lambda s: s["objects"][0].update(
        {
            "height_m": 0.95,
            "scale_anchor": "its top is at the pharmacist's shoulder",
            "support": {"kind": "stands_on", "by": "the shop floor"},
        }
    ))),
    "the floor-standing twin passed too, so the mounted case proved nothing",
)

print("D8 the lighting rule, by behaviour")
check("the docs say a clouded sky cannot cast a crisp shadow", said("a clouded sky covers the sun"))


def light_errors(mutate):
    return [e for e in errors_for(mutate) if "lighting" in e]


check(
    "and the code refuses a hard key under an overcast sky",
    bool(light_errors(lambda s: (
        s["location"].update({"weather": "heavy overcast"}),
        s["lighting"]["key"].update({"source": "direct sun", "quality": "hard, crisp edged shadows"}),
    ))),
    "a hard key under heavy overcast passed",
)
check("the docs say a fill as hard and strong as the key is a second key", said("a fill with the key's power and hardness is a second key"))
check(
    "and the code refuses a hard fill",
    bool(light_errors(lambda s: s["lighting"].update(
        {"fill": ["a second hard spotlight at the same power"]}
    ))),
    "a hard fill at the key's power passed",
)
check(
    "while a soft weaker fill passes",
    not light_errors(lambda s: s["lighting"].update(
        {"fill": ["a soft white bounce about two stops under the key"]}
    )),
    "a soft, weaker fill was refused",
)

print("D9 a seated figure still has an eye line, which only the band used to pin")
# agent.json says a seated or kneeling figure "still has an eye line, and in an
# interview or desk scene it is the only one". D4 pins the 0.15 m band that
# sentence ends with, not the eye line it opens with. When the full edition
# narrowed q_eye_line to standing people on the camera's floor, that clause was
# true but checked by nothing. Here it is checked: in a scene with nobody
# standing, every seated person gets a horizon crossing and a measured question.
check(
    "the docs say a seated figure still has an eye line",
    said("A seated or kneeling figure still has an eye line"),
)
interview = copy.deepcopy(EXAMPLE)
for person in interview["subjects"]:
    person["posture"] = "sitting"
    person["pose"] = "seated at the consultation desk, both feet on the floor"
interview["camera"]["height_m"] = image_spec.EYE_ABSOLUTE_M["sitting"]
compiled = image_spec.compile_spec(interview, WIDTH, HEIGHT, CONFIG, "none")
seated_ids = {p["id"] for p in interview["subjects"]}
crossed = {c["id"] for c in compiled["derived"].get("horizon_crossings", [])}
measured = {
    q["id"].removeprefix("q_horizon_cut_")
    for q in compiled["questions"]
    if q["id"].startswith("q_horizon_cut_") and q.get("verify_with") == "geometry"
}
check(
    "and with nobody standing, every seated person gets a horizon crossing",
    seated_ids <= crossed,
    f"seated {sorted(seated_ids)}, crossings for {sorted(crossed)}",
)
check(
    "and a measured question about where it crosses them",
    seated_ids <= measured,
    f"seated {sorted(seated_ids)}, measured crossing questions for {sorted(measured)}",
)

print("D10 a thing placed in the reserved quiet area is warned, a relative position is not")
# SKILL.md says the compiler warns when a position opens in the part of the frame
# composition.negative_space reserves, and that a position relative to another
# thing is not warned. The shipped example reserves the upper right quarter.
check(
    "the docs say the compiler warns on a position in the quiet area",
    said("the compiler warns when a `position` opens in that part of the frame"),
)
check(
    "and that a position relative to another thing is not warned",
    said('A position relative to another thing ("the lower right of the notebook") is not warned'),
)


def quiet_area_warnings(position: str) -> list[str]:
    spec = copy.deepcopy(EXAMPLE)
    spec["subjects"][1]["position"] = position
    warnings = image_spec.validate_spec(spec, WIDTH, HEIGHT, CONFIG)[1]
    return [w for w in warnings if "negative_space" in w and "customer" in w]


placed = quiet_area_warnings("upper right of the frame, nearer the camera")
check("a person whose position opens in the reserved upper right is warned", bool(placed), "no warning")
relative = quiet_area_warnings("the upper right of the counter, nearer the camera")
check("one at the upper right of another thing is not", not relative, str(relative)[:160])
elsewhere = quiet_area_warnings("lower left of the frame, nearer the camera")
check("nor one in another part of the frame", not elsewhere, str(elsewhere)[:160])

print("D6 the claims this edition once made and the code does not honour stay gone")
for stale in (
    "both bands are read and intersected",
    "Bracket between two landmarks",
    "eye_level band is one head height",
    "whatever the focal length",
    # true until the full edition's 569a7ae, which moved both rules
    "compared with the tallest person in the frame",
    "0.7 m on 50 mm",
    "0.6 m on 85 mm",
):
    check(f"the docs no longer say {stale!r}", not said(stale))

if failures:
    print(f"RESULT: {len(failures)} failures")
    raise SystemExit(1)
print("DOC_CLAIMS_TEST_OK")
