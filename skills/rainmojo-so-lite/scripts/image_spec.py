#!/usr/bin/env python3
"""Structured image specs: validate, derive geometry, compile prompts, and gate reviews.

An image manifest item may carry a ``spec`` object describing the picture the way a
photographer's shot brief would: camera, lens, distances, light, every person and
object with its size, position and support. This module

- validates the spec and the physical relations it implies (frame coverage at the
  subject distance, horizon position for the camera tilt, shadow direction for the
  key light, depth ordering of the planes, support for every object);
- derives facts a prompt rarely states but a correct picture must obey (apparent
  size ratios between subjects at different distances, depth of field limits);
- compiles the spec into one prompt and one avoid list in a fixed order, and a set
  of atomic yes/no questions the visual reviewer must answer against the image;
- checks that a structured plausibility review answers every rubric check and every
  spec question with evidence before an image can pass.

Pure standard library: no Pillow, no network. The physics here is first-order
(pinhole camera, thin-lens depth of field); it catches contradictions in the brief,
it does not prove a generated picture is correct. The reviewer still looks.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

SPEC_VERSION = 1

# Full-frame sensor (36 x 24 mm); focal lengths in a spec are full-frame equivalents.
SENSOR_W_MM = 36.0
SENSOR_H_MM = 24.0
CIRCLE_OF_CONFUSION_MM = 0.03

MEDIA = {"photograph", "3d_render", "illustration", "flat_vector", "infographic_base"}
PHOTOGRAPHIC_MEDIA = {"photograph", "3d_render"}
SHOT_TYPES = {
    "extreme_wide",
    "wide",
    "full",
    "medium_wide",
    "medium",
    "medium_close",
    "close_up",
    "extreme_close_up",
    "macro",
}
ANGLES = {"eye_level", "high", "low", "overhead", "worms_eye", "dutch"}
TILTS = {"level", "down", "up", "straight_down", "straight_up"}
HORIZON = {"upper_third", "middle", "lower_third", "above_frame", "below_frame", "not_visible"}
# Only these three put the horizon somewhere in the picture. The other three say
# it is outside it, so nothing in the frame can be measured against it.
HORIZON_IN_FRAME = {"upper_third", "middle", "lower_third"}
DIRECTIONS = {
    "left",
    "right",
    "front",
    "behind",
    "above",
    "front_left",
    "front_right",
    "behind_left",
    "behind_right",
}
OPPOSITE = {
    "left": "right",
    "right": "left",
    "front": "toward the back of the scene",
    "behind": "toward the camera",
    "above": "directly below each object",
    "front_left": "back right",
    "front_right": "back left",
    "behind_left": "front right, toward the camera",
    "behind_right": "front left, toward the camera",
}
SHADOW_EXPECTED = {
    "left": {"right"},
    "right": {"left"},
    "front": {"behind", "away_from_camera"},
    "behind": {"front", "toward_camera"},
    "above": {"below", "under"},
    "front_left": {"behind_right", "right"},
    "front_right": {"behind_left", "left"},
    "behind_left": {"front_right", "right", "toward_camera"},
    "behind_right": {"front_left", "left", "toward_camera"},
}
PLANES = ("foreground", "midground", "background")

# What a reference source shows. A photograph of a shopfront says nothing about
# the room behind it, so a spec whose camera is inside needs an inside source.
VIEWPOINTS = {
    "exterior",
    "entrance",
    "street",
    "aerial",
    "interior_wide",
    "interior_detail",
    "stage_or_ring",
    "seating",
    "treatment_room",
    "reception",
    "product_detail",
    "staff_or_uniform",
}
# Which viewpoints show the SPACE a camera stands in. The useful question is
# not interior against exterior: a page of staff portraits is taken indoors and
# shows nothing of the room, and a product shot shows a thing, not a place.
INTERIOR_VIEWPOINTS = {
    "interior_wide",
    "interior_detail",
    "stage_or_ring",
    "seating",
    "treatment_room",
    "reception",
}
# Viewpoints that answer for a person or an object and never for a space.
NON_SPATIAL_VIEWPOINTS = {"product_detail", "staff_or_uniform"}
EXTERIOR_VIEWPOINTS = {"exterior", "entrance", "street", "aerial"}
# Only a source the client owns or has licensed may be fed to the generator as a
# conditioning image. A source found on the web informs what the author writes;
# it is not an input to the model.
CONDITIONING_RIGHTS = {"client_owned", "licensed"}
# A real site with an unbuilt scheme on it is neither a photograph of something
# that exists nor an invented place. Saying which it is keeps the facts and
# labels the picture honestly.
REFERENCE_STATES = {"existing", "planned", "under_construction", "former"}
REFERENCE_RIGHTS = CONDITIONING_RIGHTS | {"reference_only"}

# Eye height as a fraction of stature, by posture. Standing 0.93 is stable across
# populations: ANSUR II gives 164.0/175.5 = 0.934 for men and 151.7/162.6 = 0.933
# for women, and a British 50th-percentile table agrees within a centimetre.
# Under about five years a relatively larger head makes 0.90 safer. Seated and
# kneeling figures are handled as an absolute height above the floor instead,
# because the seat, not the stature, sets them.
EYE_FRACTION = {"standing": 0.93, "walking": 0.93, "leaning": 0.90, "crouching": 0.55}
EYE_ABSOLUTE_M = {"sitting": 1.23, "seated": 1.23, "kneeling": 1.15, "lying": 0.25}
CHILD_EYE_FRACTION = 0.90

# Where the landmarks of a standing body fall, as a fraction of stature. Same
# data family as EYE_FRACTION above: the standing-figure proportions of Drillis
# and Contini (1966), as tabulated in Winter, Biomechanics and Motor Control of
# Human Movement, figure 4.1. These make a scale anchor checkable: "its top
# meets her just above the hip" is a claim about a height, and a 0.42 m counter
# cannot make it.
BODY_LANDMARK_FRACTION = {
    "eye": 0.936,
    "eyes": 0.936,
    "chin": 0.870,
    "shoulder": 0.818,
    "shoulders": 0.818,
    "chest": 0.720,
    "elbow": 0.630,
    "elbows": 0.630,
    "waist": 0.600,
    "hip": 0.530,
    "hips": 0.530,
    # Mid-thigh, the midpoint of knee and hip, because it is what a desk or a
    # table top actually meets on a standing adult.
    "thigh": 0.420,
    "mid-thigh": 0.420,
    "wrist": 0.485,
    "fingertip": 0.377,
    "fingertips": 0.377,
    "knee": 0.285,
    "knees": 0.285,
    "ankle": 0.039,
}
# How far from the landmark the object's own height may sit before the anchor is
# describing a different object. Generous, because "just above the hip" is a
# human sentence, not a measurement.
LANDMARK_TOLERANCE_M = 0.12
# An object taller than this fraction of a person's stature does not fit in one
# hand; above the second it is a two-handed load. Read off the same table: a
# palm spans roughly the distance from fingertip to wrist.
# A landmark in a claim about width or length says nothing about height: "as
# wide as her shoulders" is a real sentence about a sign 0.5 m tall.
EXTENT_WORDS = (
    "wide", "width", "across", "broad", "long", "length", "span", "spans",
    "deep", "depth", "thick", "diameter", "tall as", "high as",
)
# Only something that stands on a surface has a height above that surface. A
# banner that hangs or a shelf that is mounted carries its own length in
# height_m, and comparing that with a landmark is meaningless.
FLOOR_SUPPORTED = {"stands_on", "rests_on"}
ONE_HAND_FRACTION = 0.30
TWO_HAND_FRACTION = 0.60
HAND_HELD_WORDS = ("one hand", "a hand", "his hand", "her hand", "their hand", "palm", "fingers wrap")

# A lens has a nearest sensible working distance for a face. Closer than this
# and the nose renders larger than the ears: the wide-angle portrait everyone
# recognises and nobody asks for.
MIN_FACE_DISTANCE_M = {20: 1.2, 28: 1.0, 35: 0.9, 50: 0.7, 85: 0.6}

# Weather that cannot coexist with a hard-edged shadow, because the sky is the
# source and the sky is the size of the sky.
DIFFUSE_WEATHER = ("overcast", "cloudy", "rain", "raining", "storm", "fog", "mist", "haze", "snow")
HARD_WORDS = ("hard", "crisp", "sharp-edged", "sharp edged", "harsh", "direct sun", "point source")
SOFT_WORDS = ("soft", "diffuse", "diffused", "wrapped", "even", "gentle")

# Heights fixed by building code or settled convention, in metres, as a range.
# Code-backed: ADA and the IRC/IBC. Convention-backed rows are marked, because a
# convention is a default a client may legitimately override, while a code
# minimum in a picture of a real building is simply wrong.
# ADA 404.2.7 (door hardware), ADA 308.2.1 (operable parts), IRC R311.7.5.1 and
# IBC 1011.5 (risers), IRC R311.7.5.2 (treads), IRC R305.1 (ceilings).
REFERENCE_HEIGHTS_M = {
    "door": (1.98, 2.15, "code: ADA, 2032 mm leaf, 1981 mm allowed at closers"),
    "doorway": (1.98, 2.15, "code: ADA"),
    "doorknob": (0.86, 1.22, "code: ADA 404.2.7, 34 to 48 in above the floor"),
    "door handle": (0.86, 1.22, "code: ADA 404.2.7"),
    "light switch": (0.38, 1.22, "code: ADA 308.2.1 operable parts"),
    "stair riser": (0.10, 0.20, "code: IRC 7 3/4 in, IBC 7 in maximum"),
    "stair tread": (0.25, 0.40, "code: IRC R311.7.5.2, 10 in minimum depth"),
    "ceiling": (2.13, 3.60, "code: IRC R305.1, 7 ft minimum for habitable space"),
    "countertop": (0.86, 0.95, "convention: 36 in US residential"),
    "kitchen counter": (0.86, 0.95, "convention: 36 in US residential"),
    "bar counter": (1.00, 1.12, "convention: 42 in"),
    "desk": (0.57, 0.78, "standard: BIFMA G1-2013 seated work surface range"),
    "work surface": (0.57, 0.78, "standard: BIFMA G1-2013"),
    "dining table": (0.70, 0.78, "convention: 28 to 30 in"),
    "chair seat": (0.38, 0.56, "standard: BIFMA G1-2013 and ANSI/HFES 100-2007"),
    "office chair": (0.38, 0.56, "standard: BIFMA G1-2013"),
    "handrail": (0.84, 0.99, "code: ADA 505.4, 34 to 38 in"),
    "sedan": (1.35, 1.55, "convention: measured roof heights of current sedans"),
    "pickup truck": (1.75, 2.02, "model data: Ram 1500 at 1917 mm"),
}
SUPPORT_KINDS = {"rests_on", "held_by", "mounted_on", "hangs_from", "worn_by", "stands_on", "floats_in", "fixed_in"}
# A support that holds nothing is the floating-object failure written into the
# brief. Scanned only for the kinds that bear weight: something may legitimately
# float in water, and nothing here should stop it.
UNSUPPORTING_RE = re.compile(
    r"\b(thin air|mid-?air|the air|nothing|nowhere|no (?:visible )?support|"
    r"hovering|floating|levitat\w*|suspended in (?:the )?air|an invisible \w+)\b",
    re.I,
)
BEARING_SUPPORT = {"rests_on", "stands_on", "mounted_on", "fixed_in", "hangs_from"}
SUPPORT_PARTICIPLE = {
    "rests_on": "resting on",
    "held_by": "held by",
    "mounted_on": "mounted on",
    "hangs_from": "hanging from",
    "worn_by": "worn by",
    "stands_on": "standing on",
    "floats_in": "floating in",
    "fixed_in": "fixed in",
}
# Only something that meets the ground or a surface casts the kind of shadow two
# entities can be compared on, and only those share a ground plane.
GROUNDED_SUPPORT = {"rests_on", "stands_on"}

# Rough framed width at the subject plane for each shot type, in metres, for a
# standing adult as the reference subject. Used only to flag gross contradictions.
SHOT_FRAME_WIDTH_M = {
    "extreme_wide": (8.0, 10000.0),
    "wide": (3.0, 200.0),
    "full": (1.2, 6.0),
    "medium_wide": (1.0, 4.0),
    "medium": (0.6, 2.5),
    "medium_close": (0.4, 1.6),
    "close_up": (0.15, 1.0),
    "extreme_close_up": (0.03, 0.4),
    "macro": (0.005, 0.15),
}

# Correlated colour temperature ranges (kelvin) that a named time of day can carry.
TIME_KELVIN = {
    "sunrise": (2000, 4500),
    "golden_hour": (2000, 4500),
    "morning": (4000, 6500),
    "midday": (5000, 7000),
    "afternoon": (4500, 6500),
    "sunset": (2000, 4500),
    "blue_hour": (6500, 12000),
    "overcast": (6000, 8000),
}
DAYLIGHT_SOURCES = ("sun", "daylight", "window", "sky")

# Where the compiled prompt may put the avoid list.
#   negative_prompt   a real negative channel: Stable Diffusion 3.5, Ideogram 3.0,
#                     Midjourney --no
#   inline_constraints a Constraints block in the prompt, which is what OpenAI's
#                     own guide prescribes and restates on every edit
#   none              no exclusions anywhere, for Gemini, FLUX, Ideogram 4.x,
#                     Recraft and Firefly, which have no negative field and whose
#                     vendors all say to describe the positive state instead
PROMPT_TARGETS = {"negative_prompt", "inline_constraints", "none"}
TARGET_ALIASES = {"positive_only": "inline_constraints"}

# A number in a prompt is decorative; the phrase it stands for is what steers.
# Measured, with 1.0 as perfect agreement with the request: colour temperature
# scores 0.231 on SD3 and 0.236 on FLUX, focal length 0.236 and 0.200, shutter
# 0.273 and 0.240 (Generative Photography, CVPR 2025, arXiv:2412.02168). Aperture
# fares no better: requested-versus-delivered blur correlates -0.206 on SD 1.5 and
# -0.033 on FLUX (Bokeh Diffusion, arXiv:2503.08434). So every number is emitted
# next to the words for its effect, never alone, which is also what Recraft's and
# Adobe's own example prompts do.
KELVIN_PHRASES = (
    (2200, "deep warm candle and tungsten light"),
    (3200, "warm tungsten light"),
    (4000, "warm white light"),
    (5000, "neutral white light"),
    (5800, "neutral daylight"),
    (7000, "cool daylight"),
    (20000, "cold blue shade light"),
)
APERTURE_PHRASES = (
    (1.8, "a very shallow depth of field, the background melting to soft bokeh"),
    (2.8, "a shallow depth of field, the background clearly soft"),
    (5.6, "a moderate depth of field"),
    (11.0, "a deep depth of field, most of the scene sharp"),
    (64.0, "sharp focus from front to back"),
)
FOCAL_PHRASES = (
    (20, "an ultra-wide view that stretches whatever is nearest the lens"),
    (28, "a wide view that takes in the room"),
    (40, "a wide-normal view"),
    (60, "a normal view, close to what the eye sees"),
    (105, "a short telephoto view that flatters a face and compresses depth"),
    (300, "a telephoto view that compresses the scene"),
    (1000, "a long telephoto view that stacks the planes flat"),
)
# Shot size as a taxonomy term is respected; the framing it delivers is not. Asked
# for a shot size in words alone, models overshot the staged subject height by
# 1.73 to 1.91 times, against 0.955 with geometric conditioning (PACE). So the
# prompt names the body fraction as well as the term.
SHOT_FRAMING = {
    "extreme_wide": "the figure small in a wide landscape",
    "wide": "the whole figure with space around it",
    "full": "head to feet, just inside the frame",
    "medium_wide": "framed from the knees up",
    "medium": "framed from the waist up",
    "medium_close": "framed from the chest up",
    "close_up": "head and shoulders filling the frame",
    "extreme_close_up": "part of the face filling the frame",
    "macro": "a detail at life size or larger",
}

# A positive prompt may never carry a negation. Applying a negative in the first
# few diffusion steps paradoxically generates the forbidden object, and 41.5 per
# cent of failed negated statements render exactly the thing the prompt forbade;
# the best model scores 31.4 per cent overall on negation (arXiv:2406.02965,
# NegT2IBench arXiv:2610.03084). Every vendor says the same in its own words:
# a party prompted with "no cake" still gets a cake. Describe the state instead.
# Words that push the model's own idealising prior harder without adding a fact.
# Banned from the brief for the same reason negation is: they feel like effort
# and they cost fidelity. One vendor's guidance reports they actively degrade
# the result; everywhere else they merely crowd out the facts that would have
# worked.
BOOSTER_WORDS = (
    "ultra detailed", "ultra-detailed", "hyper detailed", "hyper-detailed",
    "ultra realistic", "ultra-realistic", "hyperrealistic", "hyper-realistic",
    "photorealistic", "photo-realistic", "masterpiece", "stunning", "flawless",
    "breathtaking", "insane detail", "trending on artstation",
)
# Boosters that are also facts: "a perfect circle", "an award-winning chef", "a
# Sony 4K camcorder", "best quality coffee beans", "The Epic Theatre", "a highly
# detailed brass engraving", "the label in sharp focus". Refusing them anywhere
# refused correct briefs, so they are refused only as a bare list item, which
# is how a booster is written: "photorealistic, 8k, best quality". Found by the
# rangsarn session in its own lint, the same rule family.
LIST_BOOSTER_WORDS = (
    "4k", "8k", "16k", "uhd", "best quality", "high quality", "award winning",
    "award-winning", "perfect", "epic", "intricate detail", "intricate details",
    "highly detailed", "sharp focus",
)
# "crisp" is deliberately absent: HARD_WORDS looks for it in
# lighting.key.quality, where "edges are crisp" is the correct way to say a hard
# light. A word cannot be required by one check and refused by another.
BOOSTER_RE = re.compile(
    r"\b(" + "|".join(word.replace(" ", r"[\s-]") for word in BOOSTER_WORDS) + r")\b",
    re.I,
)
LIST_BOOSTER_RE = re.compile(
    r"(?:(?:and|or|in|with|at|(?:shot|rendered|captured) in)\s+)?("
    + "|".join(word.replace(" ", r"[\s-]") for word in LIST_BOOSTER_WORDS)
    + r")",
    re.I,
)
# A list item is what sits between commas, semicolons, bars, line breaks or
# sentence ends.
LIST_ITEM_SPLIT_RE = re.compile(r"[,;|\n]|\.(?:\s|$)")

# The identity of a person who comes with a reference image is carried by the
# image, not by the text. Describing the face in words fights the reference.
IDENTITY_LOCK = (
    "the face, bone structure, eye shape and colour, nose, mouth, jawline, skin "
    "tone and every identifying mark stay exactly as they are in the reference "
    "image"
)

# A simile is drawn, not understood: "hands like a pianist's" puts a piano in
# the frame. Adopted from rangsarn's prompt_lint P01.
SIMILE_RE = re.compile(
    r"\b(like|as if|as though|resembl\w*|reminiscent of|in the manner of|evoking)\b"
    r"|\b\w+-like\b",
    re.I,
)
# Words that are about a material or a finish rather than a comparison.
SIMILE_EXEMPT = ("lifelike", "life-like", "true-to-life", "businesslike", "likeness")
# "what a first appointment looks like" is not a comparison, so the simile rule
# has no business refusing it. It is still a weaker opening than the scene
# itself, which is said in its own message rather than smuggled into this one.
# Verbs and nouns in a purpose that put a person in the frame whatever the
# subject list says. Measured on the sweep: "the moment a rental car is handed
# over" and "as its customers meet it" both came back with people.
PERSON_IMPLIED_RE = re.compile(
    r"\b(handed|hands? over|handover|meet(?:s|ing)?|greet\w*|customers?|visitors?|"
    r"guests?|patients?|staff|people|someone|anyone|crowd|audience|teaching|"
    # Verb forms only: explain\w* matched "a technical explainer" and consult\w*
    # "the consultant's empty office", nouns that put nobody in the frame.
    r"explain(?:s|ed|ing)?|serv(?:e|es|ing)|welcom(?:e|es|ed)|consult(?:s|ed|ing)?)\b",
    re.I,
)
LOOKS_LIKE_RE = re.compile(
    r"\b(looks?|looked|looking|sounds?|feels?) like\b"
    # "what the consultation is really like" asks for the nature of a thing,
    # which is not a comparison. The leading "what" is the tell: without it,
    # "a smile is like sunshine" is a simile and stays refused.
    r"|\bwhat\b[^.;]{0,120}?\b(?:is|are|was|were)\s+(?:really\s+|actually\s+|truly\s+)?like\b",
    re.I,
)

# A pose named by the impression it gives is not a pose. The model needs to know
# where the limbs are. Adopted from rangsarn's prompt_lint P02.
EFFECT_POSE_RE = re.compile(
    r"\b(graceful(?:ly)?|elegant|dynamic|striking|confident|powerful|natural|relaxed|"
    r"casual|professional|stylish|heroic|iconic|expressive|effortless|poised|candid)\s+"
    r"(pose|posture|stance|gesture|look|manner|air|vibe)\b"
    r"|\bposed? (?:elegantly|gracefully|dynamically|confidently|naturally|professionally)\b",
    re.I,
)

# Camera words in a brief for a drawing get a photograph. The reverse of the
# medium the client asked for. Adopted from rangsarn's prompt_lint P04.
PHOTO_WORDS_RE = re.compile(
    r"\b(photograph\w*|photo-?real\w*|dslr|mirrorless|shot on \w+|film still|raw photo|"
    r"\d{2,3}\s?mm lens|bokeh|depth of field|shutter|exposure|iso \d+)\b",
    re.I,
)

# A fact recorded with a hedge was not established. Adopted from rangsarn's B01.
# Epistemic hedging only. "About 21:00" and "roughly 2.08 hectares" are not
# hedges, they are how a careful source states a figure and how an honest record
# of it reads, so a quantity after about, around or roughly is left alone.
HEDGE_RE = re.compile(
    r"\b(maybe|perhaps|possibly|probably|apparently|seemingly|"
    r"some kind of|sort of|kind of|or so|unclear|unknown|"
    r"appears to be|is said to be|reportedly)\b"
    r"|\b(?:about|around|roughly|approximately)\s+(?![\d.]|a few|an? \w+ of)"
    r"|-ish\b",
    re.I,
)

# Lettering the picture shows, in straight or curly double quotes. Single
# quotes are left out because they are also apostrophes.
QUOTED_RE = re.compile(r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d')
NEGATION_RE = re.compile(
    r"\b(no|not|none|never|without|free of|empty of|devoid of|avoid|exclude|"
    r"excluding|absent|lacking|remove|omit)\b",
    re.I,
)


def canonical_sha256(data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def policy_from_config(config: dict[str, Any]) -> dict[str, Any]:
    images = config.get("images", {}) if isinstance(config, dict) else {}
    spec_policy = dict(images.get("spec", {}) or {})
    plausibility = dict(images.get("plausibility", {}) or {})
    style = images.get("style", {}) or {}
    infographic = images.get("infographic", {}) or {}
    return {
        "spec": spec_policy,
        "plausibility": plausibility,
        "style_prompt_rules": _list(style.get("prompt_rules")),
        "style_negative_rules": _list(style.get("negative_prompt_rules")),
        "text_default": _text(style.get("text_default") or "none"),
        "infographic_allowed": bool(infographic.get("allowed", False)),
    }


def model_registry() -> dict[str, Any]:
    """Capability data for the generators a client may target.

    Model names, prompt limits and negative-prompt support change every few
    months, so this is a data file and never a table in code. Of the generators
    in the shipped registry only a minority have a negative-prompt field at all,
    which is why the target is read from the registry rather than assumed.
    """
    try:
        data = json.loads(MODEL_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    models = data.get("models", {})
    return models if isinstance(models, dict) else {}


def target_model_policy(config: dict[str, Any]) -> dict[str, Any]:
    """The registry entry for images.spec.target_model, or an empty dict."""
    name = _text(policy_from_config(config)["spec"].get("target_model"))
    if not name:
        return {}
    entry = model_registry().get(name)
    if not isinstance(entry, dict):
        raise ValueError(
            f"images.spec.target_model {name!r} is not in image-model-registry.json. "
            "Add a row for the model rather than changing the compiler."
        )
    return entry


def spec_required(item: dict[str, Any], config: dict[str, Any]) -> bool:
    """A spec is required for images that a model will generate."""
    policy = policy_from_config(config)["spec"]
    if not policy.get("required", True):
        return False
    provenance = item.get("provenance", {})
    source_type = ""
    if isinstance(provenance, dict):
        source_type = _text(provenance.get("source_type")).lower()
    required_types = [
        _text(value).lower()
        for value in policy.get("required_for_source_types", ["", "generated", "ai_generated"])
    ]
    return source_type in required_types


# ---------------------------------------------------------------- derivation


def frame_at(distance_m: float, focal_mm: float, aspect: float) -> tuple[float, float]:
    """Width and height in metres covered by the frame at a distance (pinhole)."""
    if aspect >= 1.0:
        width = distance_m * SENSOR_W_MM / focal_mm
        sensor_h = SENSOR_W_MM / aspect
        height = distance_m * sensor_h / focal_mm
    else:
        height = distance_m * SENSOR_W_MM / focal_mm
        width = height * aspect
    return width, height


def depth_of_field(focal_mm: float, aperture: float, distance_m: float) -> tuple[float, float]:
    """Near and far limits of acceptable focus in metres (thin lens, full frame)."""
    f = focal_mm / 1000.0
    c = CIRCLE_OF_CONFUSION_MM / 1000.0
    hyperfocal = f * f / (aperture * c) + f
    near = distance_m * (hyperfocal - f) / (hyperfocal + distance_m - 2 * f)
    if distance_m >= hyperfocal:
        far = math.inf
    else:
        far = distance_m * (hyperfocal - f) / (hyperfocal - distance_m)
    return max(near, 0.0), far


def expected_horizon(camera: dict[str, Any]) -> set[str]:
    """Where the horizon can sit in frame for the camera tilt (pinhole, no shift lens)."""
    tilt = _text(camera.get("tilt") or "level")
    angle = _text(camera.get("angle"))
    if tilt in {"straight_down", "straight_up"} or angle == "overhead":
        return {"not_visible", "above_frame", "below_frame"}
    if tilt == "level":
        return {"middle", "not_visible"}
    if tilt == "down":
        return {"upper_third", "above_frame", "not_visible"}
    if tilt == "up":
        return {"lower_third", "below_frame", "not_visible"}
    return set(HORIZON)


def _entities(spec: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for subject in _list(spec.get("subjects")):
        if isinstance(subject, dict):
            out.append(("subject", subject))
    for obj in _list(spec.get("objects")):
        if isinstance(obj, dict):
            out.append(("object", obj))
    return out


def ground_height(entity: dict[str, Any]) -> float:
    """Height of the surface this entity stands on, above the camera's own floor.

    Zero for someone standing on the same floor as the camera. A boxing ring, a
    stage or a kerb raises it, and the horizon then crosses that person lower on
    their body than it crosses anyone on the floor. Getting this wrong is how a
    picture ends up with a fighter whose eye line matches a spectator's.
    """
    return _num(entity.get("ground_height_m")) or 0.0


def eye_height(subject: dict[str, Any]) -> float | None:
    """Eye height above the floor for a person, from stature and posture.

    This is what fixes the horizon: the horizon is the vanishing line of the
    ground plane, so any point at the camera's own height images onto it,
    whatever its distance or the lens. A standing person whose eye height equals
    the camera height therefore has their eyes on the horizon. Farid states the
    projection fact in arXiv:2206.14617 section 2.1; Criminisi, Reid and
    Zisserman give the general cross-ratio form in Single View Metrology, IJCV
    40(2):123-148, 2000.
    """
    stature = _num(subject.get("height_m"))
    if stature is None:
        return None
    posture = _text(subject.get("posture") or "standing").lower()
    if posture in EYE_ABSOLUTE_M:
        return EYE_ABSOLUTE_M[posture] + ground_height(subject)
    fraction = EYE_FRACTION.get(posture)
    if fraction is None:
        return None
    if stature <= 1.15:  # a child under about five carries a larger head
        fraction = CHILD_EYE_FRACTION
    return stature * fraction + ground_height(subject)


def people(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Every person in the spec, whatever they are doing."""
    return [
        entity
        for kind, entity in _entities(spec)
        if kind == "subject" and _text(entity.get("kind") or "person") == "person"
    ]


