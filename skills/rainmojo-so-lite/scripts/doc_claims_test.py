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

print("D3 the hand-held fractions the docs quote")
check("the docs say three tenths warns", said("above three tenths of that height it is a warning"))
check("and six tenths refuses", said("above six tenths it is refused"))
check(
    "and the code uses 0.30 and 0.60",
    (image_spec.ONE_HAND_FRACTION, image_spec.TWO_HAND_FRACTION) == (0.30, 0.60),
    str((image_spec.ONE_HAND_FRACTION, image_spec.TWO_HAND_FRACTION)),
)
check(
    "the docs say it is measured against the tallest person in the frame",
    said("compared with the tallest person in the frame"),
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


seated_eye = image_spec.EYE_ABSOLUTE_M["sitting"]
inside = [e for e in errors_for(seated(seated_eye + 0.14)) if "eye_level" in e or "eye level" in e]
outside = [e for e in errors_for(seated(seated_eye + 0.16)) if "eye_level" in e or "eye level" in e]
check("a lens 0.14 m above a seated eye line is still eye level", not inside, str(inside))
check("a lens 0.16 m above it is not", bool(outside), "0.16 m above a seated eye line passed")

print("D5 the face-distance floors the docs quote")
floors = image_spec.MIN_FACE_DISTANCE_M
quoted = {20: "1.2 m on 20 mm", 28: "1.0 m on 28 mm", 35: "0.9 m on 35 mm", 50: "0.7 m on 50 mm", 85: "0.6 m on 85 mm"}
check(
    "the docs quote exactly the lenses the code has",
    sorted(floors) == sorted(quoted),
    f"code {sorted(floors)} against docs {sorted(quoted)}",
)
for lens, phrase in quoted.items():
    in_docs = said(phrase)
    matches = abs(floors.get(lens, -1) - float(phrase.split()[0])) < 1e-9
    check(
        f"{phrase} matches the code",
        in_docs and matches,
        (
            f"the docs no longer contain {phrase!r}"
            if not in_docs
            else f"docs say {phrase!r}, but the code's floor for {lens} mm is {floors.get(lens)} m"
        ),
    )

print("D6 the claims this edition once made and the code does not honour stay gone")
for stale in (
    "both bands are read and intersected",
    "Bracket between two landmarks",
    "eye_level band is one head height",
    "whatever the focal length",
):
    check(f"the docs no longer say {stale!r}", not said(stale))

if failures:
    print(f"RESULT: {len(failures)} failures")
    raise SystemExit(1)
print("DOC_CLAIMS_TEST_OK")
