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

# Eye height as a fraction of stature, by posture. Standing 0.93 is stable across
# populations: ANSUR II gives 164.0/175.5 = 0.934 for men and 151.7/162.6 = 0.933
# for women, and a British 50th-percentile table agrees within a centimetre.
# Under about five years a relatively larger head makes 0.90 safer. Seated and
# kneeling figures are handled as an absolute height above the floor instead,
# because the seat, not the stature, sets them.
EYE_FRACTION = {"standing": 0.93, "walking": 0.93, "leaning": 0.90, "crouching": 0.55}
EYE_ABSOLUTE_M = {"sitting": 1.23, "seated": 1.23, "kneeling": 1.15, "lying": 0.25}
CHILD_EYE_FRACTION = 0.90

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
        return EYE_ABSOLUTE_M[posture]
    fraction = EYE_FRACTION.get(posture)
    if fraction is None:
        return None
    if stature <= 1.15:  # a child under about five carries a larger head
        fraction = CHILD_EYE_FRACTION
    return stature * fraction


def standing_people(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entity
        for kind, entity in _entities(spec)
        if kind == "subject"
        and _text(entity.get("kind") or "person") == "person"
        and _text(entity.get("posture") or "standing").lower() in EYE_FRACTION
    ]


def reference_height(name: str) -> tuple[float, float, str] | None:
    """The code or convention height band for a named object, if there is one."""
    lowered = name.lower()
    best: tuple[int, tuple[float, float, str]] | None = None
    for key, band in REFERENCE_HEIGHTS_M.items():
        if key in lowered and (best is None or len(key) > best[0]):
            best = (len(key), band)
    return best[1] if best else None


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
    eyes = [e for e in (eye_height(s) for s in standing_people(spec)) if e is not None]
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
        for subject in standing_people(spec):
            stature = _num(subject.get("height_m"))
            if not stature:
                continue
            fraction = cam_height / stature
            crossings.append(
                {
                    "id": _text(subject.get("id")),
                    "fraction_of_height_from_feet": round(min(fraction, 2.0), 3),
                    "above_head": fraction > 1.0,
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
NEGATION_EXEMPT_KEYS = {"must_not_show", "text_in_image"}


def negated_fields(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Spec fields that describe the picture by what it is not."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in NEGATION_EXEMPT_KEYS:
                continue
            found.extend(negated_fields(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(negated_fields(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        for word in negations(value):
            found.append((path or "<root>", word))
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

    for path in sorted(unfilled_placeholders(spec)):
        errors.append(f"spec.{path} still holds the template question; answer it.")

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
    medium = _text(spec.get("medium") or "photograph")
    if medium not in MEDIA:
        errors.append("spec.medium must be one of " + ", ".join(sorted(MEDIA)) + ".")
    photographic = medium in PHOTOGRAPHIC_MEDIA

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
    subjects = [s for s in _list(spec.get("subjects")) if isinstance(s, dict)]
    objects = [o for o in _list(spec.get("objects")) if isinstance(o, dict)]
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
            for field in ("appearance", "wardrobe", "pose", "gaze"):
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
        for field in ("name", "position", "material"):
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
        elif _text(support.get("kind")) in {"held_by", "worn_by"} and _text(support.get("by")) not in ids:
            errors.append(f"object {oid}: support.by {support.get('by')!r} must be a subject id for held_by or worn_by.")
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

    # Camera height against angle and the people in frame.
    if photographic and cam_height is not None and eye_heights:
        mean_eye = sum(eye_heights) / len(eye_heights)
        if angle == "eye_level" and abs(cam_height - mean_eye) > 0.35:
            errors.append(
                f"spec.camera angle eye_level needs the lens near standing eye height (~{mean_eye:.2f} m); "
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
    if len(objects) > max_objects:
        warnings.append(f"spec lists {len(objects)} key objects; above {max_objects} generators drop or merge items.")

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
    """Every negation word in a prompt, which a positive prompt must not carry."""
    return sorted({match.group(0).lower() for match in NEGATION_RE.finditer(text)})


def _an(word: str) -> str:
    """``a`` or ``an`` for the word that follows, so compiled prose reads cleanly."""
    return "an" if word[:1].lower() in "aeiou" else "a"


def _cap(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


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
        line = (f"{count} " if count > 1 else "One ") + who
        if _text(subject.get("appearance")):
            line += f", {_text(subject['appearance'])}"
        if _text(subject.get("wardrobe")):
            line += f", wearing {_text(subject['wardrobe'])}"
        line += f", {_text(subject.get('position'))}"
        add("subject", 1, line)
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
        if horizon == "not_visible":
            add(
                "camera",
                1,
                "The horizon is out of frame, and every receding line still converges "
                "consistently for this one viewpoint",
            )
        else:
            add(
                "camera",
                1,
                f"The horizon and eye-level line sit across the {horizon.replace('_', ' ')} of the frame, "
                "parallel edges converge to vanishing points on that line, and verticals stay vertical",
            )
        if derived.get("camera_at_eye_height"):
            add(
                "camera",
                2,
                "The camera stands at the eye height of the standing people, so that "
                "horizon line crosses their eyes",
            )
        else:
            for crossing in derived.get("horizon_crossings", [])[:2]:
                name = _entity_name(spec, crossing["id"])
                if crossing["above_head"]:
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

    invariants = [_text(v) for v in _list(spec.get("physical_invariants")) if _text(v)]
    if invariants:
        add("invariant", 2, "Physically and logically: " + "; ".join(invariants))

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
        constraints = "Constraints: no " + "; no ".join(avoid) + "."
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
            add(
                f"{base}_hands",
                "anatomy",
                f"Do the hands of {noun} do this, each with five fingers and a grip that "
                f"would hold: {_text(subject['hands'])}?",
                base,
                verify_with="count",
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
    add(
        "q_camera_shot",
        "camera",
        f"Is the view {_an(shot)} {shot.replace('_', ' ')} shot"
        + (f", {SHOT_FRAMING[shot]}" if shot in SHOT_FRAMING else "")
        + f", from {_an(_text(camera.get('angle')))} "
        f"{_text(camera.get('angle')).replace('_', ' ')} angle?",
        verify_with="geometry",
    )
    horizon = _text(camera.get("horizon"))
    if horizon and horizon != "not_visible":
        add(
            "q_horizon",
            "camera",
            f"Does the horizon or eye-level line sit across the {horizon.replace('_', ' ')} "
            "of the frame, level, with receding parallel edges meeting on it?",
            verify_with="geometry",
        )
    if derived.get("camera_at_eye_height"):
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
            f"Is {_entity_name(spec, eid)} softer than {_entity_name(spec, focus)}, as its "
            "distance from the focus plane requires?",
        )
    for ratio in derived.get("apparent_ratios", [])[:6]:
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
    add(
        "q_light",
        "light",
        f"Is every person and object lit from the {_text(key.get('direction')).replace('_', ' ')} "
        f"by {_text(key.get('source'))}, with the shaded side on the opposite side?",
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
            + ", ".join(_noun(entity) for entity in ground[:4])
            + " all sit on one floor that recedes consistently, rather than on separate "
            "invisible shelves?",
        )
    for crossing in derived.get("horizon_crossings", []):
        name = _entity_name(spec, crossing["id"])
        if crossing["above_head"]:
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
    for index, inv in enumerate(_list(spec.get("physical_invariants")), start=1):
        add("q_invariant_%02d" % index, "physics", f"Does the image respect this: {_text(inv)}?")
    for index, value in enumerate(_list(spec.get("must_not_show")), start=1):
        add(
            "q_must_not_%02d" % index,
            "constraint",
            f"Is the image free of this: {_text(value)}?",
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


def blank_spec(medium: str = "photograph", people: int = 1) -> dict[str, Any]:
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
        "physical_invariants": [
            "<a scene fact a wrong picture would break>",
        ],
        "must_not_show": [],
        "text_in_image": "none",
    }
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
