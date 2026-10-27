#!/usr/bin/env python3
"""Process article image manifests with exact sizing, logo policy, and metadata QA."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow", file=sys.stderr)
    raise SystemExit(1)

import content_pipeline
import image_spec


PROVENANCE_SNAPSHOT_FIELDS = (
    "source_type",
    "provider",
    "source_url",
    "rights_record",
    "license_record",
    "generation_notes",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def provenance_snapshot(item: dict[str, Any]) -> dict[str, str]:
    provenance = item.get("provenance")
    if not isinstance(provenance, dict):
        raise RuntimeError(f"{item.get('id')}: provenance record is missing.")
    return {
        key: str(provenance.get(key, "")).strip()
        for key in PROVENANCE_SNAPSHOT_FIELDS
    }


def source_identity(path: Path, package: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        image.load()
        width, height = image.size
        image_format = image.format or ""
    return {
        "path": str(path.relative_to(package)).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "width": width,
        "height": height,
        "format": image_format,
    }


def webp_chunks(path: Path) -> list[str]:
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return []
    chunks: list[str] = []
    offset = 12
    while offset + 8 <= len(data):
        fourcc = data[offset : offset + 4].decode("ascii", errors="replace")
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        chunks.append(fourcc)
        offset += 8 + size + (size % 2)
    return chunks


# Encoder settings per images.format. AVIF copies the source ICC profile unless
# it is blanked; WebP never embeds one unasked.
ENCODERS = {
    "WEBP": {"options": {"method": 6}},
    "AVIF": {"options": {"icc_profile": b""}},
}
# Container markers that would ship embedded metadata, per format
PROHIBITED_CONTAINER_MARKERS = {
    "WEBP": {"EXIF", "XMP ", "ICCP", "META"},
    # iinf item types Exif and mime (XMP), and colr boxes holding an ICC profile
    "AVIF": {"item:Exif", "item:mime", "colr:prof", "colr:rICC"},
}


def iter_boxes(data: bytes, start: int, end: int):
    """Yield (type, payload_start, box_end) for ISOBMFF boxes in data[start:end]."""
    offset = start
    while offset + 8 <= end:
        size = int.from_bytes(data[offset : offset + 4], "big")
        box_type = data[offset + 4 : offset + 8].decode("ascii", errors="replace")
        header = 8
        if size == 1:
            if offset + 16 > end:
                return
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header = 16
        elif size == 0:
            size = end - offset
        if size < header or offset + size > end:
            return
        yield box_type, offset + header, offset + size
        offset += size


def avif_markers(path: Path) -> list[str]:
    """Metadata-relevant markers in an AVIF file: item types from meta/iinf
    (av01, Exif, mime for XMP) and colour types from iprp/ipco colr boxes
    (nclx is plain colour signalling; prof or rICC is an embedded ICC profile)."""
    data = path.read_bytes()
    if len(data) < 12 or data[4:8] != b"ftyp":
        return []
    markers: list[str] = []
    for box, start, end in iter_boxes(data, 0, len(data)):
        if box != "meta":
            continue
        # meta is a FullBox: skip version and flags
        for child, c_start, c_end in iter_boxes(data, start + 4, end):
            if child == "iinf":
                count_bytes = 2 if data[c_start] == 0 else 4
                for entry, e_start, e_end in iter_boxes(data, c_start + 4 + count_bytes, c_end):
                    version = data[e_start] if e_start < e_end else 0
                    if entry != "infe" or version < 2:
                        continue
                    type_at = e_start + 4 + (2 if version == 2 else 4) + 2
                    markers.append(
                        "item:" + data[type_at : type_at + 4].decode("ascii", errors="replace")
                    )
            elif child == "iprp":
                for prop, p_start, p_end in iter_boxes(data, c_start, c_end):
                    if prop != "ipco":
                        continue
                    for item, i_start, _i_end in iter_boxes(data, p_start, p_end):
                        if item == "colr":
                            markers.append(
                                "colr:" + data[i_start : i_start + 4].decode("ascii", errors="replace")
                            )
    return markers


def container_markers(path: Path, image_format: str) -> list[str]:
    return avif_markers(path) if image_format == "AVIF" else webp_chunks(path)


def load_effective_config(
    client: Path,
    package: Path,
    article: dict[str, Any],
) -> dict[str, Any]:
    for loader_name in ("load_package_config", "load_effective_config"):
        loader = getattr(content_pipeline, loader_name, None)
        if callable(loader):
            return loader(client, package, article)
    frozen = package / "resolved-config.json"
    if frozen.exists():
        config = content_pipeline.load_json(frozen)
    else:
        config = content_pipeline.load_client_config(client)
    article_override = article.get(
        "config_overrides",
        article.get("config_override", {}),
    )
    if article_override:
        config = content_pipeline.deep_merge(config, article_override)
    return config


def validate_provenance(item: dict[str, Any], config: dict[str, Any]) -> None:
    metadata = config["images"].get("metadata", {})
    if not metadata.get("internal_provenance_sidecar", True):
        return
    provenance = item.get("provenance")
    if not isinstance(provenance, dict):
        raise RuntimeError(f"{item.get('id')}: provenance record is missing.")
    source_type = str(provenance.get("source_type", "")).strip().lower()
    provider = str(provenance.get("provider", "")).strip()
    if not source_type or not provider:
        raise RuntimeError(
            f"{item.get('id')}: provenance requires source_type and provider."
        )
    if not str(provenance.get("rights_record", "")).strip():
        raise RuntimeError(
            f"{item.get('id')}: provenance requires a rights_record."
        )
    if source_type in {"licensed", "stock", "third_party"} and not str(
        provenance.get("license_record", "")
    ).strip():
        raise RuntimeError(
            f"{item.get('id')}: licensed sources require an internal license record."
        )
    if source_type in {"generated", "ai_generated"} and not str(
        provenance.get("generation_notes", "")
    ).strip():
        raise RuntimeError(
            f"{item.get('id')}: generated sources require generation notes."
        )


def visual_mode(item: dict[str, Any], role_config: dict[str, Any]) -> str:
    mode = str(
        item.get("visual_mode")
        or role_config.get("visual_mode")
        or role_config.get("asset_type")
        or ""
    ).strip()
    allowed = role_config.get("allowed_visual_modes", [])
    if isinstance(allowed, str):
        allowed = [allowed]
    if allowed and mode not in allowed:
        raise RuntimeError(
            f"{item.get('id')}: visual mode {mode!r} is not allowed for this role."
        )
    return mode


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def apply_text_overlays(
    image: Image.Image,
    client: Path,
    item: dict[str, Any],
    config: dict[str, Any],
) -> tuple[Image.Image, list[dict[str, Any]]]:
    overlays = item.get("text_overlays") or []
    if not overlays:
        return image, []
    mode = str(item.get("visual_mode", "")).lower()
    if "infographic" not in mode:
        raise RuntimeError(
            f"{item.get('id')}: deterministic text is allowed only in an "
            "infographic visual mode."
        )
    infographic = config["images"].get("infographic", {})
    if not infographic.get("allowed", False):
        raise RuntimeError(
            f"{item.get('id')}: text overlays require an enabled infographic workflow."
        )
    language = str(infographic.get("language", "English")).lower()
    canvas = image.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    reports: list[dict[str, Any]] = []
    for index, overlay in enumerate(overlays, 1):
        text = str(overlay.get("text", "")).strip()
        if not text:
            raise RuntimeError(f"{item.get('id')}: text overlay {index} is empty.")
        if language == "english" and not text.isascii():
            raise RuntimeError(
                f"{item.get('id')}: infographic text must be English-only."
            )
        font_path_value = str(
            overlay.get("font_path") or infographic.get("font_path") or ""
        ).strip()
        font_size = max(
            10,
            int(
                overlay.get(
                    "font_size_px",
                    round(image.height * float(overlay.get("font_size_ratio", 0.04))),
                )
            ),
        )
        if font_path_value:
            font_path = content_pipeline.safe_path(client, font_path_value)
            if not font_path.exists():
                raise RuntimeError(f"Approved infographic font not found: {font_path}")
            font = ImageFont.truetype(str(font_path), font_size)
        else:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()
        x = round(image.width * float(overlay.get("x_ratio", 0.05)))
        y = round(image.height * float(overlay.get("y_ratio", 0.05)))
        max_width = round(
            image.width * float(overlay.get("max_width_ratio", 0.9))
        )
        line_spacing = max(1, int(overlay.get("line_spacing_px", font_size * 0.25)))
        fill = str(overlay.get("fill", "#000000"))
        stroke_fill = str(overlay.get("stroke_fill", "#FFFFFF"))
        stroke_width = max(0, int(overlay.get("stroke_width", 0)))
        lines = wrap_text(draw, text, font, max_width)
        for line in lines:
            draw.text(
                (x, y),
                line,
                font=font,
                fill=fill,
                stroke_fill=stroke_fill,
                stroke_width=stroke_width,
            )
            box = draw.textbbox((x, y), line, font=font, stroke_width=stroke_width)
            y = box[3] + line_spacing
        reports.append(
            {
                "index": index,
                "text": text,
                "language": infographic.get("language", "English"),
                "deterministic": True,
            }
        )
    return canvas.convert("RGB"), reports


def should_apply_logo(policy: dict[str, Any], role: str) -> bool:
    apply_to = policy.get("apply_to", [])
    if isinstance(apply_to, str):
        apply_to = [apply_to]
    if not policy.get("allowed", True):
        if policy.get("required") or apply_to:
            raise RuntimeError(
                "Logo policy cannot request an overlay while logos are disallowed."
            )
        return False
    return bool(
        policy.get("required")
        or "all" in apply_to
        or role in apply_to
    )


def fit_image(
    image: Image.Image,
    width: int,
    height: int,
    fit: str,
    allow_upscale: bool,
) -> Image.Image:
    source = image.convert("RGB")
    if not allow_upscale and (source.width < width or source.height < height):
        raise RuntimeError(
            f"Source image {source.width}x{source.height} is below required "
            f"{width}x{height}; upscaling is disabled."
        )
    if fit == "cover":
        return ImageOps.fit(
            source,
            (width, height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
    if fit == "contain":
        contained = ImageOps.contain(
            source,
            (width, height),
            method=Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGB", (width, height), "white")
        x = (width - contained.width) // 2
        y = (height - contained.height) // 2
        canvas.paste(contained, (x, y))
        return canvas
    raise RuntimeError(f"Unsupported image fit mode: {fit}")


def logo_geometry(
    image: Image.Image,
    logo: Image.Image,
    policy: dict[str, Any],
) -> dict[str, int]:
    target_width = round(image.width * float(policy.get("width_ratio", 0.1)))
    target_width = max(int(policy.get("min_width_px", 1)), target_width)
    target_width = min(int(policy.get("max_width_px", image.width)), target_width)
    target_height = max(1, round(logo.height * target_width / logo.width))
    margin_x = max(1, round(image.width * float(policy.get("margin_x_ratio", 0.03))))
    margin_y = max(1, round(image.height * float(policy.get("margin_y_ratio", 0.03))))
    placement = policy.get("placement", "top-right")
    positions = {
        "top-left": (margin_x, margin_y),
        "top-right": (image.width - target_width - margin_x, margin_y),
        "bottom-left": (margin_x, image.height - target_height - margin_y),
        "bottom-right": (
            image.width - target_width - margin_x,
            image.height - target_height - margin_y,
        ),
    }
    if placement not in positions:
        raise RuntimeError(f"Unsupported logo placement: {placement}")
    x, y = positions[placement]
    if x < 0 or y < 0:
        raise RuntimeError("Configured logo is too large for the output image.")
    return {
        "x": x,
        "y": y,
        "width": target_width,
        "height": target_height,
        "margin_x": margin_x,
        "margin_y": margin_y,
    }


def apply_logo(
    image: Image.Image,
    logo_path: Path,
    policy: dict[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    with Image.open(logo_path) as logo_image:
        logo = logo_image.convert("RGBA")
        geometry = logo_geometry(image, logo, policy)
        logo = logo.resize(
            (geometry["width"], geometry["height"]),
            Image.Resampling.LANCZOS,
        )
        opacity = max(0.0, min(1.0, float(policy.get("opacity", 1.0))))
        logo.putalpha(
            logo.getchannel("A").point(lambda value: round(value * opacity))
        )
        canvas = image.convert("RGBA")
        canvas.alpha_composite(logo, (geometry["x"], geometry["y"]))
    return canvas.convert("RGB"), {
        "applied": True,
        "asset": str(logo_path),
        "placement": policy.get("placement", "top-right"),
        "opacity": opacity,
        **geometry,
    }


LICENSING_FIELD_TERMS = {"iptc", "xmp", "icc_profile", "c2pa", "copyright", "license", "creator"}


def effective_prohibited_terms(metadata_cfg: dict) -> list[str]:
    """Prohibited metadata terms after the client's declared licensing exception.

    Image licensing badges read creator, credit, and licence fields out of IPTC/XMP
    photo metadata, so a client that wants those badges may declare
    licensing_fields_exception=true to keep exactly those carriers. Privacy and
    provenance terms (gps, exif, software, prompt, parameters, comment) are never
    exempted: the exception is about rights fields, not about shipping device
    location or generator traces.
    """
    terms = list(metadata_cfg["prohibited_terms"])
    if metadata_cfg.get("licensing_fields_exception", False):
        terms = [t for t in terms if t.lower() not in LICENSING_FIELD_TERMS]
    return terms


def audit_metadata(
    path: Path,
    prohibited_terms: list[str],
    expected_width: int,
    expected_height: int,
    expected_format: str = "WEBP",
) -> dict[str, Any]:
    with Image.open(path) as image:
        keys = sorted(str(key) for key in image.info)
        prohibited = sorted(
            key
            for key in keys
            if any(term.lower() in key.lower() for term in prohibited_terms)
        )
        chunks = container_markers(path, expected_format)
        prohibited_chunks = sorted(
            chunk for chunk in chunks if chunk in PROHIBITED_CONTAINER_MARKERS[expected_format]
        )
        passed = (
            image.format == expected_format
            and image.size == (expected_width, expected_height)
            and not prohibited
            and not prohibited_chunks
        )
        return {
            "file": path.name,
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "embedded_info_keys": keys,
            "prohibited_keys": prohibited,
            "container_chunks": chunks,
            "prohibited_chunks": prohibited_chunks,
            "passed": passed,
        }


def validate_source_review(
    package: Path,
    item: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    source_value = str(item.get("source", "")).strip()
    if not source_value:
        raise RuntimeError(f"{item.get('id')}: source image path is missing.")
    source = content_pipeline.safe_path(package, source_value)
    if not source.is_file():
        raise RuntimeError(f"{item.get('id')}: source image not found: {source}")
    identity = source_identity(source, package)
    required = config.get("quality_gates", {}).get(
        "image_source_review_required",
        True,
    )
    if not required:
        return identity

    review = item.get("source_review")
    if not isinstance(review, dict) or review.get("status") != "passed":
        raise RuntimeError(
            f"{item.get('id')}: structured image source review has not passed."
        )
    evidence_value = str(review.get("evidence_file", "")).strip()
    if not evidence_value:
        raise RuntimeError(
            f"{item.get('id')}: source review evidence_file is missing."
        )
    evidence_path = content_pipeline.safe_path(package, evidence_value)
    if not evidence_path.is_file():
        raise RuntimeError(
            f"{item.get('id')}: source review evidence is missing: {evidence_path}"
        )
    evidence = content_pipeline.load_json(evidence_path)
    reviewer = str(evidence.get("reviewer", "")).strip()
    if not reviewer:
        raise RuntimeError(
            f"{item.get('id')}: source review evidence is missing reviewer."
        )
    reviewed_identity = evidence.get("source_identity")
    if not isinstance(reviewed_identity, dict):
        raise RuntimeError(
            f"{item.get('id')}: source review identity must be an object."
        )
    for key in ("path", "sha256", "bytes", "width", "height", "format"):
        if reviewed_identity.get(key) != identity.get(key):
            raise RuntimeError(
                f"{item.get('id')}: source {key} changed after source review."
            )

    current_provenance = provenance_snapshot(item)
    current_provenance_hash = content_pipeline.canonical_json_sha256(
        current_provenance
    )
    reviewed_provenance = evidence.get("provenance_snapshot")
    reviewed_provenance_hash = str(
        evidence.get("provenance_sha256", "")
    ).strip()
    if not isinstance(reviewed_provenance, dict):
        raise RuntimeError(
            f"{item.get('id')}: reviewed provenance snapshot is missing."
        )
    if (
        content_pipeline.canonical_json_sha256(reviewed_provenance)
        != reviewed_provenance_hash
    ):
        raise RuntimeError(
            f"{item.get('id')}: source review provenance evidence was modified."
        )
    if (
        current_provenance_hash != reviewed_provenance_hash
        or current_provenance != reviewed_provenance
    ):
        raise RuntimeError(
            f"{item.get('id')}: provenance changed after source review."
        )

    checklist = evidence.get("checklist")
    if not isinstance(checklist, dict):
        raise RuntimeError(
            f"{item.get('id')}: source review checklist must be an object."
        )
    required_checks = config.get("quality_gates", {}).get(
        "image_source_review_checklist",
        [],
    )
    missing = [key for key in required_checks if key not in checklist]
    failed = [
        key
        for key in required_checks
        if str(checklist.get(key, "")).strip().casefold() != "passed"
    ]
    if missing:
        raise RuntimeError(
            f"{item.get('id')}: source review checklist is missing: "
            + ", ".join(missing)
        )
    if failed:
        raise RuntimeError(
            f"{item.get('id')}: source review checklist has not passed: "
            + ", ".join(failed)
        )
    return identity


def record_source_review(
    client_value: str | Path,
    slug: str,
    image_id: str,
    review_file: str | Path,
) -> dict[str, Any]:
    client = content_pipeline.resolve_client(client_value)
    package, article = content_pipeline.read_package(client, slug)
    config = load_effective_config(client, package, article)
    if config.get("engine", {}).get("mode") != "generic":
        raise RuntimeError(
            "Generic source review is disabled for client_native mode. "
            "Use the declared review_image_sources adapter operation."
        )
    content_pipeline.require_config_capabilities(config, ["images"])
    if article.get("status") != "image_specs_ready":
        raise RuntimeError(
            "Image source review requires article status image_specs_ready. "
            "Invalidate later states before reviewing changed source assets."
        )

    manifest_path = content_pipeline.safe_path(package, article["images_file"])
    manifest = content_pipeline.load_json(manifest_path)
    target = next(
        (item for item in manifest.get("items", []) if item.get("id") == image_id),
        None,
    )
    if target is None:
        raise RuntimeError(f"Image id not found: {image_id}")
    validate_provenance(target, config)
    source_value = str(target.get("source", "")).strip()
    if not source_value:
        raise RuntimeError(f"{image_id}: source image path is missing.")
    source = content_pipeline.safe_path(package, source_value)
    if not source.is_file():
        raise RuntimeError(f"{image_id}: source image not found: {source}")
    identity = source_identity(source, package)

    input_path = content_pipeline.safe_path(package, review_file)
    if not input_path.is_file():
        raise RuntimeError(f"Source review input file not found: {input_path}")
    review = content_pipeline.load_json(input_path)
    reviewer = str(review.get("reviewer", "")).strip()
    if not reviewer:
        raise RuntimeError("Image source review requires a reviewer.")
    submitted_sha = str(review.get("source_sha256", "")).strip().lower()
    if submitted_sha != identity["sha256"]:
        raise RuntimeError(
            f"{image_id}: source_sha256 does not match the current raw image."
        )
    for field, identity_key in (
        ("source_width", "width"),
        ("source_height", "height"),
    ):
        submitted = review.get(field)
        if submitted != identity[identity_key]:
            raise RuntimeError(
                f"{image_id}: {field} does not match the current raw image."
            )

    submitted_provenance = review.get("provenance")
    if not isinstance(submitted_provenance, dict):
        raise RuntimeError("Image source review provenance must be an object.")
    reviewed_provenance = {
        key: str(submitted_provenance.get(key, "")).strip()
        for key in PROVENANCE_SNAPSHOT_FIELDS
    }
    current_provenance = provenance_snapshot(target)
    if reviewed_provenance != current_provenance:
        raise RuntimeError(
            f"{image_id}: reviewed provenance does not match image-manifest.json."
        )
    provenance_hash = content_pipeline.canonical_json_sha256(
        reviewed_provenance
    )

    checklist = review.get("checklist")
    if not isinstance(checklist, dict):
        raise RuntimeError("Image source review checklist must be an object.")
    required_checks = config.get("quality_gates", {}).get(
        "image_source_review_checklist",
        [],
    )
    missing = [key for key in required_checks if key not in checklist]
    failed = [
        key
        for key in required_checks
        if str(checklist.get(key, "")).strip().casefold() != "passed"
    ]
    if missing:
        raise RuntimeError(
            "Image source review checklist is missing required items: "
            + ", ".join(missing)
        )
    if failed:
        raise RuntimeError(
            "Image source review checklist items have not passed: "
            + ", ".join(failed)
        )

    timestamp = content_pipeline.now_iso()
    evidence = {
        "version": "1.0.0",
        "slug": slug,
        "image_id": image_id,
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "source_identity": identity,
        "provenance_snapshot": reviewed_provenance,
        "provenance_sha256": provenance_hash,
        "checklist": {
            key: str(checklist[key]).strip().casefold()
            for key in required_checks
        },
        "notes": str(review.get("notes", "")).strip(),
    }
    evidence_path = package / "reports" / f"{image_id}-source-review.json"
    content_pipeline.write_json(evidence_path, evidence)
    target["source_review"] = {
        "status": "passed",
        "reviewer": reviewer,
        "reviewed_at": timestamp,
        "evidence_file": str(evidence_path.relative_to(package)).replace("\\", "/"),
        "source_sha256": identity["sha256"],
        "source_width": identity["width"],
        "source_height": identity["height"],
        "provenance_sha256": provenance_hash,
    }
    target["technical_status"] = "pending"
    target["qa_status"] = "pending"
    for key in (
        "technical_report",
        "qa_notes",
        "qa_reviewer",
        "qa_reviewed_at",
        "qa_checklist",
        "qa_evidence_file",
    ):
        target.pop(key, None)
    content_pipeline.write_json(manifest_path, manifest)
    return evidence


def process_item(
    client: Path,
    package: Path,
    item: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    role = item.get("role")
    if role not in {"featured", "inline"}:
        raise RuntimeError(f"Unsupported image role: {role}")
    role_config = config["images"][role]
    mode = visual_mode(item, role_config)
    source_value = item.get("source", "").strip()
    if not source_value:
        raise RuntimeError(f"{item.get('id')}: source image path is missing.")
    source = content_pipeline.safe_path(package, source_value)
    if not source.exists():
        raise RuntimeError(f"{item.get('id')}: source image not found: {source}")
    reviewed_source = validate_source_review(package, item, config)
    validate_provenance(item, config)
    output = content_pipeline.safe_path(package, item["output"])
    output_format = content_pipeline.image_output_format(config["images"])
    if output_format not in ENCODERS:
        raise RuntimeError(f"Unsupported images.format: {output_format}")
    expected_suffix = content_pipeline.IMAGE_OUTPUT_FORMATS[output_format]
    if output.suffix.lower() != expected_suffix:
        raise RuntimeError(
            f"{item.get('id')}: output {output.name} does not match images.format "
            f"{output_format} (expected {expected_suffix}). Re-plan the image manifest "
            "after changing images.format."
        )
    width = int(role_config["width"])
    height = int(role_config["height"])

    with Image.open(source) as source_image:
        source_image.load()
        processed = fit_image(
            source_image,
            width,
            height,
            role_config.get("fit", "cover"),
            bool(role_config.get("allow_upscale", False)),
        )

    processed, text_overlay_report = apply_text_overlays(
        processed,
        client,
        item,
        config,
    )
    logo_policy = config["images"]["logo"]
    logo_report: dict[str, Any] = {"applied": False}
    if should_apply_logo(logo_policy, role):
        if item.get("preexisting_logo"):
            raise RuntimeError(
                f"{item.get('id')}: source is marked with a pre-existing logo; "
                "refusing to apply a second overlay."
            )
        asset = logo_policy.get("asset_path", "").strip()
        if not asset:
            raise RuntimeError(
                f"{item.get('id')}: logo is required but asset_path is empty."
            )
        logo_path = content_pipeline.safe_path(client, asset)
        if not logo_path.exists():
            raise RuntimeError(f"Approved logo asset not found: {logo_path}")
        processed, logo_report = apply_logo(processed, logo_path, logo_policy)

    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_cfg = config["images"].get("metadata", {})
    if not metadata_cfg.get("strip_embedded_metadata", True):
        if not metadata_cfg.get("licensing_fields_exception", False):
            raise RuntimeError(
                "Published image production requires strip_embedded_metadata=true, "
                "unless the client config declares licensing_fields_exception=true "
                "to keep IPTC/XMP licensing and creator fields for image licensing "
                "badges. GPS, EXIF device data, and generator traces stay prohibited "
                "either way."
            )
    processed.save(
        output,
        output_format,
        quality=int(
            role_config.get("avif_quality", 60)
            if output_format == "AVIF"
            else role_config.get("quality", 85)
        ),
        **ENCODERS[output_format]["options"],
    )
    metadata_report = audit_metadata(
        output,
        effective_prohibited_terms(config["images"]["metadata"]),
        width,
        height,
        output_format,
    )
    if not metadata_report["passed"]:
        raise RuntimeError(
            f"{item.get('id')}: output metadata or dimensions failed validation."
        )
    item["width"] = width
    item["height"] = height
    item["technical_status"] = "passed"
    item["visual_mode"] = mode
    item["qa_status"] = "needs_visual_review"
    for key in (
        "qa_notes",
        "qa_reviewer",
        "qa_reviewed_at",
        "qa_checklist",
        "qa_evidence_file",
    ):
        item.pop(key, None)
    item["technical_report"] = {
        "source": str(source),
        "output": str(output),
        "source_sha256": reviewed_source["sha256"],
        "output_sha256": sha256_file(output),
        "source_bytes": reviewed_source["bytes"],
        "source_width": reviewed_source["width"],
        "source_height": reviewed_source["height"],
        "source_format": reviewed_source["format"],
        "source_review": item.get("source_review"),
        "output_bytes": output.stat().st_size,
        "visual_mode": mode,
        "text_overlays": text_overlay_report,
        "logo": logo_report,
        "metadata": metadata_report,
    }
    return item["technical_report"]


def process_manifest(client_value: str | Path, slug: str) -> dict[str, Any]:
    client = content_pipeline.resolve_client(client_value)
    package, article = content_pipeline.read_package(client, slug)
    current_status = str(article.get("status", ""))
    if current_status not in content_pipeline.STATUSES:
        raise RuntimeError(f"Article has an invalid status: {current_status}")
    if content_pipeline.STATUSES.index(current_status) < content_pipeline.STATUSES.index(
        "image_specs_ready"
    ):
        raise RuntimeError(
            "Image processing requires image_specs_ready or a later state."
        )
    config = load_effective_config(client, package, article)
    manifest_path = content_pipeline.safe_path(package, article["images_file"])
    manifest = content_pipeline.load_json(manifest_path)
    for item in manifest.get("items", []):
        validate_source_review(package, item, config)
        validate_provenance(item, config)
        if image_spec.spec_required(item, config):
            stale = image_spec.freshness_errors(item)
            if stale:
                raise RuntimeError("; ".join(stale))
    reports: list[dict[str, Any]] = []
    for item in manifest.get("items", []):
        reports.append(process_item(client, package, item, config))
    content_pipeline.write_json(manifest_path, manifest)

    current_status = content_pipeline.load_json(package / "article.json")["status"]
    current_index = content_pipeline.STATUSES.index(current_status)
    technical_index = content_pipeline.STATUSES.index("images_technical_ready")
    if current_status == "image_specs_ready":
        content_pipeline.set_status(
            client,
            slug,
            "images_technical_ready",
            "All images were reprocessed and previous visual approval was cleared.",
        )
    elif current_index > technical_index:
        invalidator = getattr(content_pipeline, "invalidate_status", None)
        if callable(invalidator):
            invalidator(
                client,
                slug,
                "images_technical_ready",
                "Image processing invalidated every previous visual approval.",
            )
        else:  # Backward-compatible fallback for an older content_pipeline module.
            content_pipeline.set_status(
                client,
                slug,
                "images_technical_ready",
                "Image processing invalidated every previous visual approval.",
            )

    report = {
        "checked_at": content_pipeline.now_iso(),
        "slug": slug,
        "files": reports,
        "passed": all(
            item["metadata"]["passed"]
            and (
                item["logo"]["applied"]
                or not config["images"]["logo"].get("required")
            )
            for item in reports
        ),
        "visual_review_required": bool(
            config["images"].get("style", {}).get(
                "human_visual_review_required",
                True,
            )
        ),
        "synthid_note": config["images"]["metadata"]["synthid_note"],
    }
    content_pipeline.write_json(
        package / "reports" / "image-production-audit.json",
        report,
    )
    return report


def mark_reviewed(
    client_value: str | Path,
    slug: str,
    image_id: str,
    status: str,
    notes: str = "",
    reviewer: str = "",
    checklist_path: str | Path | None = None,
) -> dict[str, Any]:
    if status not in {"passed", "rejected"}:
        raise RuntimeError("Visual review status must be passed or rejected.")
    client = content_pipeline.resolve_client(client_value)
    package, article = content_pipeline.read_package(client, slug)
    config = load_effective_config(client, package, article)
    manifest_path = content_pipeline.safe_path(package, article["images_file"])
    manifest = content_pipeline.load_json(manifest_path)
    target = next(
        (item for item in manifest.get("items", []) if item.get("id") == image_id),
        None,
    )
    if target is None:
        raise RuntimeError(f"Image id not found: {image_id}")
    if target.get("technical_status") != "passed":
        raise RuntimeError(f"{image_id}: technical processing must pass first.")
    reviewer = reviewer.strip()
    if not reviewer:
        raise RuntimeError("Visual review requires a non-empty reviewer.")
    if not notes.strip():
        raise RuntimeError("Visual review requires review notes.")
    checklist: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    evidence_file = ""
    if checklist_path:
        checklist_file = content_pipeline.safe_path(package, checklist_path)
        if not checklist_file.exists():
            raise RuntimeError(f"Visual review checklist not found: {checklist_file}")
        evidence = content_pipeline.load_json(checklist_file)
        evidence_reviewer = str(evidence.get("reviewer", "")).strip()
        if evidence_reviewer and evidence_reviewer != reviewer:
            raise RuntimeError(
                "Checklist reviewer does not match the command reviewer."
            )
        raw_checks = evidence.get("checks", {})
        if not isinstance(raw_checks, dict):
            raise RuntimeError("Visual review checklist checks must be an object.")
        checklist = raw_checks
        evidence_file = str(checklist_file.relative_to(package))
    if status == "passed":
        if not checklist:
            raise RuntimeError(
                "A passed visual review requires a structured checklist JSON."
            )
        failed = [
            name
            for name, value in checklist.items()
            if value not in {True, "passed", "pass"}
        ]
        if failed:
            raise RuntimeError(
                "Visual review checklist has non-passing items: "
                + ", ".join(sorted(failed))
            )
        required_checks = config["images"].get("style", {}).get(
            "review_checklist",
            [],
        )
        if isinstance(required_checks, str):
            required_checks = [required_checks]
        missing = [name for name in required_checks if name not in checklist]
        if missing:
            raise RuntimeError(
                "Visual review checklist is missing required items: "
                + ", ".join(missing)
            )
        optimized = content_pipeline.safe_path(package, target.get("output", ""))
        image_digest = sha256_file(optimized) if optimized.exists() else ""
        plausibility_errors = image_spec.review_errors(
            evidence,
            target,
            config,
            image_digest,
        )
        if plausibility_errors:
            raise RuntimeError(
                "Plausibility review is incomplete or failing: "
                + "; ".join(plausibility_errors)
            )
    target["qa_status"] = status
    target["qa_notes"] = notes
    target["qa_reviewer"] = reviewer
    target["qa_checklist"] = checklist
    target["qa_plausibility"] = {
        "checks": {
            cid: str(entry.get("status", ""))
            for cid, entry in (evidence.get("plausibility") or {}).items()
            if isinstance(entry, dict)
        },
        "failed": image_spec.failed_items(evidence),
        "crops_reviewed": evidence.get("crops_reviewed", 0),
        "image_sha256": str(evidence.get("image_sha256", "")),
    }
    target["qa_evidence_file"] = evidence_file
    target["qa_reviewed_at"] = content_pipeline.now_iso()
    content_pipeline.write_json(manifest_path, manifest)

    if status == "passed" and all(
        item.get("qa_status") == "passed" for item in manifest.get("items", [])
    ):
        current = content_pipeline.load_json(package / "article.json")["status"]
        if (
            content_pipeline.STATUSES.index(current)
            < content_pipeline.STATUSES.index("images_qa_passed")
        ):
            content_pipeline.set_status(
                client,
                slug,
                "images_qa_passed",
                "Every required image passed full-resolution visual review.",
            )
    return target


def read_manifest(
    client_value: str | Path,
    slug: str,
) -> tuple[Path, Path, dict[str, Any], Path, dict[str, Any], dict[str, Any]]:
    """Resolve one article package and return its image manifest and config."""
    client = content_pipeline.resolve_client(client_value)
    package, article = content_pipeline.read_package(client, slug)
    config = load_effective_config(client, package, article)
    manifest_path = content_pipeline.safe_path(package, article["images_file"])
    manifest = content_pipeline.load_json(manifest_path)
    return client, package, article, manifest_path, manifest, config


def find_item(manifest: dict[str, Any], image_id: str) -> dict[str, Any]:
    target = next(
        (item for item in manifest.get("items", []) if item.get("id") == image_id),
        None,
    )
    if target is None:
        raise RuntimeError(f"Image id not found: {image_id}")
    return target


def compile_specs(
    client_value: str | Path,
    slug: str,
    image_id: str | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """Compile every image spec into the manifest prompt, avoid list and questions.

    The prompt is never written by hand: it is derived from the spec, so a changed
    spec forces a recompile and a hand-edited prompt is caught by the gate.
    """
    _, package, _, manifest_path, manifest, config = read_manifest(client_value, slug)
    policy = image_spec.policy_from_config(config)["spec"]
    # Empty means the registry entry for target_model decides; compile_spec
    # resolves it. Passing "negative_prompt" here overrode the registry, so
    # gpt-image clients lost their exclusions to a field it does not have.
    prompt_target = target or str(policy.get("prompt_target") or "")
    target_warning = (
        "images.spec.target_model is not set, so exclusions go inline in the prompt, as "
        "gpt-image on Codex and ChatGPT needs. On a Gemini or FLUX host, whose vendors "
        "advise describing the positive state only, set target_model (gemini-image, flux), "
        "or prompt_target explicitly."
        if not prompt_target and not image_spec.target_model_policy(config)
        else ""
    )
    compiled_target = ""
    items = (
        [find_item(manifest, image_id)]
        if image_id
        else list(manifest.get("items", []))
    )
    compiled: list[dict[str, Any]] = []
    skipped: list[str] = []
    for item in items:
        iid = str(item.get("id"))
        if not image_spec.spec_required(item, config):
            skipped.append(iid)
            continue
        role_config = config["images"].get(str(item.get("role")), {})
        width = int(item.get("width") or role_config.get("width") or 0)
        height = int(item.get("height") or role_config.get("height") or 0)
        spec = item.get("spec")
        if not isinstance(spec, dict) or not spec:
            raise RuntimeError(
                f"{iid}: spec is empty. Fill it from the spec-template command; "
                "the prompt is compiled from the spec, never written by hand."
            )
        result = image_spec.compile_spec(spec, width, height, config, prompt_target)
        compiled_target = str(result.get("target") or "")
        item["prompt"] = result["prompt"]
        item["negative_prompt"] = result["negative_prompt"]
        # Every recorded reference conditions the generator (owner decision,
        # 2026-10-26), so the manifest carries them for the host to attach. Until
        # this, nothing sent them: the rangsarn session found its harness attached none.
        item["conditioning"] = image_spec.conditioning_references(spec)
        item["spec_compiled"] = image_spec.compile_record(
            spec,
            result,
            content_pipeline.now_iso(),
        )
        compiled.append(
            {
                "id": iid,
                "prompt_words": len(result["prompt"].split()),
                "avoid_items": len(result["avoid"]),
                "questions": len(result["questions"]),
                "conditioning": len(item["conditioning"]),
                "derived": result["derived"],
                "warnings": result["warnings"] + ([target_warning] if target_warning else []),
            }
        )
    content_pipeline.write_json(manifest_path, manifest)
    return {
        "compiled_at": content_pipeline.now_iso(),
        "slug": slug,
        "target": compiled_target or prompt_target or "inline_constraints",
        "compiled": compiled,
        "skipped": skipped,
        "package": str(package),
    }


def write_review_template(
    client_value: str | Path,
    slug: str,
    image_id: str,
) -> dict[str, Any]:
    """Write the blank plausibility review the reviewer fills in from the image."""
    _, package, _, _, manifest, config = read_manifest(client_value, slug)
    item = find_item(manifest, image_id)
    template = image_spec.review_template(item, config)
    output = content_pipeline.safe_path(
        package,
        f"reports/{image_id}-visual-review-input.json",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    optimized = content_pipeline.safe_path(package, item.get("output", ""))
    if optimized.exists():
        template["image_sha256"] = sha256_file(optimized)
    content_pipeline.write_json(output, template)
    return {
        "review_file": str(output.relative_to(package)),
        "checks": len(template["plausibility"]),
        "spec_questions": len(template["spec_answers"]),
        "image_sha256": template.get("image_sha256", ""),
    }


def write_review_crops(
    client_value: str | Path,
    slug: str,
    image_id: str,
) -> dict[str, Any]:
    """Cut the optimized image into a grid of full-resolution crops to inspect.

    A whole 1200 px image hides the failures that matter: fingers, teeth, contact
    shadows, warped lines, gibberish on signage. The reviewer looks at every crop.
    """
    _, package, _, _, manifest, config = read_manifest(client_value, slug)
    item = find_item(manifest, image_id)
    optimized = content_pipeline.safe_path(package, item.get("output", ""))
    if not optimized.exists():
        raise RuntimeError(f"{image_id}: optimized image is missing: {optimized}")
    plaus = image_spec.policy_from_config(config)["plausibility"]
    grid = int(plaus.get("zoom_grid", 3))
    if grid < 1:
        raise RuntimeError("images.plausibility.zoom_grid must be at least 1.")
    scale = float(plaus.get("crop_scale", 2.0))
    out_dir = content_pipeline.safe_path(package, f"reports/crops/{image_id}")
    if out_dir.exists():
        for stale in sorted(out_dir.glob("*.png")):
            stale.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    with Image.open(optimized) as image:
        image.load()
        width, height = image.size
        step_x = width / grid
        step_y = height / grid
        for row in range(grid):
            for col in range(grid):
                box = (
                    int(col * step_x),
                    int(row * step_y),
                    int(min((col + 1) * step_x, width)),
                    int(min((row + 1) * step_y, height)),
                )
                crop = image.crop(box)
                if scale > 1.0:
                    crop = crop.resize(
                        (
                            max(1, int(crop.width * scale)),
                            max(1, int(crop.height * scale)),
                        ),
                        Image.LANCZOS,
                    )
                name = f"{image_id}-r{row + 1}c{col + 1}.png"
                crop.save(out_dir / name, format="PNG")
                written.append(str((out_dir / name).relative_to(package)))
    return {
        "image": str(optimized.relative_to(package)),
        "image_sha256": sha256_file(optimized),
        "grid": grid,
        "crop_scale": scale,
        "crops": written,
    }


def _file_config(config_path: str | Path | None, target_model: str | None) -> dict[str, Any]:
    """Plugin defaults, an optional config merged over them, and the named generator."""
    config = content_pipeline.load_json(image_spec.DEFAULTS_PATH)
    if config_path:
        config = content_pipeline.deep_merge(config, content_pipeline.load_json(Path(config_path)))
    if target_model:
        config.setdefault("images", {}).setdefault("spec", {})["target_model"] = target_model
    return config


def _cut_crops(image_path: Path, out_dir: Path, stem: str, grid: int, scale: float) -> list[Path]:
    """The reviewer's grid of magnified crops, written as <stem>-r<row>c<col>.png."""
    if grid < 1:
        raise RuntimeError("images.plausibility.zoom_grid must be at least 1.")
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in sorted(out_dir.glob(f"{stem}-r*c*.png")):
        stale.unlink()
    written: list[Path] = []
    with Image.open(image_path) as image:
        image.load()
        width, height = image.size
        for row in range(grid):
            for col in range(grid):
                box = (
                    int(col * width / grid),
                    int(row * height / grid),
                    int(min((col + 1) * width / grid, width)),
                    int(min((row + 1) * height / grid, height)),
                )
                crop = image.crop(box)
                if scale > 1.0:
                    crop = crop.resize(
                        (max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
                        Image.LANCZOS,
                    )
                target = out_dir / f"{stem}-r{row + 1}c{col + 1}.png"
                crop.save(target, format="PNG")
                written.append(target)
    return written


def review_crops_file(
    image_path: str | Path,
    out_dir: str | Path,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Cut one image file into the reviewer's crops, outside any article package."""
    image_path = Path(image_path)
    if not image_path.exists():
        raise RuntimeError(f"image is missing: {image_path}")
    plaus = image_spec.policy_from_config(_file_config(config_path, None))["plausibility"]
    grid = int(plaus.get("zoom_grid", 3))
    scale = float(plaus.get("crop_scale", 2.0))
    written = _cut_crops(image_path, Path(out_dir), image_path.stem, grid, scale)
    return {
        "image": str(image_path),
        "image_sha256": sha256_file(image_path),
        "grid": grid,
        "crop_scale": scale,
        "crops": [str(path) for path in written],
    }


def review_template_file(
    spec_path: str | Path,
    width: int,
    height: int,
    target_model: str | None = None,
    target: str | None = None,
    config_path: str | Path | None = None,
    image_path: str | Path | None = None,
    image_id: str | None = None,
) -> dict[str, Any]:
    """The blank plausibility review for one spec file, outside any article package.

    The spec is compiled exactly as compile-spec-file compiles it, so the
    questions are the ones the generator's prompt was built with.
    """
    data = content_pipeline.load_json(Path(spec_path))
    spec = data["spec"] if isinstance(data.get("spec"), dict) else data
    config = _file_config(config_path, target_model)
    result = image_spec.compile_spec(spec, width, height, config, target or "")
    item = {
        "id": image_id or Path(spec_path).stem,
        "spec": spec,
        "prompt": result["prompt"],
        "negative_prompt": result["negative_prompt"],
        "spec_compiled": image_spec.compile_record(spec, result, content_pipeline.now_iso()),
    }
    template = {"image_id": item["id"], **image_spec.review_template(item, config)}
    if image_path:
        template["image_sha256"] = sha256_file(Path(image_path))
    return template


def compile_spec_file(
    spec_path: str | Path,
    width: int,
    height: int,
    target_model: str | None = None,
    target: str | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate and compile one spec file, outside any article package.

    For a client whose content runs through its own adapter: the plugin
    defaults, an optional config file merged over them, and the generator named
    from the model registry. The file may hold the spec itself or {"spec": ...}.
    """
    data = content_pipeline.load_json(Path(spec_path))
    spec = data["spec"] if isinstance(data.get("spec"), dict) else data
    config = _file_config(config_path, target_model)
    errors, warnings = image_spec.validate_spec(spec, width, height, config)
    report: dict[str, Any] = {"spec": str(spec_path), "valid": not errors, "errors": errors, "warnings": warnings}
    if errors:
        return report
    result = image_spec.compile_spec(spec, width, height, config, target or "")
    report.update(
        target=result["target"],
        prompt=result["prompt"],
        negative_prompt=result["negative_prompt"],
        avoid=result["avoid"],
        conditioning=image_spec.conditioning_references(spec),
        warnings=result["warnings"],
        questions=result["questions"],
        derived=result["derived"],
    )
    return report


def command_compile_spec_file(args: argparse.Namespace) -> int:
    report = compile_spec_file(
        args.spec, args.width, args.height, args.target_model, args.target, args.config
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if report["valid"] else 1


def command_review_crops_file(args: argparse.Namespace) -> int:
    print(json.dumps(review_crops_file(args.image, args.out_dir, args.config), ensure_ascii=False, indent=2))
    return 0


def command_review_template_file(args: argparse.Namespace) -> int:
    template = review_template_file(
        args.spec, args.width, args.height, args.target_model, args.target, args.config, args.image, args.image_id
    )
    text = json.dumps(template, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def command_compile_spec(args: argparse.Namespace) -> int:
    report = compile_specs(args.client, args.slug, args.image_id, args.target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def command_spec_template(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            image_spec.blank_spec(args.medium, args.people, args.reference),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_review_template(args: argparse.Namespace) -> int:
    report = write_review_template(args.client, args.slug, args.image_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def command_review_crops(args: argparse.Namespace) -> int:
    report = write_review_crops(args.client, args.slug, args.image_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def command_process(args: argparse.Namespace) -> int:
    report = process_manifest(args.client, args.slug)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


def command_review_source(args: argparse.Namespace) -> int:
    result = record_source_review(
        args.client,
        args.slug,
        args.image_id,
        args.review_file,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_mark(args: argparse.Namespace) -> int:
    result = mark_reviewed(
        args.client,
        args.slug,
        args.image_id,
        args.status,
        args.notes,
        args.reviewer,
        args.checklist_json,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    process = sub.add_parser("process", help="Process every image in a manifest.")
    process.add_argument("--client", required=True)
    process.add_argument("--slug", required=True)
    process.set_defaults(func=command_process)

    review_source = sub.add_parser(
        "review-source",
        help="Approve one exact raw source and provenance snapshot before processing.",
    )
    review_source.add_argument("--client", required=True)
    review_source.add_argument("--slug", required=True)
    review_source.add_argument("--image-id", required=True)
    review_source.add_argument(
        "--review-file",
        required=True,
        help="Structured review JSON confined to the article package.",
    )
    review_source.set_defaults(func=command_review_source)

    spec_template = sub.add_parser(
        "spec-template",
        help="Print a blank image spec to fill in; the prompt is compiled from it.",
    )
    spec_template.add_argument(
        "--medium",
        default="photograph",
        choices=sorted(image_spec.MEDIA),
    )
    spec_template.add_argument(
        "--people",
        type=int,
        default=1,
        help="How many person subjects to scaffold (0 for an object-only scene).",
    )
    spec_template.add_argument(
        "--reference",
        action="store_true",
        help="Scaffold location.reference for a real named place, which a picture of "
             "somewhere real needs and nobody guesses is there.",
    )
    spec_template.set_defaults(func=command_spec_template)

    compile_spec = sub.add_parser(
        "compile-spec",
        help="Validate every image spec and compile it into the prompt and avoid list.",
    )
    compile_spec.add_argument("--client", required=True)
    compile_spec.add_argument("--slug", required=True)
    compile_spec.add_argument("--image-id")
    compile_spec.add_argument(
        "--target",
        choices=sorted(image_spec.PROMPT_TARGETS | set(image_spec.TARGET_ALIASES)),
        help="Override where exclusions go; by default the registry entry for target_model decides.",
    )
    compile_spec.set_defaults(func=command_compile_spec)

    spec_file = sub.add_parser(
        "compile-spec-file",
        help="Validate and compile one spec file, for a client whose content runs through its own adapter.",
    )
    spec_file.add_argument("--spec", required=True, help="A JSON file holding the spec, or {\"spec\": ...}.")
    spec_file.add_argument("--width", type=int, required=True)
    spec_file.add_argument("--height", type=int, required=True)
    spec_file.add_argument("--target-model", help="A model name from image-model-registry.json, e.g. openai-gpt-image.")
    spec_file.add_argument(
        "--target",
        choices=sorted(image_spec.PROMPT_TARGETS | set(image_spec.TARGET_ALIASES)),
        help="Override where exclusions go; by default the registry entry for the target model decides.",
    )
    spec_file.add_argument("--config", help="A JSON config merged over the plugin defaults (its images section).")
    spec_file.add_argument("--out", help="Write the report here instead of printing it.")
    spec_file.set_defaults(func=command_compile_spec_file)

    crops_file = sub.add_parser(
        "review-crops-file",
        help="Cut one image file into the reviewer's magnified crops, outside any article package.",
    )
    crops_file.add_argument("--image", required=True)
    crops_file.add_argument("--out-dir", required=True)
    crops_file.add_argument("--config", help="A JSON config merged over the plugin defaults (zoom_grid, crop_scale).")
    crops_file.set_defaults(func=command_review_crops_file)

    review_file = sub.add_parser(
        "review-template-file",
        help="Write the blank review for one spec file, compiled as compile-spec-file compiles it.",
    )
    review_file.add_argument("--spec", required=True)
    review_file.add_argument("--width", type=int, required=True)
    review_file.add_argument("--height", type=int, required=True)
    review_file.add_argument("--target-model")
    review_file.add_argument("--target", choices=sorted(image_spec.PROMPT_TARGETS | set(image_spec.TARGET_ALIASES)))
    review_file.add_argument("--config")
    review_file.add_argument("--image", help="The generated image, to record its sha256 in the review.")
    review_file.add_argument("--image-id", help="The id to write into the review; defaults to the spec file's name.")
    review_file.add_argument("--out")
    review_file.set_defaults(func=command_review_template_file)

    review_template = sub.add_parser(
        "review-template",
        help="Write the blank plausibility review for one image.",
    )
    review_template.add_argument("--client", required=True)
    review_template.add_argument("--slug", required=True)
    review_template.add_argument("--image-id", required=True)
    review_template.set_defaults(func=command_review_template)

    review_crops = sub.add_parser(
        "review-crops",
        help="Cut the optimized image into full-resolution crops for close inspection.",
    )
    review_crops.add_argument("--client", required=True)
    review_crops.add_argument("--slug", required=True)
    review_crops.add_argument("--image-id", required=True)
    review_crops.set_defaults(func=command_review_crops)

    mark = sub.add_parser(
        "mark-reviewed",
        help="Record the mandatory full-resolution visual review.",
    )
    mark.add_argument("--client", required=True)
    mark.add_argument("--slug", required=True)
    mark.add_argument("--image-id", required=True)
    mark.add_argument("--status", required=True, choices=["passed", "rejected"])
    mark.add_argument("--notes", required=True)
    mark.add_argument("--reviewer", required=True)
    mark.add_argument("--checklist-json")
    mark.set_defaults(func=command_mark)
    return parser


def _self_test_hook() -> None:
    if "--self-test" in sys.argv[1:]:
        raise SystemExit(_self_test())


def main() -> int:
    _self_test_hook()
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2



def _self_test() -> int:
    """Logo policy, prohibited terms and provenance snapshot without an image."""
    assert should_apply_logo({"allowed": True, "apply_to": ["featured"]}, "featured")
    assert not should_apply_logo({"allowed": True, "apply_to": ["featured"]}, "inline")
    try:
        should_apply_logo({"allowed": False, "required": True}, "featured")
        raise AssertionError("disallowed logo with required must raise")
    except RuntimeError:
        pass
    terms = effective_prohibited_terms({"prohibited_terms": ["stock photo"]})
    assert isinstance(terms, list) and "stock photo" in terms
    try:
        provenance_snapshot({"id": "img-1"})
        raise AssertionError("missing provenance must raise")
    except RuntimeError:
        pass
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        exif = Image.Exif()
        exif[0x010F] = "Fixture Camera"
        dirty = Path(tmp) / "dirty.avif"
        Image.new("RGB", (64, 64), (10, 20, 30)).save(dirty, "AVIF", exif=exif)
        assert "item:Exif" in avif_markers(dirty), avif_markers(dirty)
        assert not audit_metadata(dirty, [], 64, 64, "AVIF")["passed"]
        clean = Path(tmp) / "clean.avif"
        Image.new("RGB", (64, 64), (10, 20, 30)).save(clean, "AVIF", **ENCODERS["AVIF"]["options"])
        assert audit_metadata(clean, [], 64, 64, "AVIF")["passed"]
    print("SELF-TEST PASS: logo policy, prohibited terms, provenance gate, AVIF metadata audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