def standing_people(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entity
        for entity in people(spec)
        if _text(entity.get("posture") or "standing").lower() in EYE_FRACTION
    ]


def eye_line_people(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Everyone whose eye height is known, standing or not.

    A seated figure has an eye line too, and in an interview, a desk or a
    restaurant scene it is the only one in the picture. Leaving the seated out
    of the horizon machinery threw away the most measurable cue in exactly the
    scenes that need it most.
    """
    return [entity for entity in people(spec) if eye_height(entity) is not None]


def entity_names(spec: dict[str, Any]) -> list[tuple[str, str]]:
    """Every name the spec declares for something that is in the picture."""
    names: list[tuple[str, str]] = []
    for _, entity in _entities(spec):
        eid = _text(entity.get("id"))
        for key in ("short_name", "name", "description"):
            value = _text(entity.get(key))
            if value:
                names.append((eid, value))
    return names


# Words that leave an avoid entry still naming just the thing itself.
_BARE_DETERMINERS = re.compile(
    r"^(?:a|an|the|any|some|every|all|no)\s+", re.I
)


def _bare(text: str) -> str:
    """An avoid entry reduced to its noun phrase, determiners and plural gone."""
    value = " ".join(text.lower().split()).strip(" .,;")
    previous = None
    while previous != value:
        previous = value
        value = _BARE_DETERMINERS.sub("", value)
    if value.endswith("es") and value[:-2] and not value.endswith("ses"):
        singular = value[:-2]
    elif value.endswith("s") and not value.endswith("ss"):
        singular = value[:-1]
    else:
        singular = value
    return singular


def collisions(spec: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Avoid entries that forbid, outright, a thing the spec puts in the picture.

    Only an entry that reduces to the declared name and nothing else is a
    contradiction. "A cluttered counter", "the pharmacist looking away", "pills
    on the counter" and "a second desk" all constrain a declared thing rather
    than forbid it, which is what must_not_show is for, and refusing them would
    refuse the most useful entries an author can write.

    Returns (avoid text, entity id, the name that matched).
    """
    found: list[tuple[str, str, str]] = []
    declared = entity_names(spec)
    for value in _list(spec.get("must_not_show")):
        text = _text(value)
        if not text:
            continue
        bare = _bare(text)
        for eid, name in declared:
            if bare and bare in {_bare(name), name.lower()}:
                found.append((text, eid, name))
                break
    return found


def anchor_person(anchor: str, subjects: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The person a scale anchor is about, or None when it does not say.

    Matched on word boundaries against the id and the short name, because an id
    of "a" otherwise matches the "a" inside "waist". With several people in
    frame and none of them named, the anchor is ambiguous and no check runs: a
    wrong referent produces a confident error message naming someone the author
    never mentioned, which is worse than no check at all.
    """
    lowered = anchor.lower()
    named = []
    for subject in subjects:
        for token in (subject.get("id"), subject.get("short_name")):
            text = _text(token).lower()
            if text and re.search(r"\b" + re.escape(text) + r"\b", lowered):
                named.append(subject)
                break
    if len(named) == 1:
        return named[0]
    if not named and len(subjects) == 1:
        return subjects[0]
    return None


def anchor_is_about_extent(anchor: str, word: str) -> bool:
    """Whether the landmark sits in a claim about width or length, not height."""
    lowered = anchor.lower()
    index = lowered.find(word)
    if index < 0:
        return False
    window = lowered[max(0, index - 40):index]
    return any(extent in window for extent in EXTENT_WORDS)


def reference_height(name: str) -> tuple[float, float, str] | None:
    """The code or convention height band for a named object, if there is one."""
    lowered = name.lower()
    best: tuple[int, tuple[float, float, str]] | None = None
    for key, band in REFERENCE_HEIGHTS_M.items():
        # The name has to END with the reference word, so a desk lamp is not a
        # desk and a ceiling bracket is not a ceiling. A qualifier in front is
        # fine, "pale wood dispensing counter" is still a counter.
        if not re.search(r"\b" + re.escape(key) + r"s?\b\s*$", lowered):
            continue
        if best is None or len(key) > best[0]:
            best = (len(key), band)
    return best[1] if best else None


def has_reference_image(subject: dict[str, Any]) -> bool:
    """Whether this person's likeness is supplied as an image."""
    return bool(_text(subject.get("reference_image")))


def reference_block(spec: dict[str, Any]) -> dict[str, Any]:
    location = spec.get("location")
    if not isinstance(location, dict):
        return {}
    reference = location.get("reference")
    return reference if isinstance(reference, dict) else {}


def is_real_place(spec: dict[str, Any]) -> bool:
    return bool(reference_block(spec).get("place_is_real"))


def camera_is_inside(spec: dict[str, Any]) -> bool:
    """Whether the camera stands inside the place, from the layout it describes."""
    camera = spec.get("camera", {}) if isinstance(spec.get("camera"), dict) else {}
    if _text(camera.get("angle")) == "overhead":
        return False
    location = spec.get("location", {}) if isinstance(spec.get("location"), dict) else {}
    inside_words = ("room", "hall", "indoor", "inside", "interior", "counter", "lobby", "studio")
    place = _text(location.get("place")).lower()
    if any(word in place for word in inside_words):
        return True
    horizon = _text(camera.get("horizon"))
    return horizon == "not_visible"


def people_count(spec: dict[str, Any]) -> int:
    total = 0
    for subject in _list(spec.get("subjects")):
        if isinstance(subject, dict) and _text(subject.get("kind") or "person") == "person":
            count = _num(subject.get("count"))
            total += int(count) if count else 1
    return total


def derive(spec: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    camera = spec.get("camera", {}) if isinstance(spec.get("camera"), dict) else {}
    aspect = width / height if width and height else 1.5
    focal = _num(camera.get("focal_length_mm"))
    distance = _num(camera.get("subject_distance_m"))
    aperture = _num(camera.get("aperture_f"))
    derived: dict[str, Any] = {
        "aspect_ratio": round(aspect, 3),
        "orientation": "landscape" if aspect > 1.05 else ("portrait" if aspect < 0.95 else "square"),
        "expected_horizon": sorted(expected_horizon(camera)),
    }
    if focal and distance:
        frame_w, frame_h = frame_at(distance, focal, aspect)
        derived["frame_at_subject_m"] = {"width": round(frame_w, 2), "height": round(frame_h, 2)}
        derived["horizontal_fov_deg"] = round(
            math.degrees(2 * math.atan(SENSOR_W_MM / (2 * focal))), 1
        )
    if focal and distance and aperture:
        near, far = depth_of_field(focal, aperture, distance)
        derived["depth_of_field_m"] = {
            "near": round(near, 2),
            "far": "infinity" if math.isinf(far) else round(far, 2),
        }
    scale: list[dict[str, Any]] = []
    sized = []
    for kind, entity in _entities(spec):
        h = _num(entity.get("height_m"))
        d = _num(entity.get("distance_m"))
        if h and d:
            sized.append((entity, h, d))
    if focal and sized:
        sensor_h = SENSOR_H_MM if aspect >= 1.0 else SENSOR_W_MM
        if aspect >= 1.0:
            sensor_h = SENSOR_W_MM / aspect
        for entity, h, d in sized:
            fraction = (h * focal / 1000.0) / d / (sensor_h / 1000.0)
            scale.append(
                {
                    "id": _text(entity.get("id")),
                    "apparent_height_fraction": round(fraction, 3),
                }
            )
    derived["apparent_heights"] = scale
    ratios = []
    for i in range(len(sized)):
        for j in range(i + 1, len(sized)):
            a, ha, da = sized[i]
            b, hb, db = sized[j]
            if abs(da - db) < 0.01:
                continue
            ratio = (ha / da) / (hb / db)
            ratios.append(
                {
                    "a": _text(a.get("id")),
                    "b": _text(b.get("id")),
                    "a_to_b_apparent_height": round(ratio, 2),
                }
            )
    derived["apparent_ratios"] = ratios

    # An entity taller than the frame at its own distance has no measurable frame
    # height, so a ratio against it cannot be answered by looking at the picture.
    fits: dict[str, bool] = {}
    if focal:
        for entity, h, d in sized:
            _, frame_h = frame_at(d, focal, aspect)
            fits[_text(entity.get("id"))] = h <= frame_h * 0.98
    derived["fits_in_frame"] = fits

    # Which entities fall outside the depth of field, so the prompt can name them
    # as soft instead of quoting metres an image model cannot use.
    dof = derived.get("depth_of_field_m")
    outside: list[str] = []
    if dof:
        near = float(dof["near"])
        far = math.inf if dof["far"] == "infinity" else float(dof["far"])
        for entity, _h, d in sized:
            if d < near or d > far:
                outside.append(_text(entity.get("id")))
    derived["outside_focus"] = outside

    # The camera at standing eye height puts the horizon through the eyes: the
    # single most reliable cue that a generated scene has one consistent viewpoint.
    cam_height = _num(camera.get("height_m"))
    eyes = [e for e in (eye_height(s) for s in eye_line_people(spec)) if e is not None]
    derived["camera_at_eye_height"] = bool(
        cam_height is not None
        and eyes
        and abs(cam_height - sum(eyes) / len(eyes)) <= 0.15
    )

    # Where the horizon must cut each standing figure, as a fraction of its height
    # from the feet: h_c / h, exactly, independent of distance and of focal length.
    # In image rows the same identity reads
    # h / h_c = (y_base - y_top) / (y_base - y_horizon), which is the one test a
    # reviewer can actually measure with a ruler on the finished picture.
    crossings: list[dict[str, Any]] = []
    if cam_height:
        for subject in eye_line_people(spec):
            stature = _num(subject.get("height_m"))
            if not stature:
                continue
            # The horizon is at the lens height, so for someone whose feet are
            # already raised the eye-level line sits lower on them, and for
            # someone standing high enough it passes below their feet entirely.
            feet = ground_height(subject)
            posture = _text(subject.get("posture") or "standing").lower()
            if posture in EYE_ABSOLUTE_M:
                # A seated figure's visible height is not their stature: measure
                # the crossing against the eye height the pose actually gives.
                visible = EYE_ABSOLUTE_M[posture] / 0.93
            else:
                visible = stature
            fraction = (cam_height - feet) / visible
            crossings.append(
                {
                    "id": _text(subject.get("id")),
                    "fraction_of_height_from_feet": round(max(min(fraction, 2.0), -2.0), 3),
                    "above_head": fraction > 1.0,
                    "below_feet": fraction < 0.0,
                    "stands_on_m": round(feet, 2),
                }
            )
    derived["horizon_crossings"] = crossings

    # Apparent-size relations stated in words, because a model reads "clearly
    # larger in the frame" and cannot act on "1.55x". The exact ratios stay in
    # apparent_ratios for the reviewer's questions.
    notes: list[str] = []
    by_id = {_text(entity.get("id")): entity for _, entity in _entities(spec)}
    for ratio in ratios:
        a = by_id.get(ratio["a"])
        b = by_id.get(ratio["b"])
        if not a or not b:
            continue
        ha, hb = _num(a.get("height_m")), _num(b.get("height_m"))
        if not ha or not hb:
            continue
        # Only worth saying when the frame contradicts the real sizes: the
        # smaller thing reading larger, or two near-equal things reading apart.
        real = ha / hb
        apparent = ratio["a_to_b_apparent_height"]
        # Worth a sentence only when the frame contradicts the real sizes by a
        # fifth or more; a difference proportional to the sizes, not absolute,
        # so a tall thing next to a small one does not trigger it every time.
        if not real or abs(apparent / real - 1.0) < 0.2:
            continue
        notes.append(
            f"{_noun(a)[0].upper() + _noun(a)[1:]} is {_fmt_m(ha)} tall and "
            f"{_noun(b)} is {_fmt_m(hb)} tall, but because of their distances "
            f"{_noun(a)} reads {_size_word(apparent)} {_noun(b)}"
        )
    derived["scale_notes"] = notes[:3]
    return derived


# ---------------------------------------------------------------- validation


PLACEHOLDER_RE = re.compile(r"^<.*>$", re.S)


def unfilled_placeholders(value: Any, path: str = "") -> list[str]:
    """Paths whose value is still a template question such as ``<who they are>``."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(unfilled_placeholders(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(unfilled_placeholders(child, f"{path}[{index}]"))
    elif isinstance(value, str) and PLACEHOLDER_RE.match(value.strip()):
        found.append(path or "<root>")
    return found


# These two reach the avoid list, never the positive prompt, so a negation in
# them is correct. text_in_image is a policy value whose own default is "none".
# Fields whose text never reaches the prompt. The lint rules exist to protect
# the prompt, so running them over an audit trail refuses the most useful
# sentence an author can write: "none of the three sources shows the inside of
# this clinic at all" belongs in conflicting_claims and is a negation by nature.
NEGATION_EXEMPT_KEYS = {"must_not_show", "text_in_image"}
AUDIT_ONLY_KEYS = {
    "sources",
    "conflicting_claims",
    "address",
    "publisher",
    "url",
    "shows",
    "accessed",
    "rights",
    "viewpoint",
    "conditioning_images",
    "place_name",
}


def negated_fields(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Spec fields that describe the picture by what it is not."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in NEGATION_EXEMPT_KEYS or key in AUDIT_ONLY_KEYS:
                continue
            found.extend(negated_fields(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(negated_fields(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for word in negations(value):
            found.append((path or "<root>", word))
    return found


def _prose_fields(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Every free-text field in the spec, with its path, for the lint rules."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in NEGATION_EXEMPT_KEYS or key in AUDIT_ONLY_KEYS:
                continue
            found.extend(_prose_fields(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_prose_fields(child, f"{path}[{index}]"))
    elif isinstance(value, str) and value.strip():
        found.append((path or "<root>", value))
    return found


def _require(errors: list[str], cond: bool, message: str) -> None:
    if not cond:
        errors.append(message)


def validate_spec(
    spec: Any,
    width: int,
    height: int,
    config: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block compilation."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(spec, dict) or not spec:
        return ["spec must be a non-empty object."], warnings
    policy = policy_from_config(config or {})
    spec_policy = policy["spec"]

    # Everything any section below may read, bound once, before any of them run.
    # These are pure reads of the spec; nothing needs them computed late, and
    # binding them here is what stops a new check in one section raising an
    # UnboundLocalError by reaching for a name another section binds later.
    medium = _text(spec.get("medium") or "photograph")
    photographic = medium in PHOTOGRAPHIC_MEDIA
    subjects = [s for s in _list(spec.get("subjects")) if isinstance(s, dict)]
    objects = [o for o in _list(spec.get("objects")) if isinstance(o, dict)]

    for path in sorted(unfilled_placeholders(spec)):
        errors.append(f"spec.{path} still holds the template question; answer it.")

    for path, word in sorted(boosted_fields(spec)):
        errors.append(
            f"spec.{path} reaches for {word!r}, which is a booster word, not a fact. It "
            "pushes the model's own idea of a good picture and crowds out the detail that "
            "would have steered it. Say what is actually there instead."
        )

    for path, word in sorted(negated_fields(spec)):
        errors.append(
            f"spec.{path} says what the picture is not ({word!r}). Describe the state "
            "it is in instead, and move anything to exclude into spec.must_not_show, "
            "which reaches the avoid list rather than the prompt."
        )

    version = spec.get("version", SPEC_VERSION)
    if version != SPEC_VERSION:
        errors.append(f"spec.version must be {SPEC_VERSION}.")
    _require(errors, bool(_text(spec.get("purpose"))), "spec.purpose is required: what the reader must understand from the image.")
    if medium not in MEDIA:
        errors.append("spec.medium must be one of " + ", ".join(sorted(MEDIA)) + ".")

    if not subjects and PERSON_IMPLIED_RE.search(_text(spec.get("purpose"))):
        warnings.append(
            "spec.purpose describes a human action but the spec declares no people. "
            "The purpose opens the prompt, which every model weights most, so it "
            "outweighs an empty subject list and people tend to appear. Either declare "
            "the people, or write the purpose as the thing or the place."
        )

    for path, value in _prose_fields(spec):
        if path == "purpose" and LOOKS_LIKE_RE.search(value):
            warnings.append(
                "spec.purpose says what the picture looks like rather than what it is. "
                "Write the scene: a pharmacist pointing at a label, not what a pharmacy "
                "visit looks like. The opening of the prompt is the part every model "
                "weights most."
            )
        for word in similes(value):
            errors.append(
                f"spec.{path} compares with {word!r}. A generator draws the thing you "
                "compared to, so a hand like a pianist's puts a piano in the frame. Say "
                "what is actually there instead."
            )
        if EFFECT_POSE_RE.search(value) and path.split(".")[-1].rstrip("0123456789[]") in (
            "pose", "action", "expression", "gaze", "subject_placement"
        ):
            errors.append(
                f"spec.{path} names the impression a pose gives rather than the pose. "
                "Say where the limbs are: which hand, which foot, where the weight sits, "
                "which way the body faces."
            )
        if not photographic and PHOTO_WORDS_RE.search(value):
            errors.append(
                f"spec.{path} uses camera words in a brief for {medium.replace('_', ' ')}. "
                "A generator reads those as an instruction to make a photograph. Describe "
                "the medium the client asked for instead."
            )

    # Location and time.
    location = spec.get("location")
    if not isinstance(location, dict):
        errors.append("spec.location is required (place, locale, time_of_day).")
        location = {}
    else:
        _require(errors, bool(_text(location.get("place"))), "spec.location.place is required.")
        _require(errors, bool(_text(location.get("locale"))), "spec.location.locale is required (country or city the scene belongs to).")
        if photographic:
            _require(errors, bool(_text(location.get("time_of_day"))), "spec.location.time_of_day is required for photographic media.")

    # A named real place is a claim about the world, and a picture that gets it
    # wrong is worse than a generic one: the client's own customers know the room.
    reference = location.get("reference") if isinstance(location, dict) else None
    if reference is not None and not isinstance(reference, dict):
        errors.append("spec.location.reference must be an object.")
        reference = None
    if isinstance(reference, dict) and reference.get("place_is_real"):
        _require(
            errors,
            bool(_text(reference.get("place_name"))),
            "spec.location.reference.place_name is required for a real place.",
        )
        sources = [r for r in _list(reference.get("sources")) if isinstance(r, dict)]
        min_sources = int(spec_policy.get("min_reference_sources", 2))
        if len(sources) < min_sources:
            errors.append(
                f"spec.location.reference.sources has {len(sources)} entries; a real place "
                f"needs at least {min_sources}, because one page is a claim and two that "
                "agree are evidence."
            )
        seen_viewpoints: set[str] = set()
        for index, source in enumerate(sources):
            where = f"spec.location.reference.sources[{index}]"
            for field in ("url", "publisher", "shows", "accessed"):
                if not _text(source.get(field)):
                    errors.append(f"{where}.{field} is required.")
            viewpoint = _text(source.get("viewpoint"))
            if viewpoint not in VIEWPOINTS:
                errors.append(
                    f"{where}.viewpoint must be one of " + ", ".join(sorted(VIEWPOINTS)) + "."
                )
            else:
                seen_viewpoints.add(viewpoint)
            rights = _text(source.get("rights"))
            if rights not in REFERENCE_RIGHTS:
                errors.append(
                    f"{where}.rights must be one of " + ", ".join(sorted(REFERENCE_RIGHTS)) + "."
                )
        state = _text(reference.get("state") or "existing")
        if state not in REFERENCE_STATES:
            errors.append(
                "spec.location.reference.state must be one of "
                + ", ".join(sorted(REFERENCE_STATES))
                + "."
            )
        elif state != "existing":
            warnings.append(
                f"spec.location.reference.state is {state!r}: the place is real but what "
                "the picture shows is not there yet, so the image is a visualisation. Say "
                "so wherever it is published, and keep the caption and alt text honest."
            )

        facts = [_text(v) for v in _list(reference.get("verified_facts")) if _text(v)]
        for index, fact in enumerate(facts):
            hedge = HEDGE_RE.search(fact)
            if hedge:
                errors.append(
                    f"spec.location.reference.verified_facts[{index}] hedges with "
                    f"{hedge.group(0)!r}. A fact recorded with a hedge was not verified. "
                    "Either establish it and state it plainly, or move it to "
                    "conflicting_claims where an unsettled claim belongs."
                )
        if not facts:
            errors.append(
                "spec.location.reference.verified_facts is empty: write down what the "
                "sources actually establish about this place, because that is what the "
                "picture has to match and what the reviewer will check."
            )

        # A source showing the outside says nothing about the room inside.
        if seen_viewpoints:
            inside = camera_is_inside(spec)
            needed = INTERIOR_VIEWPOINTS if inside else EXTERIOR_VIEWPOINTS
            if not (seen_viewpoints & needed):
                only_people_and_things = seen_viewpoints <= NON_SPATIAL_VIEWPOINTS
                errors.append(
                    "spec.location.reference.sources cover "
                    + ", ".join(sorted(seen_viewpoints))
                    + ", but the camera is "
                    + ("inside" if inside else "outside")
                    + " this place and "
                    + (
                        "none of those shows the space itself: a staff portrait and a "
                        "product shot answer for a person and a thing, never for a room. "
                        if only_people_and_things
                        else "no source shows it from there. "
                    )
                    + "Add a source that shows the space, or set place_is_real false and "
                    "describe a place of that kind instead of naming this one."
                )

        conditioning = [_text(v) for v in _list(reference.get("conditioning_images")) if _text(v)]
        conditioning += [
            _text(subject.get("reference_image"))
            for subject in subjects
            if has_reference_image(subject)
        ]
        # Each image has to carry its own rights. Checking that the set holds one
        # owned source let a single client photograph authorise feeding anything
        # at all to the generator, including a path with no provenance row.
        for image in conditioning:
            match = None
            for source in sources:
                url = _text(source.get("url"))
                if not url:
                    continue
                if image == url or image in url or url in image:
                    match = source
                    break
            if match is None:
                errors.append(
                    f"spec.location.reference: {image!r} is fed to the generator but no "
                    "source records where it came from. Every conditioning image needs "
                    "its own row in sources with the rights it is used under."
                )
            elif _text(match.get("rights")) not in CONDITIONING_RIGHTS:
                errors.append(
                    f"spec.location.reference: {image!r} is recorded as "
                    f"{_text(match.get('rights'))!r}, which may inform what you write but "
                    "may not be fed to the generator. Only client_owned or licensed may."
                )
    elif isinstance(reference, dict) and _list(reference.get("conditioning_images")):
        errors.append(
            "spec.location.reference.conditioning_images without place_is_real: say which "
            "place these images show."
        )

    # Camera.
    camera = spec.get("camera")
    if not isinstance(camera, dict):
        errors.append("spec.camera is required.")
        camera = {}
    focal = _num(camera.get("focal_length_mm"))
    distance = _num(camera.get("subject_distance_m"))
    aperture = _num(camera.get("aperture_f"))
    cam_height = _num(camera.get("height_m"))
    shot = _text(camera.get("shot_type"))
    angle = _text(camera.get("angle"))
    tilt = _text(camera.get("tilt") or "level")
    horizon = _text(camera.get("horizon"))
    if shot not in SHOT_TYPES:
        errors.append("spec.camera.shot_type must be one of " + ", ".join(sorted(SHOT_TYPES)) + ".")
    if angle not in ANGLES:
        errors.append("spec.camera.angle must be one of " + ", ".join(sorted(ANGLES)) + ".")
    if tilt not in TILTS:
        errors.append("spec.camera.tilt must be one of " + ", ".join(sorted(TILTS)) + ".")
    if horizon and horizon not in HORIZON:
        errors.append("spec.camera.horizon must be one of " + ", ".join(sorted(HORIZON)) + ".")
    if photographic:
        if focal is None or not 8 <= focal <= 800:
            errors.append("spec.camera.focal_length_mm (full-frame equivalent, 8-800) is required for photographic media.")
        if distance is None or distance <= 0:
            errors.append("spec.camera.subject_distance_m (metres to the focus subject) is required for photographic media.")
        if aperture is None or not 0.95 <= aperture <= 32:
            errors.append("spec.camera.aperture_f (0.95-32) is required for photographic media.")
        if cam_height is None or cam_height < 0:
            errors.append("spec.camera.height_m (lens height above the ground or floor) is required for photographic media.")
        if not horizon:
            errors.append("spec.camera.horizon is required for photographic media.")
        _require(errors, bool(_text(camera.get("focus_on"))), "spec.camera.focus_on is required: the id of the subject or object in focus.")

    if photographic and focal and distance and people(spec):
        nearest = min(
            (d for d in (_num(s.get("distance_m")) for s in people(spec)) if d),
            default=None,
        )
        floor = None
        for lens, limit in sorted(MIN_FACE_DISTANCE_M.items()):
            if focal <= lens:
                floor = limit
                break
        if nearest and floor and nearest < floor:
            errors.append(
                f"spec.camera: a face {nearest:g} m from a {focal:g} mm lens renders the "
                f"nose larger than the ears. Keep a person at least {floor:g} m away on "
                "this lens, or use a longer one."
            )

    if horizon and tilt in TILTS:
        allowed = expected_horizon(camera)
        if horizon not in allowed:
            errors.append(
                f"spec.camera.horizon {horizon!r} contradicts tilt {tilt!r}: a "
                + ("level camera puts the horizon through the frame centre" if tilt == "level" else
                   "camera tilted down pushes the horizon up" if tilt == "down" else
                   "camera tilted up pushes the horizon down" if tilt == "up" else
                   "straight up or down view shows no horizon")
                + "; allowed: " + ", ".join(sorted(allowed)) + "."
            )
    if angle == "eye_level" and tilt not in {"level", ""}:
        warnings.append("spec.camera.angle eye_level usually means a level camera; tilt is not level.")
    if angle == "high" and tilt == "up":
        errors.append("spec.camera.angle high with tilt up is contradictory.")
    if angle in {"low", "worms_eye"} and tilt == "down":
        errors.append("spec.camera.angle low with tilt down is contradictory.")

    # Entities.
    if not subjects and not objects:
        errors.append("spec needs at least one subject or object.")
    ids: dict[str, str] = {}
    for kind, entity in _entities(spec):
        eid = _text(entity.get("id"))
        if not eid:
            errors.append(f"every {kind} needs an id.")
            continue
        if eid in ids:
            errors.append(f"duplicate entity id {eid!r}.")
        ids[eid] = kind

    focus_on = _text(camera.get("focus_on"))
    if focus_on and focus_on not in ids:
        errors.append(f"spec.camera.focus_on {focus_on!r} is not a subject or object id.")

    eye_heights: list[float] = []
    for subject in subjects:
        sid = _text(subject.get("id")) or "?"
        kind = _text(subject.get("kind") or "person")
        count = _num(subject.get("count"))
        if count is None or count < 1 or int(count) != count:
            errors.append(f"subject {sid}: count must be a whole number of at least 1.")
        for field in ("description", "action", "position"):
            if not _text(subject.get(field)):
                errors.append(f"subject {sid}: {field} is required.")
        if kind == "person":
            required_fields = ["wardrobe", "pose", "gaze"]
            if has_reference_image(subject):
                # The likeness is in the image. A description of the face in the
                # prompt competes with it, so the field is refused rather than
                # merely ignored: an author who writes it expects it to be used.
                if _text(subject.get("appearance")):
                    errors.append(
                        f"subject {sid}: appearance must be empty when reference_image is "
                        "set. The likeness comes from the image, and describing the face "
                        "in words fights it and loses the likeness. Put anything that is "
                        "not the person, such as what they are wearing, in wardrobe."
                    )
            else:
                required_fields.insert(0, "appearance")
            for field in required_fields:
                if not _text(subject.get(field)):
                    errors.append(f"subject {sid}: {field} is required for a person.")
            if not _text(subject.get("hands")):
                errors.append(f"subject {sid}: hands is required for a person (what each hand does, or that hands are out of frame).")
            h = _num(subject.get("height_m"))
            if h is None or not 0.4 <= h <= 2.3:
                errors.append(f"subject {sid}: height_m (0.4-2.3) is required for a person; it anchors scale.")
            else:
                eye = eye_height(subject)
                if eye is not None:
                    eye_heights.append(eye)
        if photographic:
            d = _num(subject.get("distance_m"))
            if d is None or d <= 0:
                errors.append(f"subject {sid}: distance_m from the camera is required for photographic media.")
        plane = _text(subject.get("plane"))
        if plane and plane not in PLANES:
            errors.append(f"subject {sid}: plane must be foreground, midground or background.")
        for ref in _list(subject.get("interacts_with")):
            if _text(ref) not in ids:
                errors.append(f"subject {sid}: interacts_with {ref!r} is not a known id.")

    for obj in objects:
        oid = _text(obj.get("id")) or "?"
        count = _num(obj.get("count"))
        if count is None or count < 1 or int(count) != count:
            errors.append(f"object {oid}: count must be a whole number of at least 1.")
        for field in ("name", "position", "material", "state"):
            if not _text(obj.get(field)):
                errors.append(f"object {oid}: {field} is required.")
        if not _text(obj.get("size")) and _num(obj.get("height_m")) is None and _num(obj.get("width_m")) is None:
            errors.append(f"object {oid}: give a real size (size text, height_m or width_m).")
        if not _text(obj.get("scale_anchor")):
            errors.append(f"object {oid}: scale_anchor is required: compare its size with a person or another object in the scene.")
        support = obj.get("support")
        if not isinstance(support, dict) or _text(support.get("kind")) not in SUPPORT_KINDS or not _text(support.get("by")):
            errors.append(
                f"object {oid}: support {{kind, by}} is required so nothing floats; kind is one of "
                + ", ".join(sorted(SUPPORT_KINDS)) + "."
            )
        elif (
            _text(support.get("kind")) in BEARING_SUPPORT
            and UNSUPPORTING_RE.search(_text(support.get("by")))
        ):
            errors.append(
                f"object {oid}: support.by {support.get('by')!r} does not hold anything "
                "up. Name the surface, the fixing or the person that takes its weight, or "
                "change the scene so it does not need one."
            )
        elif (
            _text(support.get("kind")) in {"held_by", "worn_by"}
            and ids.get(_text(support.get("by"))) != "subject"
        ):
            # ids spans subjects and objects, so testing membership let a carton
            # be held by a counter while the message said it must be a person.
            errors.append(
                f"object {oid}: support.by {support.get('by')!r} must be a subject id for "
                "held_by or worn_by; only a person holds or wears something."
            )
        if photographic:
            d = _num(obj.get("distance_m"))
            if d is None or d <= 0:
                errors.append(f"object {oid}: distance_m from the camera is required for photographic media.")
        plane = _text(obj.get("plane"))
        if plane and plane not in PLANES:
            errors.append(f"object {oid}: plane must be foreground, midground or background.")
        for ref in _list(obj.get("interacts_with")):
            if _text(ref) not in ids:
                errors.append(f"object {oid}: interacts_with {ref!r} is not a known id.")

    # Plane ordering: every foreground entity is nearer than every midground one, and so on.
    by_plane: dict[str, list[float]] = {p: [] for p in PLANES}
    for _, entity in _entities(spec):
        plane = _text(entity.get("plane"))
        d = _num(entity.get("distance_m"))
        if plane in by_plane and d:
            by_plane[plane].append(d)
    for near_plane, far_plane in (("foreground", "midground"), ("midground", "background"), ("foreground", "background")):
        if by_plane[near_plane] and by_plane[far_plane] and max(by_plane[near_plane]) >= min(by_plane[far_plane]):
            errors.append(
                f"plane order contradiction: a {near_plane} entity is not nearer than every {far_plane} entity."
            )

    # Focus subject distance should agree with the focus entity's own distance.
    if focus_on and distance:
        for _, entity in _entities(spec):
            if _text(entity.get("id")) == focus_on:
                d = _num(entity.get("distance_m"))
                if d and abs(d - distance) / distance > 0.25:
                    errors.append(
                        f"spec.camera.subject_distance_m {distance} disagrees with {focus_on}.distance_m {d}."
                    )

    # Shot type against the frame actually covered at the subject plane.
    if photographic and focal and distance and shot in SHOT_FRAME_WIDTH_M and width and height:
        frame_w, frame_h = frame_at(distance, focal, width / height)
        low, high = SHOT_FRAME_WIDTH_M[shot]
        if not low * 0.5 <= frame_w <= high * 1.5:
            errors.append(
                f"spec.camera shot_type {shot!r} contradicts the lens and distance: {focal:g} mm at "
                f"{distance:g} m frames about {frame_w:.2f} m wide, expected {low:g}-{high:g} m. "
                "Change the focal length, the distance, or the shot type."
            )
        for obj in objects:
            obj_width = _num(obj.get("width_m"))
            obj_distance = _num(obj.get("distance_m"))
            # A ground plane, a wall, a row of seats, a roof deck or a body of
            # water is wider than the frame by design. Saying so keeps width_m
            # the real size instead of the visible run, which is what every
            # apparent-size ratio is computed from.
            if obj.get("extends_beyond_frame"):
                continue
            if obj_width and obj_distance:
                frame_width, _ = frame_at(obj_distance, focal, width / height)
                if obj_width > frame_width * 3.0:
                    errors.append(
                        f"object {_text(obj.get('id'))}: {obj_width:g} m wide at "
                        f"{obj_distance:g} m, where the lens frames {frame_width:.2f} m "
                        "across. Only a fraction of it can be in shot. Either it is "
                        "nearer, or narrower, or the shot is wider than the spec says, or "
                        "it genuinely runs past the edge of the frame and wants "
                        "extends_beyond_frame true, which keeps width_m the real size."
                    )
        if shot in {"full", "wide", "extreme_wide"}:
            for subject in subjects:
                h = _num(subject.get("height_m"))
                d = _num(subject.get("distance_m"))
                if h and d and _text(subject.get("posture") or "standing") == "standing":
                    _, fh = frame_at(d, focal, width / height)
                    if h > fh:
                        errors.append(
                            f"subject {subject.get('id')}: a {h:g} m standing person at {d:g} m does not fit "
                            f"the {fh:.2f} m frame height of a {shot} shot."
                        )

    # A scale anchor names a landmark on a person. That is a claim about a
    # height, and the object either makes it or does not.
    tallest = max(
        (h for h in (_num(subject.get("height_m")) for subject in subjects) if h),
        default=None,
    )
    for obj in objects:
        anchor = _text(obj.get("scale_anchor")).lower()
        obj_height = _num(obj.get("height_m"))
        if not anchor or not obj_height or not tallest:
            continue
        support = obj.get("support", {}) if isinstance(obj.get("support"), dict) else {}
        floor_supported = _text(support.get("kind")) in FLOOR_SUPPORTED
        ground = _num(obj.get("ground_height_m")) or 0.0
        # An anchor often names two landmarks, "just above the hip, a little
        # below her waist". Take the one it leads with: that is the claim.
        named = sorted(
            ((anchor.find(word), word, fraction)
             for word, fraction in BODY_LANDMARK_FRACTION.items()
             if word in anchor),
        )
        referent = anchor_person(anchor, subjects)
        for _, word, fraction in named[:1]:
            if not floor_supported:
                # height_m is the thing's own length, not a height above a floor.
                break
            if anchor_is_about_extent(anchor, word):
                break
            if referent is None:
                break
            stature = _num(referent.get("height_m"))
            if not stature:
                break
            expected = fraction * stature
            if abs((obj_height + ground) - expected) > LANDMARK_TOLERANCE_M:
                errors.append(
                    f"object {_text(obj.get('id'))}: scale_anchor says it reaches the "
                    f"{word} of {_noun(referent)}, who is {stature:g} m, so that is "
                    f"{expected:.2f} m, but height_m is {obj_height:g}. Change the "
                    "height, the anchor, or the person it names."
                )
        if any(word in anchor for word in HAND_HELD_WORDS):
            if obj_height > tallest * TWO_HAND_FRACTION:
                errors.append(
                    f"object {_text(obj.get('id'))}: scale_anchor says it is held in a hand, "
                    f"but at {obj_height:g} m against a {tallest:g} m person it is a "
                    "two-handed load at best."
                )
            elif obj_height > tallest * ONE_HAND_FRACTION:
                warnings.append(
                    f"object {_text(obj.get('id'))}: at {obj_height:g} m it is large for the "
                    "one hand its scale_anchor describes."
                )

    # Object heights against code and settled convention, so a 1.2 m kitchen
    # counter or a 0.3 m stair riser is caught in the brief.
    for obj in objects:
        name = _text(obj.get("name"))
        height = _num(obj.get("height_m"))
        band = reference_height(name) if name else None
        if band and height:
            low, high, source = band
            if not low <= height <= high:
                errors.append(
                    f"object {_text(obj.get('id'))}: height_m {height:g} is outside the "
                    f"{low:g}-{high:g} m range for {name!r} ({source})."
                )

    for subject in subjects:
        if has_reference_image(subject) and not isinstance(
            (spec.get("location") or {}).get("reference"), dict
        ):
            errors.append(
                f"subject {_text(subject.get('id'))}: reference_image needs a "
                "location.reference block recording where the likeness comes from and on "
                "what basis it may be used. A person's face is not a free asset."
            )
        raised = _num(subject.get("ground_height_m"))
        if raised is not None and raised < 0:
            errors.append(
                f"subject {_text(subject.get('id'))}: ground_height_m cannot be negative; "
                "it is the height of the surface they stand on above the camera's floor."
            )

    # Camera height against angle and the people in frame.
    if photographic and cam_height is not None and eye_heights:
        mean_eye = sum(eye_heights) / len(eye_heights)
        eye_level_tolerance = 0.35 if standing_people(spec) else 0.15
        if angle == "eye_level" and abs(cam_height - mean_eye) > eye_level_tolerance:
            errors.append(
                f"spec.camera angle eye_level needs the lens near the eye height of the people "
                f"in frame (~{mean_eye:.2f} m); "
                f"height_m is {cam_height:g}."
            )
        if angle == "high" and cam_height <= mean_eye:
            errors.append("spec.camera angle high needs the lens above the subjects' eye height.")
        if angle in {"low", "worms_eye"} and cam_height >= mean_eye:
            errors.append("spec.camera angle low needs the lens below the subjects' eye height.")

    # Depth of field against an explicit background treatment.
    if photographic and focal and distance and aperture:
        near, far = depth_of_field(focal, aperture, distance)
        bg = _text(spec.get("background_focus"))
        bg_d = by_plane["background"]
        if bg == "sharp" and bg_d and max(bg_d) > far:
            errors.append(
                f"spec.background_focus sharp is impossible at f/{aperture:g}, {focal:g} mm, focus {distance:g} m: "
                f"focus ends near {far:.1f} m. Stop down or drop the sharp background."
            )
        if bg == "blurred" and bg_d and math.isinf(far):
            warnings.append("spec.background_focus blurred but the computed depth of field reaches infinity.")

    # Light.
    lighting = spec.get("lighting")
    if not isinstance(lighting, dict):
        errors.append("spec.lighting is required.")
        lighting = {}
    key = lighting.get("key")
    if not isinstance(key, dict):
        errors.append("spec.lighting.key {source, direction, quality} is required: exactly one key light.")
        key = {}
    else:
        _require(errors, bool(_text(key.get("source"))), "spec.lighting.key.source is required.")
        if _text(key.get("direction")) not in DIRECTIONS:
            errors.append("spec.lighting.key.direction must be one of " + ", ".join(sorted(DIRECTIONS)) + " (from the camera's view).")
        _require(errors, bool(_text(key.get("quality"))), "spec.lighting.key.quality is required (hard or soft and why).")
    if isinstance(lighting.get("key"), list):
        errors.append("spec.lighting.key must be one light; put others in spec.lighting.fill.")
    shadow = _text(lighting.get("shadow_direction"))
    key_dir = _text(key.get("direction")) if isinstance(key, dict) else ""
    if photographic and not shadow:
        errors.append("spec.lighting.shadow_direction is required for photographic media.")
    if shadow and key_dir in SHADOW_EXPECTED and shadow not in SHADOW_EXPECTED[key_dir]:
        errors.append(
            f"spec.lighting.shadow_direction {shadow!r} contradicts a key light from {key_dir!r}; "
            "shadows fall " + OPPOSITE[key_dir] + "."
        )
    quality = _text(key.get("quality")).lower() if isinstance(key, dict) else ""
    weather = _text(location.get("weather")).lower()
    if quality and weather and any(word in weather for word in DIFFUSE_WEATHER):
        if any(word in quality for word in HARD_WORDS) and not any(
            word in quality for word in SOFT_WORDS
        ):
            errors.append(
                f"spec.lighting.key.quality is hard, but the weather is {weather!r}. An "
                "overcast or rainy sky is the light source and it is the size of the sky, "
                "so its shadows are soft and open. Choose one."
            )
    for index, fill in enumerate(_list(lighting.get("fill"))):
        text = _text(fill).lower()
        if any(word in text for word in HARD_WORDS) and not any(
            word in text for word in SOFT_WORDS
        ):
            errors.append(
                f"spec.lighting.fill[{index}] describes a second hard light. A fill that "
                "casts its own shadow is a second key, and two keys give every object two "
                "shadows going different ways, which is the first thing a reader sees as "
                "wrong. Make it soft and lower in power, or put it in key and rewrite the "
                "scene around one light."
            )

    kelvin = _num(lighting.get("color_temperature_k"))
    time_of_day = _text(location.get("time_of_day")).lower().replace(" ", "_")
    key_source = _text(key.get("source")).lower() if isinstance(key, dict) else ""
    if kelvin and time_of_day in TIME_KELVIN and any(word in key_source for word in DAYLIGHT_SOURCES):
        low, high = TIME_KELVIN[time_of_day]
        if not low <= kelvin <= high:
            warnings.append(
                f"spec.lighting.color_temperature_k {kelvin:g} is unusual for daylight at {time_of_day} ({low}-{high} K)."
            )
    if time_of_day == "night" and any(word in key_source for word in ("sun", "daylight")):
        errors.append("spec.lighting.key.source is sunlight but location.time_of_day is night.")

    # Composition and overlays.
    composition = spec.get("composition")
    if not isinstance(composition, dict):
        errors.append("spec.composition is required (subject_placement, negative_space).")
        composition = {}
    else:
        _require(errors, bool(_text(composition.get("subject_placement"))), "spec.composition.subject_placement is required.")
        _require(errors, bool(_text(composition.get("negative_space"))), "spec.composition.negative_space is required (where the frame stays quiet for crops, title or logo).")

    # Both model families beautify unless told otherwise: skin loses pores,
    # clothes lose creases, rooms tidy themselves, backgrounds gain saturation.
    # A photograph of a real place has specific, placed flaws, and naming them is
    # the only thing that survives the prior.
    realism = spec.get("realism")
    if realism is not None and not isinstance(realism, dict):
        errors.append("spec.realism must be an object.")
        realism = None
    if photographic:
        imperfections = [
            _text(v) for v in _list((realism or {}).get("imperfections")) if _text(v)
        ]
        minimum = int(spec_policy.get("min_imperfections", 2))
        if len(imperfections) < minimum:
            errors.append(
                f"spec.realism.imperfections has {len(imperfections)} entries; a "
                f"photograph needs at least {minimum}. Name them and place them: a scuff "
                "on the counter edge by the till, flyaway hair at the left temple, one "
                "chair pushed out of line. An unplaced flaw is decoration; a placed one "
                "is what makes the frame read as a photograph rather than a render."
            )
        for index, value in enumerate(imperfections):
            if len(value.split()) < 4:
                warnings.append(
                    f"spec.realism.imperfections[{index}] is too short to be located; "
                    "say where it is as well as what it is."
                )

    for value, eid, name in collisions(spec):
        errors.append(
            f"spec.must_not_show {value!r} forbids {name!r}, which the spec also puts in "
            f"the picture as {eid}. The model would be given it twice, once as content "
            "and once as a prohibition. Decide whether it is in the frame or not."
        )

    text_in_image = _text(spec.get("text_in_image") or policy["text_default"] or "none")
    if text_in_image not in {"none", ""} and not policy["infographic_allowed"]:
        errors.append("spec.text_in_image must be none: the client has not enabled an infographic text workflow.")

    # Load limits: generators lose track of many people and objects.
    max_people = int(spec_policy.get("max_people", 4))
    if people_count(spec) > max_people:
        errors.append(
            f"spec shows {people_count(spec)} people; the client limit is {max_people}. "
            "Fewer people keeps anatomy and scale reliable."
        )
    max_objects = int(spec_policy.get("max_key_objects", 8))
    object_count = sum(int(_num(obj.get("count")) or 1) for obj in objects)
    if object_count > max_objects:
        warnings.append(
            f"spec shows {object_count} objects across {len(objects)} entries; above "
            f"{max_objects} generators drop, merge or duplicate them. A count of many "
            "identical things is still many things to draw."
        )

    if not _list(spec.get("physical_invariants")):
        warnings.append("spec.physical_invariants is empty: add the scene-specific facts a wrong picture would break.")
    return errors, warnings


# ---------------------------------------------------------------- compilation


def _sentence(text: str) -> str:
    text = " ".join(text.split()).strip(" ;,")
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text[0].upper() + text[1:]


def _fmt_m(value: float | None) -> str:
    if value is None:
        return ""
    if value < 1:
        return f"{value * 100:.0f} cm"
    return f"{value:g} m"


def _phrase_for(value: float, table: tuple[tuple[float, str], ...]) -> str:
    for threshold, phrase in table:
        if value <= threshold:
            return phrase
    return table[-1][1]


def negations(text: str) -> list[str]:
    """Every negation word in a prompt, which a positive prompt must not carry.

    Not negations, and so left alone: quoted lettering ('a sign reading "No
    Smoking"'), all-caps signage ("NO PARKING stencilled on the kerb"), a number
    ("the No. 9 bus"), a hyphenated compound ("a no-frills canteen") and "not
    only". Each is what the picture shows, not what it lacks. Raised by the
    rangsarn session from a review of its own lint.
    """
    masked = QUOTED_RE.sub(lambda m: " " * len(m.group(0)), text)
    found = set()
    for match in NEGATION_RE.finditer(masked):
        word = match.group(0)
        after = masked[match.end():]
        before = masked[:match.start()]
        if word.lower() == "no" and re.match(r"\.\s*\d", after):
            continue
        if re.match(r"-[A-Za-z]", after):
            continue
        if word.lower() == "not" and re.match(r"\s+only\b", after, re.I):
            continue
        if word.isupper() and len(word) > 1 and (
            re.match(r"\s+[A-Z]{2,}\b", after) or re.search(r"\b[A-Z]{2,}\s+$", before)
        ):
            continue
        found.add(word.lower())
    return sorted(found)


def similes(text: str) -> list[str]:
    """Comparisons a generator will draw as the thing compared."""
    lowered = text.lower()
    found = set()
    skip = {m.span() for m in LOOKS_LIKE_RE.finditer(text)}
    for match in SIMILE_RE.finditer(text):
        word = match.group(0).lower()
        start = max(0, match.start() - 12)
        if any(ok in lowered[start:match.end() + 4] for ok in SIMILE_EXEMPT):
            continue
        if any(a <= match.start() and match.end() <= b for a, b in skip):
            continue
        found.add(word)
    return sorted(found)


def boosters(text: str) -> list[str]:
    """Quality-booster words, which buy nothing and cost fidelity."""
    found = {" ".join(m.group(0).lower().split()) for m in BOOSTER_RE.finditer(text)}
    for item in LIST_ITEM_SPLIT_RE.split(text):
        match = LIST_BOOSTER_RE.fullmatch(item.strip(" .:!?()[]\"'"))
        if match:
            found.add(" ".join(match.group(1).lower().split()))
    return sorted(found)


def boosted_fields(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Spec fields reaching for a booster word instead of a fact."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in NEGATION_EXEMPT_KEYS or key in AUDIT_ONLY_KEYS:
                continue
            found.extend(boosted_fields(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(boosted_fields(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for word in boosters(value):
            found.append((path or "<root>", word))
    return found


def _no(item: str) -> str:
    """``no`` before an avoid entry, without "no a doctor's coat" or "no no"."""
    text = item.strip()
    if re.match(r"(?:no|none of)\b", text, re.I):
        return text
    return "no " + re.sub(r"^(?:a|an|the)\s+", "", text, flags=re.I)


def _an(word: str) -> str:
    """``a`` or ``an`` for the word that follows, so compiled prose reads cleanly."""
    return "an" if word[:1].lower() in "aeiou" else "a"


def _cap(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def _and_list(items: list[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``: a list a sentence can carry."""
    items = [item for item in items if item]
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def _noun(entity: dict[str, Any], article: str = "the") -> str:
    """A short noun phrase for an entity, for readable prompt and question text."""
    name = _text(entity.get("short_name"))
    if not name:
        name = _text(entity.get("name")) or _text(entity.get("description")) or _text(entity.get("id"))
    name = name.strip()
    first = name.split(" ", 1)[0].lower() if name else ""
    if not article or first in {"the", "a", "an"}:
        return name
    return f"{article} {name}"


def _entity_name(spec: dict[str, Any], eid: str) -> str:
    for _, entity in _entities(spec):
        if _text(entity.get("id")) == eid:
            return _noun(entity)
    return eid


MAX_MEASURABLE_RATIO = 8.0

SIZE_WORDS = (
    (1.8, "much larger in the frame than"),
    (1.25, "clearly larger in the frame than"),
    (1.08, "slightly larger in the frame than"),
    (0.93, "about the same height in the frame as"),
    (0.8, "slightly smaller in the frame than"),
    (0.56, "clearly smaller in the frame than"),
    (0.0, "much smaller in the frame than"),
)


def _size_word(ratio: float) -> str:
    for threshold, phrase in SIZE_WORDS:
        if ratio >= threshold:
            return phrase
    return SIZE_WORDS[-1][1]


DEFAULT_AVOID = [
    "text, letters, numbers, captions or signage that was not specified",
    "logos, brand marks, watermarks or signatures",
    "extra, missing or fused fingers, limbs or joints",
    "duplicated people or objects, or a person merged into an object",
    "objects floating without visible support",
    "shadows that disagree with the light direction, or a second sun",
    "warped or bent straight lines in walls, tiles, frames or furniture",
    "people or objects whose size does not match their distance",
]

# Output order of the clause groups. The picture's subject and action come first
# because every model weights the opening of a prompt most heavily; the physics
# closing line comes last so it is never the clause a length limit cuts.
GROUP_ORDER = (
    "opening",
    "subject",
    "object",
    "layout",
    "camera",
    "scale",
    "light",
    "composition",
    "style",
    "locale",
    "invariant",
    "realism",
    "constraint",
    "closing",
)

MEDIUM_WORDS = {
    "photograph": "A realistic editorial photograph",
    "3d_render": "A physically based 3D render",
    "illustration": "An editorial illustration",
    "flat_vector": "A flat vector illustration",
    "infographic_base": "A clean infographic background plate",
}


def _budget(clauses: list[dict[str, Any]], max_words: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Trim the lowest-priority clauses until the prompt fits the word budget.

    Models stop honouring a prompt long before it runs out of tokens, so a spec
    richer than the budget loses its least load-bearing detail first and says so,
    instead of silently producing a prompt the model reads only the start of.
    """
    if max_words <= 0:
        return clauses, []
    kept = list(clauses)
    dropped: list[dict[str, Any]] = []

    def words(items: list[dict[str, Any]]) -> int:
        return sum(len(item["text"].split()) for item in items)

    while words(kept) > max_words:
        worst = max(
            range(len(kept)),
            key=lambda index: (kept[index]["tier"], index),
        )
        if kept[worst]["tier"] <= 1:
            break
        dropped.append(kept.pop(worst))
    return kept, dropped


def build_clauses(
    spec: dict[str, Any],
    derived: dict[str, Any],
    width: int,
    height: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Every sentence of the prompt, each tagged with its group and its priority.

    Tier 1 clauses are the picture: medium, subject, action, hands, camera, key
    light, the quiet area and the physics closing line. Tier 4 clauses are the
    ones a length budget can take away without changing what is in the frame.
    """
    clauses: list[dict[str, Any]] = []

    def add(group: str, tier: int, text: str) -> None:
        sentence = _sentence(text)
        if sentence:
            clauses.append({"group": group, "tier": tier, "text": sentence})

    camera = spec["camera"]
    location = spec["location"]
    lighting = spec["lighting"]
    composition = spec["composition"]
    medium = _text(spec.get("medium") or "photograph")
    photographic = medium in PHOTOGRAPHIC_MEDIA
    style = spec.get("style", {}) if isinstance(spec.get("style"), dict) else {}
    subjects = [s for s in _list(spec.get("subjects")) if isinstance(s, dict)]
    objects = [o for o in _list(spec.get("objects")) if isinstance(o, dict)]

    # opening -----------------------------------------------------------------
    look = _text(style.get("look"))
    add(
        "opening",
        1,
        f"{MEDIUM_WORDS[medium]}, {derived['orientation']} {width}x{height}"
        + (f", {look}" if look else "")
        + f", showing {_text(spec['purpose'])}",
    )
    # A viewpoint below or above the subject is the single hardest thing to get a
    # generator to honour: models carry a strong eye-level prior and a request for
    # an angle is among the weakest-followed parts of a prompt. So when the spec
    # asks for one, it is said in visual terms, in the opening, where the model
    # weights it most, rather than left to a camera-height figure further down.
    raised = [
        crossing
        for crossing in derived.get("horizon_crossings", [])
        if crossing.get("below_feet") or crossing["fraction_of_height_from_feet"] < 0.35
    ]
    lowered = [
        crossing
        for crossing in derived.get("horizon_crossings", [])
        if crossing.get("above_head")
    ]
    if raised:
        names = _and_list([_entity_name(spec, crossing["id"]) for crossing in raised[:3]])
        add(
            "opening",
            1,
            f"The camera is lower than {names} and looks up: the undersides of the chin, "
            "the arms and the feet are visible, the body narrows toward the head, and "
            "whatever they stand on is seen from beneath its edge",
        )
    elif lowered:
        names = _and_list([_entity_name(spec, crossing["id"]) for crossing in lowered[:3]])
        add(
            "opening",
            1,
            f"The camera is higher than {names} and looks down: the tops of the head and "
            "shoulders are visible and the ground is seen spreading away behind them",
        )
    scene = f"The scene is {_text(location.get('place'))} in {_text(location.get('locale'))}"
    if _text(location.get("time_of_day")):
        scene += f", {_text(location['time_of_day']).replace('_', ' ')}"
    if _text(location.get("weather")):
        scene += f", {_text(location['weather'])}"
    add("opening", 1, scene)

    # subjects ----------------------------------------------------------------
    for subject in subjects:
        count = int(_num(subject.get("count")) or 1)
        noun = _noun(subject)
        who = _text(subject.get("description"))
        if has_reference_image(subject):
            line = (
                (f"{count} " if count > 1 else "One ")
                + f"{who}, the person from the reference image"
            )
        else:
            line = (f"{count} " if count > 1 else "One ") + who
            if _text(subject.get("appearance")):
                line += f", {_text(subject['appearance'])}"
        if _text(subject.get("wardrobe")):
            line += f", wearing {_text(subject['wardrobe'])}"
        line += f", {_text(subject.get('position'))}"
        add("subject", 1, line)
        if has_reference_image(subject):
            add("subject", 1, f"For {noun}, {IDENTITY_LOCK}")
        actor = "They" if count > 1 else _cap(noun)
        add("subject", 1, f"{actor} {_text(subject.get('action'))}")
        if _text(subject.get("hands")):
            add("subject", 1, f"Hands of {noun}: {_text(subject['hands'])}")
        if _text(subject.get("pose")):
            add("subject", 2, f"Pose of {noun}: {_text(subject['pose'])}")
        if _text(subject.get("gaze")):
            add("subject", 2, f"{_cap(noun)} looks {_text(subject['gaze'])}")
        if _text(subject.get("expression")):
            add("subject", 3, f"Expression of {noun}: {_text(subject['expression'])}")

    # objects -----------------------------------------------------------------
    for obj in objects:
        count = int(_num(obj.get("count")) or 1)
        line = (f"{count} " if count > 1 else "") + _text(obj.get("name"))
        if _text(obj.get("size")):
            line += f", {_text(obj['size'])}"
        if _text(obj.get("material")):
            line += f", {_text(obj['material'])}"
        if _text(obj.get("state")):
            line += f", {_text(obj['state'])}"
        line += f", {_text(obj.get('position'))}"
        support = obj.get("support", {}) if isinstance(obj.get("support"), dict) else {}
        by = _text(support.get("by"))
        by_name = _entity_name(spec, by) if by in {_text(e.get("id")) for _, e in _entities(spec)} else by
        kind = _text(support.get("kind"))
        line += f", {SUPPORT_PARTICIPLE.get(kind, kind.replace('_', ' '))} {by_name}"
        add("object", 1, line)
        if obj.get("extends_beyond_frame"):
            add(
                "object",
                2,
                f"{_cap(_noun(obj))} runs past both edges of the frame and is cut by them, "
                "so the frame holds a section of its length and both ends lie outside it",
            )
        if _text(obj.get("scale_anchor")):
            add("object", 2, f"For scale, {_text(obj['scale_anchor'])}")

    layout = spec.get("spatial_layout", {}) if isinstance(spec.get("spatial_layout"), dict) else {}
    for plane in PLANES:
        if _text(layout.get(plane)):
            add("layout", 3, f"{plane.capitalize()}: {_text(layout[plane])}")

    # camera ------------------------------------------------------------------
    if photographic:
        focal = _num(camera["focal_length_mm"])
        aperture = _num(camera["aperture_f"])
        shot = _text(camera["shot_type"])
        framing = SHOT_FRAMING.get(shot, "")
        add(
            "camera",
            1,
            f"{_an(shot)} {shot.replace('_', ' ')} shot"
            + (f", {framing}" if framing else "")
            + f", from {_an(_text(camera['angle']))} {_text(camera['angle']).replace('_', ' ')} angle, "
            f"the lens {_fmt_m(_num(camera['height_m']))} above the floor and held "
            f"{_text(camera.get('tilt') or 'level').replace('_', ' ')}",
        )
        add(
            "camera",
            1,
            f"Shot on a full-frame camera with a {focal:g} mm lens, "
            f"{_phrase_for(focal, FOCAL_PHRASES)}, at f/{aperture:g}, "
            f"{_phrase_for(aperture, APERTURE_PHRASES)}, focused on "
            f"{_entity_name(spec, _text(camera['focus_on']))}",
        )
        horizon = _text(camera.get("horizon"))
        if horizon not in HORIZON_IN_FRAME:
            where = {
                "above_frame": "above the top edge",
                "below_frame": "below the bottom edge",
            }.get(horizon, "outside the picture")
            add(
                "camera",
                1,
                f"The eye-level line falls {where}, and every receding line still "
                "converges consistently for this one viewpoint",
            )
        else:
            add(
                "camera",
                1,
                f"The horizon and eye-level line sit across the {horizon.replace('_', ' ')} of the frame, "
                "parallel edges converge to vanishing points on that line, and verticals stay vertical",
            )
        if (
            derived.get("camera_at_eye_height")
            and _text(camera.get("horizon")) in HORIZON_IN_FRAME
            and standing_people(spec)
        ):
            add(
                "camera",
                2,
                "The camera stands at the eye height of the standing people, so that "
                "horizon line crosses their eyes",
            )
        else:
            for crossing in derived.get("horizon_crossings", [])[:2]:
                name = _entity_name(spec, crossing["id"])
                if crossing.get("below_feet"):
                    add(
                        "camera",
                        2,
                        f"{_cap(name)} stands {crossing['stands_on_m']:g} m above the floor the "
                        "camera is on, so the eye-level line passes below their feet and the "
                        "whole figure is seen from below",
                    )
                elif crossing["above_head"]:
                    add("camera", 2, f"That horizon line passes above the head of {name}")
                else:
                    percent = round(crossing["fraction_of_height_from_feet"] * 100)
                    add(
                        "camera",
                        2,
                        f"That horizon line crosses {name} about {percent} per cent of the "
                        "way up from the feet",
                    )
        soft = derived.get("outside_focus", [])
        focus_name = _entity_name(spec, _text(camera.get("focus_on")))
        if soft:
            add(
                "camera",
                2,
                f"{_cap(focus_name)} is the sharpest thing in the frame; "
                + ", ".join(_entity_name(spec, eid) for eid in soft)
                + " fall progressively softer the further they are from that focus plane",
            )
        else:
            add("camera", 3, f"{_cap(focus_name)} carries the sharpest detail")
    else:
        add(
            "camera",
            1,
            f"Viewpoint: {_an(_text(camera.get('shot_type')))} "
            f"{_text(camera.get('shot_type')).replace('_', ' ')} framing from "
            f"{_an(_text(camera.get('angle')))} {_text(camera.get('angle')).replace('_', ' ')} angle",
        )

    # scale -------------------------------------------------------------------
    for pair in derived.get("scale_notes", []):
        add("scale", 2, pair)

    # light -------------------------------------------------------------------
    key = lighting["key"]
    light = (
        f"Key light: {_text(key['source'])} from the {_text(key['direction']).replace('_', ' ')} "
        f"of the frame, {_text(key['quality'])}"
    )
    kelvin = _num(lighting.get("color_temperature_k"))
    if kelvin:
        light += f", {_phrase_for(kelvin, KELVIN_PHRASES)} at about {kelvin:g} K"
    add("light", 1, light)
    shadow = _text(lighting.get("shadow_direction"))
    if shadow:
        add(
            "light",
            1,
            f"Every shadow falls {shadow.replace('_', ' ')} from that one key light, and every "
            "person and object touching a surface has a soft contact shadow where they meet",
        )
    for fill in _list(lighting.get("fill")):
        if _text(fill):
            add("light", 3, f"Fill: {_text(fill)}")

    # composition -------------------------------------------------------------
    add("composition", 1, f"Composition: {_text(composition['subject_placement'])}")
    add(
        "composition",
        1,
        f"The frame stays quiet in {_text(composition['negative_space'])}, even enough to "
        "carry a headline laid over it later",
    )
    if _text(composition.get("crop_safety")):
        add("composition", 3, f"Crop safety: {_text(composition['crop_safety'])}")

    # style, locale, invariants ----------------------------------------------
    for field in ("color_palette", "mood", "texture"):
        if _text(style.get(field)):
            add("style", 3, f"{field.replace('_', ' ').capitalize()}: {_text(style[field])}")
    for rule in policy["style_prompt_rules"]:
        if _text(rule):
            add("style", 2, _text(rule))

    details = [_text(v) for v in _list(location.get("locale_details")) if _text(v)]
    if details:
        add("locale", 1, "Local details that must be right: " + "; ".join(details))
    reference = reference_block(spec)
    facts = [_text(v) for v in _list(reference.get("verified_facts")) if _text(v)]
    if facts:
        add(
            "locale",
            1,
            f"This is {_text(reference.get('place_name'))}, a real place, and these "
            "things about it are established: " + "; ".join(facts),
        )

    invariants = [_text(v) for v in _list(spec.get("physical_invariants")) if _text(v)]
    if invariants:
        add("invariant", 2, "Physically and logically: " + "; ".join(invariants))

    realism = spec.get("realism", {}) if isinstance(spec.get("realism"), dict) else {}
    flaws = [_text(v) for v in _list(realism.get("imperfections")) if _text(v)]
    if flaws:
        add(
            "realism",
            1,
            "This is a photograph of a real place and it carries the marks of use: "
            + "; ".join(flaws),
        )

    # constraints and closing -------------------------------------------------
    if _text(spec.get("text_in_image") or "none") == "none":
        # Stated as the state of the scene, not as a prohibition, because a
        # prohibition in a positive prompt tends to produce the thing it forbids.
        add(
            "constraint",
            1,
            "Any lettering this place would really carry sits small, soft and out of "
            "focus, too indistinct to read as words",
        )
    add(
        "closing",
        1,
        "Everything obeys real-world physics: one camera viewpoint, every size consistent "
        "with its distance, every object resting on or held by something, and hands with "
        "five fingers each that close around what they hold",
    )
    return clauses


def compile_spec(
    spec: dict[str, Any],
    width: int,
    height: int,
    config: dict[str, Any] | None = None,
    target: str = "",
) -> dict[str, Any]:
    """Compile a validated spec into prompt, avoid list and review questions.

    ``target`` says where the avoid list may go: ``negative_prompt`` for a model
    with a real negative channel, ``inline_constraints`` for one whose vendor
    prescribes an inline Constraints block, ``none`` for one that has neither and
    whose vendor says to describe the positive state instead. Left empty, it comes
    from the registry entry for ``images.spec.target_model``.
    """
    errors, warnings = validate_spec(spec, width, height, config)
    if errors:
        raise ValueError("spec is invalid:\n- " + "\n- ".join(errors))
    policy = policy_from_config(config or {})
    model = target_model_policy(config or {})
    spec_policy = policy["spec"]
    if not target and model.get("prompt_target"):
        target = _text(model["prompt_target"])
    target = TARGET_ALIASES.get(target or "negative_prompt", target or "negative_prompt")
    if target not in PROMPT_TARGETS:
        raise ValueError("target must be one of " + ", ".join(sorted(PROMPT_TARGETS)) + ".")
    derived = derive(spec, width, height)

    avoid: list[str] = []
    seen: set[str] = set()
    for value in (
        _list(spec.get("must_not_show"))
        + policy["style_negative_rules"]
        + _list(policy["spec"].get("default_avoid", DEFAULT_AVOID))
    ):
        text = _text(value)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            avoid.append(text)

    clauses = build_clauses(spec, derived, width, height, policy)

    # The scene clauses are checked for negation before any Constraints block is
    # added, because that block is the one place a negation belongs.
    scene_prompt = " ".join(clause["text"] for clause in clauses)
    found = negations(scene_prompt)
    if found:
        raise ValueError(
            "the compiled prompt describes the scene with negation ("
            + ", ".join(found)
            + "). Describe the state the picture is in instead, and put exclusions in "
            "must_not_show, which reaches the avoid list. A negation in a positive "
            "prompt tends to produce the thing it forbids."
        )
    constraints = ""
    if target == "inline_constraints":
        constraints = "Constraints: " + "; ".join(_no(item) for item in avoid) + "."
    max_words = spec_policy.get("max_prompt_words")
    if max_words in (None, "") and model:
        max_words = model.get("max_prompt_words")
    max_words = int(max_words or 0)
    kept, dropped = _budget(clauses, max_words)
    order = {group: index for index, group in enumerate(GROUP_ORDER)}
    kept.sort(key=lambda clause: order.get(clause["group"], len(order)))
    prompt = " ".join(clause["text"] for clause in kept)
    if constraints:
        prompt = f"{prompt} {constraints}"
    if dropped:
        warnings.append(
            f"prompt was trimmed to the {max_words}-word budget; "
            f"{len(dropped)} lower-priority sentences were left out: "
            + "; ".join(clause["group"] for clause in dropped)
        )
    words = len(prompt.split())
    if max_words and words > max_words:
        warnings.append(
            f"the {max_words}-word budget could not be met: the clauses that cannot be "
            f"dropped without changing what is in the frame run to {words} words. This "
            "generator will read only the opening of the prompt, so either simplify the "
            "scene, split it across fewer subjects and objects, or target a model that "
            "rewards detail."
        )

    questions = build_questions(spec, derived)
    return {
        "prompt": prompt,
        "prompt_words": len(prompt.split()),
        "negative_prompt": ", ".join(avoid) if target == "negative_prompt" else "",
        "avoid": avoid,
        "derived": derived,
        "questions": questions,
        "warnings": warnings,
        "dropped_clauses": [clause["text"] for clause in dropped],
        "target": target,
        "target_model": _text(spec_policy.get("target_model")),
    }


def build_questions(spec: dict[str, Any], derived: dict[str, Any]) -> list[dict[str, Any]]:
    """Atomic yes/no questions from the spec, each answerable by looking at the image.

    Questions follow the scene-graph idea: entities first, then their attributes,
    relations and actions, then camera, light and constraints. A child question only
    makes sense when its parent entity question is answered yes. Each one asks about
    a single fact, because a reviewer or a vision model answering a compound question
    answers the half it noticed.
    """
    questions: list[dict[str, Any]] = []

    def add(
        qid: str,
        group: str,
        text: str,
        parent: str = "",
        verify_with: str = "",
    ) -> None:
        question = {
            "id": qid,
            "group": group,
            "question": " ".join(text.split()),
            "parent": parent,
        }
        if verify_with:
            # Three kinds of question are routed away from judgement. Counting and
            # rendered text are what a vision model gets wrong often enough to be
            # useless: 67.4 per cent on counting and 13.7 to 24.9 per cent on text,
            # where it answers yes almost whenever any text is present at all (Cho
            # et al., DSG, ICLR 2024, arXiv:2310.18235). Shot size, camera angle,
            # lens and lighting are the third: the best of 24 vision models averaged
            # under 60 per cent, with camera angle at 51 to 58 and lens at 44 to 49
            # (ShotBench, arXiv:2506.21356). Measure those on the image instead.
            question["verify_with"] = verify_with
        questions.append(question)

    for subject in [s for s in _list(spec.get("subjects")) if isinstance(s, dict)]:
        sid = _text(subject.get("id"))
        noun = _noun(subject)
        count = int(_num(subject.get("count")) or 1)
        base = f"q_{sid}"
        add(
            base,
            "entity",
            f"Does the image show exactly {count} {_text(subject.get('description'))}?",
            verify_with="count",
        )
        if has_reference_image(subject):
            add(
                f"{base}_identity",
                "attribute",
                f"Is {noun} recognisably the same person as the reference image, in the "
                "face, the bone structure and every identifying mark?",
                base,
            )
        for field, lead in (
            ("appearance", "look like this"),
            ("wardrobe", "wear this"),
            ("position", "stand here in the frame"),
        ):
            if _text(subject.get(field)):
                add(
                    f"{base}_{field}",
                    "attribute",
                    f"Does {noun} {lead}: {_text(subject[field])}?",
                    base,
                )
        add(
            f"{base}_action",
            "action",
            f"Is {noun} doing this: {_text(subject.get('action'))}?",
            base,
        )
        if _text(subject.get("pose")):
            add(
                f"{base}_pose",
                "anatomy",
                f"Does the body of {noun} hold this pose, with joints that bend the way a "
                f"body bends: {_text(subject['pose'])}?",
                base,
            )
        if _text(subject.get("hands")):
            # One question asking four things at once gets resolved on whichever
            # one the reader noticed. Measured on a real scene, the compound form
            # returned cannot_tell on a framing technicality without ever
            # reaching the defect; atomic questions on the same crops returned
            # none and named four real faults.
            add(
                f"{base}_hands_action",
                "anatomy",
                f"Do the hands of {noun} do this: {_text(subject['hands'])}?",
                base,
            )
            add(
                f"{base}_hands_count",
                "anatomy",
                f"Does every hand of {noun} that is visible have five fingers, counting "
                "the thumb, with no finger hidden behind another?",
                base,
                verify_with="count",
            )
            add(
                f"{base}_hands_joints",
                "anatomy",
                f"Do the fingers of {noun} bend only at the knuckles, in the direction a "
                "finger bends?",
                base,
            )
            add(
                f"{base}_hands_thumb",
                "anatomy",
                f"Is the thumb of each visible hand of {noun} on the inner side, where a "
                "thumb is?",
                base,
            )
            add(
                f"{base}_hands_proportion",
                "anatomy",
                f"Is each hand of {noun} the right size for the wrist and forearm it is "
                "attached to?",
                base,
            )
        if _text(subject.get("gaze")):
            add(
                f"{base}_gaze",
                "anatomy",
                f"Do both eyes of {noun} point here: {_text(subject['gaze'])}?",
                base,
            )
        height = _num(subject.get("height_m"))
        if height:
            add(
                f"{base}_height",
                "scale",
                f"Does {noun} read as {_fmt_m(height)} tall against the other things in the frame?",
                base,
            )

    for obj in [o for o in _list(spec.get("objects")) if isinstance(o, dict)]:
        oid = _text(obj.get("id"))
        noun = _noun(obj)
        count = int(_num(obj.get("count")) or 1)
        base = f"q_{oid}"
        add(
            base,
            "entity",
            f"Does the image show exactly {count} {_text(obj.get('name'))}?",
            verify_with="count",
        )
        if _text(obj.get("size")) or _text(obj.get("scale_anchor")):
            add(
                f"{base}_scale",
                "scale",
                f"Is {noun} the right size: {_text(obj.get('size'))}"
                + (f", so that {_text(obj['scale_anchor'])}" if _text(obj.get("scale_anchor")) else "")
                + "?",
                base,
            )
        support = obj.get("support", {}) if isinstance(obj.get("support"), dict) else {}
        by = _text(support.get("by"))
        by_name = _entity_name(spec, by) if by else ""
        kind = _text(support.get("kind"))
        add(
            f"{base}_support",
            "physics",
            f"Is {noun} visibly {SUPPORT_PARTICIPLE.get(kind, kind.replace('_', ' '))} "
            f"{by_name}, with contact and a contact shadow where they meet?",
            base,
        )
        add(f"{base}_position", "spatial", f"Is {noun} placed here: {_text(obj.get('position'))}?", base)
        if _text(obj.get("material")):
            add(
                f"{base}_material",
                "attribute",
                f"Does {noun} read as {_text(obj['material'])}?",
                base,
            )
        if _text(obj.get("state")):
            add(f"{base}_state", "attribute", f"Is {noun} {_text(obj['state'])}?", base)

    camera = spec.get("camera", {}) if isinstance(spec.get("camera"), dict) else {}
    shot = _text(camera.get("shot_type"))
    focus_id = _text(camera.get("focus_on"))
    focus_is_person = any(
        _text(subject.get("id")) == focus_id
        and _text(subject.get("kind") or "person") == "person"
        for subject in _list(spec.get("subjects"))
        if isinstance(subject, dict)
    )
    focus_label = _entity_name(spec, focus_id) if focus_id else "the main subject"
    if shot in SHOT_FRAMING and focus_is_person:
        add(
            "q_camera_framing",
            "camera",
            f"Is {focus_label} framed like this: {SHOT_FRAMING[shot]}?",
            verify_with="geometry",
        )
    elif shot in SHOT_FRAMING:
        # Body-fraction framing means nothing for a desk or an empty room.
        add(
            "q_camera_framing",
            "camera",
            f"Is the view {_an(shot)} {shot.replace('_', ' ')} shot of {focus_label}?",
            verify_with="geometry",
        )
    else:
        add(
            "q_camera_framing",
            "camera",
            f"Is the view {_an(shot)} {shot.replace('_', ' ')} shot?",
            verify_with="geometry",
        )
    angle = _text(camera.get("angle"))
    add(
        "q_camera_angle",
        "camera",
        f"Is the camera at {_an(angle)} {angle.replace('_', ' ')} angle to the main subject?",
        verify_with="geometry",
    )
    horizon = _text(camera.get("horizon"))
    if horizon in HORIZON_IN_FRAME:
        add(
            "q_horizon",
            "camera",
            f"Does the horizon or eye-level line sit across the {horizon.replace('_', ' ')} "
            "of the frame, level, with receding parallel edges meeting on it?",
            verify_with="geometry",
        )
    if (
        derived.get("camera_at_eye_height")
        and horizon in HORIZON_IN_FRAME
        and standing_people(spec)
    ):
        add(
            "q_eye_line",
            "camera",
            "Does that horizon line cross the eyes of the standing people, as a camera at "
            "their eye height requires?",
            verify_with="geometry",
        )
    focus = _text(camera.get("focus_on"))
    if focus:
        add(
            "q_focus",
            "optics",
            f"Is {_entity_name(spec, focus)} the sharpest thing in the frame?",
        )
    for eid in derived.get("outside_focus", []):
        add(
            f"q_soft_{eid}",
            "optics",
            f"Is {_entity_name(spec, eid)} clearly out of focus, with its edges blurred and "
            "any fine detail or lettering on it unreadable, as its distance from the "
            "focus plane requires?",
        )
    fits = derived.get("fits_in_frame", {})
    measurable = [
        ratio
        for ratio in derived.get("apparent_ratios", [])
        if fits.get(ratio["a"], True) and fits.get(ratio["b"], True)
    ]
    # Past about 8:1 either way a frame-height ratio cannot be read off an image,
    # and a question nobody can answer only adds cannot_tell.
    measurable = [
        ratio
        for ratio in measurable
        if 1 / MAX_MEASURABLE_RATIO <= ratio["a_to_b_apparent_height"] <= MAX_MEASURABLE_RATIO
    ]
    for ratio in measurable[:6]:
        add(
            f"q_ratio_{ratio['a']}_{ratio['b']}",
            "scale",
            f"Does {_entity_name(spec, ratio['a'])} measure about "
            f"{ratio['a_to_b_apparent_height']} times the frame height of "
            f"{_entity_name(spec, ratio['b'])}, as their distances require?",
            verify_with="geometry",
        )

    lighting = spec.get("lighting", {}) if isinstance(spec.get("lighting"), dict) else {}
    key = lighting.get("key", {}) if isinstance(lighting.get("key"), dict) else {}
    fills = [_text(f) for f in _list(lighting.get("fill")) if _text(f)]
    add(
        "q_light",
        "light",
        f"Is every person and object lit mainly from the "
        f"{_text(key.get('direction')).replace('_', ' ')} by {_text(key.get('source'))}, "
        "with the shaded side on the opposite side?"
        + (
            " A softer, weaker fill is declared as well ("
            + "; ".join(fills)
            + ") and is expected: it lifts the shadows without casting its own."
            if fills
            else ""
        ),
    )
    if _text(lighting.get("shadow_direction")):
        add(
            "q_shadows",
            "light",
            f"Do all shadows fall {_text(lighting['shadow_direction']).replace('_', ' ')} with "
            "lengths that match one light height?",
        )

    # Cross-entity questions. Generated scenes are locally consistent and
    # globally not: Farid measured 25 of 25 kitchens whose floor-tile vanishing
    # point disagreed with the counter top, and 25 of 25 sunlit scenes whose
    # shadows no single light position could explain (arXiv:2206.14617). So the
    # question that finds the failure compares two entities; one asking whether a
    # single entity looks right will pass.
    ground = []
    for kind, entity in _entities(spec):
        if kind == "subject":
            if _text(entity.get("posture") or "standing").lower() in EYE_FRACTION:
                ground.append(entity)
            continue
        support = entity.get("support", {}) if isinstance(entity.get("support"), dict) else {}
        if _text(support.get("kind")) in GROUNDED_SUPPORT:
            ground.append(entity)
    for index in range(len(ground) - 1):
        a, b = ground[index], ground[index + 1]
        add(
            f"q_pair_shadow_{_text(a.get('id'))}_{_text(b.get('id'))}",
            "physics",
            f"Do the shadows of {_noun(a)} and {_noun(b)} run in the same direction, as "
            "one light position requires?",
        )
    if len(ground) > 1:
        add(
            "q_pair_ground_plane",
            "geometry",
            "Do "
            + _and_list([_noun(entity) for entity in ground[:4]])
            + " all sit on one floor that recedes consistently, rather than on separate "
            "invisible shelves?",
        )
    horizon_in_frame = horizon in HORIZON_IN_FRAME
    for crossing in derived.get("horizon_crossings", []):
        name = _entity_name(spec, crossing["id"])
        if not horizon_in_frame:
            # The spec puts the horizon out of shot, so there is no line to
            # measure against. Ask for the thing that is still visible: whether
            # the figure is seen from below or above.
            if crossing.get("below_feet") or crossing["fraction_of_height_from_feet"] < 0.35:
                add(
                    f"q_viewpoint_{crossing['id']}",
                    "geometry",
                    f"Is {name} seen from below, so that the undersides of the chin, arms "
                    "and feet show and the body narrows toward the head?",
                    verify_with="geometry",
                )
            elif crossing["above_head"]:
                add(
                    f"q_viewpoint_{crossing['id']}",
                    "geometry",
                    f"Is {name} seen from above, so that the tops of the shoulders and head "
                    "show and the feet are the furthest part away?",
                    verify_with="geometry",
                )
            continue
        if crossing.get("below_feet"):
            add(
                f"q_horizon_cut_{crossing['id']}",
                "geometry",
                f"Is {name} seen from below, with the eye-level line passing beneath their "
                f"feet, as standing {crossing['stands_on_m']:g} m above the camera's floor "
                "requires?",
                verify_with="geometry",
            )
        elif crossing["above_head"]:
            add(
                f"q_horizon_cut_{crossing['id']}",
                "geometry",
                f"Does the horizon pass above the head of {name}, as a camera higher than "
                "they are tall requires?",
                verify_with="geometry",
            )
        else:
            percent = round(crossing["fraction_of_height_from_feet"] * 100)
            add(
                f"q_horizon_cut_{crossing['id']}",
                "geometry",
                f"Does the horizon cross {name} about {percent} per cent of the way up "
                "from the feet, measured on the image?",
                verify_with="geometry",
            )

    composition = spec.get("composition", {}) if isinstance(spec.get("composition"), dict) else {}
    if _text(composition.get("negative_space")):
        add(
            "q_negative_space",
            "composition",
            f"Is {_text(composition['negative_space'])} quiet enough to carry a headline?",
        )
    if _text(composition.get("crop_safety")):
        add(
            "q_crop_safety",
            "composition",
            f"Does this hold: {_text(composition['crop_safety'])}?",
        )

    location = spec.get("location", {}) if isinstance(spec.get("location"), dict) else {}
    for index, detail in enumerate(_list(location.get("locale_details")), start=1):
        add("q_locale_%02d" % index, "locale", f"Is this local detail right: {_text(detail)}?")
    reference = reference_block(spec)
    place_name = _text(reference.get("place_name"))
    for index, fact in enumerate(_list(reference.get("verified_facts")), start=1):
        add(
            "q_reference_%02d" % index,
            "reference",
            f"Does the image match this established fact about {place_name}: "
            f"{_text(fact)}?",
        )
    for index, inv in enumerate(_list(spec.get("physical_invariants")), start=1):
        add("q_invariant_%02d" % index, "physics", f"Does the image respect this: {_text(inv)}?")
    for index, flaw in enumerate(_list((spec.get("realism") or {}).get("imperfections")), start=1):
        add(
            "q_imperfection_%02d" % index,
            "stylistic",
            f"Is this actually visible: {_text(flaw)}?",
        )
    for index, value in enumerate(_list(spec.get("must_not_show")), start=1):
        add(
            "q_must_not_%02d" % index,
            "constraint",
            f"Is the image free of this: {_text(value)}?",
        )
    # "Exactly two walkers?" answered yes while twenty more people stood in the
    # lane, because every count question asks about a declared entity and none
    # asks about the frame.
    add(
        "q_undeclared",
        "logic",
        "Is the frame free of people and key objects beyond the ones the spec names, "
        "with no extra figures in the background and no added props?",
        verify_with="count",
    )
    # Four misses: pseudo-lettering passed as "nothing readable". Text that is
    # illegible is still text, and half-formed glyphs are the most recognisable
    # mark of a generated image.
    add(
        "q_malformed_glyphs",
        "constraint",
        "Is the image free of malformed or invented glyphs, the half-formed marks that "
        "read as lettering at a glance without being any real script?",
        verify_with="ocr",
    )
    add(
        "q_no_text",
        "constraint",
        "Is the image free of any legible text, numbers, logos or watermarks the spec did "
        "not ask for?",
        verify_with="ocr",
    )
    return questions


# ---------------------------------------------------------------- scaffolding


REFERENCE_STUB = {
    "place_is_real": True,
    "place_name": "<the name the client and their customers use for this place>",
    "address": "<street address>",
    "sources": [
        {
            "url": "<where you read it>",
            "publisher": "<who published it>",
            "shows": "<what this source actually shows of the place>",
            "viewpoint": "interior_wide",
            "accessed": "<YYYY-MM-DD>",
            "rights": "reference_only",
        },
        {
            "url": "<a second source, because one page is a claim and two that agree are evidence>",
            "publisher": "<who published it>",
            "shows": "<what this one shows>",
            "viewpoint": "exterior",
            "accessed": "<YYYY-MM-DD>",
            "rights": "reference_only",
        },
    ],
    "verified_facts": [
        "<what the sources establish, stated plainly and with no hedge>",
    ],
    "conflicting_claims": [
        "<where the sources disagree, so nobody picks a side by accident>",
    ],
    "conditioning_images": [],
}


def blank_spec(
    medium: str = "photograph",
    people: int = 1,
    reference: bool = False,
) -> dict[str, Any]:
    """A spec skeleton with every required field present and empty.

    Every string is a question, not a placeholder, so an unfilled field reads as an
    unanswered question rather than something that looks already decided.
    """
    if medium not in MEDIA:
        raise ValueError("medium must be one of " + ", ".join(sorted(MEDIA)))
    photographic = medium in PHOTOGRAPHIC_MEDIA
    subjects = []
    for index in range(max(0, int(people))):
        subjects.append(
            {
                "id": f"person{index + 1}",
                "kind": "person",
                "count": 1,
                "description": "<who they are in three or four words>",
                "short_name": "<one or two words to call them by later>",
                "appearance": "<age range, build, hair, skin tone>",
                "wardrobe": "<garments, colours, fabrics, footwear>",
                "posture": "standing",
                "pose": "<what the body does, limb by limb>",
                "hands": "<what each hand does, or that hands are out of frame>",
                "gaze": "<where the eyes point>",
                "expression": "<the face, in plain words>",
                "action": "<the verb of the picture>",
                "position": "<where in the frame, and on what ground>",
                "height_m": 1.7,
                "ground_height_m": 0,
                "distance_m": 3.0 if photographic else None,
                "plane": "midground",
                "interacts_with": [],
            }
        )
    spec: dict[str, Any] = {
        "version": SPEC_VERSION,
        "purpose": "<what the reader must understand from this image in one sentence>",
        "medium": medium,
        "style": {
            "look": "<reference style in the client's own words>",
            "color_palette": "<palette, named or in hex>",
            "mood": "<the feeling, one phrase>",
            "texture": "<grain, sheen, surface finish>",
        },
        "location": {
            "place": "<the room, street or landscape>",
            "locale": "<country or city the scene belongs to>",
            "time_of_day": "midday" if photographic else "",
            "weather": "<sky and air, or empty indoors>",
            "locale_details": [
                "<a local detail a wrong picture would get wrong>",
            ],
        },
        "camera": {
            "shot_type": "medium",
            "angle": "eye_level",
            "tilt": "level",
            "horizon": "middle" if photographic else "",
            "height_m": 1.6 if photographic else None,
            "focal_length_mm": 50 if photographic else None,
            "aperture_f": 4.0 if photographic else None,
            "subject_distance_m": 3.0 if photographic else None,
            "focus_on": subjects[0]["id"] if subjects else "object1",
        },
        "subjects": subjects,
        "objects": [
            {
                "id": "object1",
                "name": "<the thing>",
                "short_name": "<one or two words to call it by later>",
                "count": 1,
                "material": "<what it is made of>",
                "state": "<new, worn, open, lit, wet>",
                "size": "<real size in cm or m>",
                "height_m": None,
                "width_m": None,
                "scale_anchor": "<how its size reads against a person or another object here>",
                "support": {"kind": "rests_on", "by": "<the surface or person>"},
                "position": "<where in the frame>",
                "distance_m": 3.0 if photographic else None,
                "plane": "midground",
                "interacts_with": [],
            }
        ],
        "spatial_layout": {
            "foreground": "<what is nearest the camera>",
            "midground": "<where the subject sits>",
            "background": "<what closes the frame>",
        },
        "lighting": {
            "key": {
                "source": "<sun, window, softbox, practical>",
                "direction": "front_left",
                "quality": "<hard or soft, and why: size and distance of the source>",
            },
            "fill": ["<bounce, sky, second source, or nothing>"],
            "shadow_direction": "right",
            "color_temperature_k": 5500,
        },
        "composition": {
            "subject_placement": "<where the subject sits in the frame and why>",
            "negative_space": "<the area that stays quiet for the headline or logo>",
            "crop_safety": "<what must survive the client's other aspect ratios>",
        },
        "background_focus": "blurred" if photographic else "",
        "realism": {
            "imperfections": [
                "<a flaw with a place: a scuff on the counter edge by the till>",
                "<another: one chair pushed out of line, flyaway hair at the left temple>",
            ],
        },
        "physical_invariants": [
            "<a scene fact a wrong picture would break>",
        ],
        "must_not_show": [],
        "text_in_image": "none",
    }
    if reference:
        spec["location"]["reference"] = json.loads(json.dumps(REFERENCE_STUB))
    if not photographic:
        for key in ("height_m", "focal_length_mm", "aperture_f", "subject_distance_m"):
            spec["camera"].pop(key, None)
        spec.pop("background_focus", None)
    return spec


# ---------------------------------------------------------------- freshness and review


def compile_record(spec: dict[str, Any], result: dict[str, Any], compiled_at: str) -> dict[str, Any]:
    return {
        "spec_version": SPEC_VERSION,
        "spec_sha256": canonical_sha256(spec),
        "prompt_sha256": text_sha256(result["prompt"]),
        "negative_prompt_sha256": text_sha256(result["negative_prompt"]),
        "target": result["target"],
        "compiled_at": compiled_at,
        "derived": result["derived"],
        "questions": result["questions"],
        "warnings": result["warnings"],
    }


def freshness_errors(item: dict[str, Any]) -> list[str]:
    """The prompt in the manifest must be exactly what the current spec compiles to."""
    image_id = _text(item.get("id")) or "unknown"
    spec = item.get("spec")
    record = item.get("spec_compiled")
    if not isinstance(spec, dict) or not spec:
        return [f"{image_id}: image spec is missing; fill spec and run image_production.py compile-spec."]
    if not isinstance(record, dict) or not record.get("spec_sha256"):
        return [f"{image_id}: spec has not been compiled; run image_production.py compile-spec."]
    errors = []
    if record.get("spec_sha256") != canonical_sha256(spec):
        errors.append(f"{image_id}: spec changed after compilation; run compile-spec again.")
    if record.get("prompt_sha256") != text_sha256(_text(item.get("prompt")) if item.get("prompt") is not None else ""):
        if record.get("prompt_sha256") != text_sha256(str(item.get("prompt", ""))):
            errors.append(f"{image_id}: prompt was edited by hand after compilation; change the spec instead.")
    if record.get("negative_prompt_sha256") != text_sha256(str(item.get("negative_prompt", ""))):
        errors.append(f"{image_id}: negative_prompt was edited by hand after compilation; change the spec instead.")
    return errors


REFERENCE_DIR = Path(__file__).resolve().parent.parent / "reference" / "content-production"
DEFAULTS_PATH = REFERENCE_DIR / "defaults.json"
MODEL_REGISTRY_PATH = REFERENCE_DIR / "image-model-registry.json"


def default_checks() -> list[dict[str, Any]]:
    """The shipped rubric, so a client config without checks still has a gate."""
    try:
        data = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    checks = data.get("images", {}).get("plausibility", {}).get("checks", [])
    return [c for c in checks if isinstance(c, dict) and _text(c.get("id"))]


def rubric(config: dict[str, Any]) -> list[dict[str, Any]]:
    checks = policy_from_config(config)["plausibility"].get("checks", [])
    checks = [c for c in checks if isinstance(c, dict) and _text(c.get("id"))]
    return checks or default_checks()


def _na_allowed(check: dict[str, Any], spec: dict[str, Any] | None) -> bool:
    condition = _text(check.get("not_applicable_when"))
    if condition == "always":
        return True
    if not condition or not isinstance(spec, dict) or not spec:
        return condition == "no_spec_reviewer_judgement"
    if condition == "no_people":
        return people_count(spec) == 0
    if condition == "non_photographic":
        return _text(spec.get("medium") or "photograph") not in PHOTOGRAPHIC_MEDIA
    if condition == "no_locale_details":
        location = spec.get("location", {})
        return not _list(location.get("locale_details")) if isinstance(location, dict) else True
    if condition == "absent_from_image":
        # The reviewer may stand the check down, but the evidence must say what
        # is absent: no hands in frame, no reflective surface, no liquid.
        return True
    return False


def review_template(item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """A blank structured review the reviewer fills in after looking at the image."""
    style_checks = config.get("images", {}).get("style", {}).get("review_checklist", [])
    if isinstance(style_checks, str):
        style_checks = [style_checks]
    plaus = policy_from_config(config)["plausibility"]
    record = item.get("spec_compiled") if isinstance(item.get("spec_compiled"), dict) else {}
    return {
        "reviewer": "",
        "notes": "",
        "image_sha256": "",
        "crops_reviewed": 0,
        "checks": {name: "" for name in style_checks},
        "plausibility": {
            c["id"]: {"status": "", "evidence": "", "_check": _text(c.get("question"))}
            for c in rubric(config)
        },
        "spec_answers": {
            q["id"]: {"answer": "", "evidence": "", "_question": q["question"]}
            for q in record.get("questions", [])
        },
        "_instructions": (
            "status is passed, failed or not_applicable; answer is yes or no. Every entry "
            "needs evidence naming the zone or crop you looked at and what you saw. "
            f"Review the full image, then all {int(plaus.get('zoom_grid', 3)) ** 2} crops from review-crops."
        ),
    }


def review_errors(
    review: dict[str, Any],
    item: dict[str, Any],
    config: dict[str, Any],
    image_sha256: str = "",
) -> list[str]:
    """Errors that stop a passed plausibility review."""
    plaus = policy_from_config(config)["plausibility"]
    if not plaus.get("required", True):
        return []
    image_id = _text(item.get("id")) or "unknown"
    errors: list[str] = []
    spec = item.get("spec") if isinstance(item.get("spec"), dict) else None
    evidence_required = bool(plaus.get("evidence_required", True))
    min_evidence = int(plaus.get("min_evidence_chars", 12))

    grid = int(plaus.get("zoom_grid", 3))
    crops = review.get("crops_reviewed", 0)
    if grid > 0 and (not isinstance(crops, int) or crops < grid * grid):
        errors.append(f"{image_id}: crops_reviewed must be at least {grid * grid} (zoom grid {grid}x{grid}).")
    if image_sha256 and _text(review.get("image_sha256")) != image_sha256:
        errors.append(f"{image_id}: review image_sha256 does not match the processed image; review the current file.")

    answers = review.get("plausibility", {})
    if not isinstance(answers, dict):
        return errors + [f"{image_id}: plausibility must be an object of check results."]
    for check in rubric(config):
        cid = check["id"]
        entry = answers.get(cid)
        if not isinstance(entry, dict):
            errors.append(f"{image_id}: plausibility check {cid} is unanswered.")
            continue
        status = _text(entry.get("status"))
        evidence = _text(entry.get("evidence"))
        if evidence_required and len(evidence) < min_evidence:
            errors.append(f"{image_id}: plausibility check {cid} needs evidence (what was seen and where).")
        if status == "passed":
            continue
        if status == "not_applicable":
            if not _na_allowed(check, spec):
                errors.append(f"{image_id}: plausibility check {cid} cannot be not_applicable for this image.")
            continue
        errors.append(f"{image_id}: plausibility check {cid} is {status or 'blank'}.")

    if spec_required(item, config) or (spec and item.get("spec_compiled")):
        errors.extend(freshness_errors(item))
        record = item.get("spec_compiled") if isinstance(item.get("spec_compiled"), dict) else {}
        spec_answers = review.get("spec_answers", {})
        if not isinstance(spec_answers, dict):
            spec_answers = {}
        for question in record.get("questions", []):
            qid = question.get("id")
            entry = spec_answers.get(qid)
            if not isinstance(entry, dict):
                errors.append(f"{image_id}: spec question {qid} is unanswered.")
                continue
            if evidence_required and len(_text(entry.get("evidence"))) < min_evidence:
                errors.append(f"{image_id}: spec question {qid} needs evidence.")
            if _text(entry.get("answer")).lower() != "yes":
                errors.append(f"{image_id}: spec question {qid} is answered {entry.get('answer') or 'blank'}; the image does not match its spec.")
    return errors


def failed_items(review: dict[str, Any]) -> list[str]:
    """Ids of every check or question the review did not pass, for the repair loop."""
    failed = []
    for cid, entry in (review.get("plausibility") or {}).items():
        if isinstance(entry, dict) and _text(entry.get("status")) not in {"passed", "not_applicable"}:
            failed.append(cid)
    for qid, entry in (review.get("spec_answers") or {}).items():
        if isinstance(entry, dict) and _text(entry.get("answer")).lower() != "yes":
            failed.append(qid)
    return sorted(failed)
