#!/usr/bin/env python3
"""End-to-end regression test for the lite content production pipeline.

One article package is driven from planned to publish_ready against a temporary
client workspace: fill a shot spec, compile it into the prompt, approve the raw
source, process the images, cut the review crops, answer the plausibility review
and pass the publish gate.

Three refusals are tested alongside the happy path, because each is a gate a
careless run would otherwise walk through:

1. images with no compiled spec cannot reach image_specs_ready;
2. a spec that contradicts itself never becomes a prompt;
3. a prompt edited by hand after compilation cannot be processed.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image, ImageCms, ImageDraw

import content_pipeline
import image_production
import image_spec


def fixture_spec(image_id: str) -> dict:
    """A small, valid shot brief: one person, one object, one key light."""
    return {
        "version": 1,
        "purpose": f"a deterministic editorial scene for {image_id}",
        "medium": "photograph",
        "style": {"look": "plain editorial", "mood": "calm"},
        "location": {
            "place": "a plain studio set",
            "locale": "Bangkok, Thailand",
            "time_of_day": "midday",
            "locale_details": ["the wall socket is the Thai three-pin type"],
        },
        "camera": {
            "shot_type": "medium",
            "angle": "eye_level",
            "tilt": "level",
            "horizon": "middle",
            "height_m": 1.58,
            "focal_length_mm": 50,
            "aperture_f": 4.0,
            "subject_distance_m": 2.4,
            "focus_on": "worker",
        },
        "subjects": [
            {
                "id": "worker",
                "kind": "person",
                "short_name": "worker",
                "count": 1,
                "description": "office worker in her forties",
                "appearance": "forties, medium build, dark hair",
                "wardrobe": "plain grey shirt",
                "posture": "standing",
                "pose": "standing square to the camera, arms at her sides",
                "hands": "her right hand rests on the desk, fingers spread",
                "gaze": "straight at the camera",
                "expression": "neutral",
                "action": "stands behind the desk",
                "position": "centre of the frame",
                "height_m": 1.7,
                "distance_m": 2.4,
                "plane": "midground",
                "interacts_with": ["desk"],
            }
        ],
        "objects": [
            {
                "id": "desk",
                "name": "plain wooden desk",
                "short_name": "desk",
                "count": 1,
                "material": "oak veneer",
                "state": "empty",
                "size": "0.73 m high, 1.4 m wide",
                "height_m": 0.73,
                "scale_anchor": "its top meets the worker at mid-thigh",
                "support": {"kind": "stands_on", "by": "the studio floor"},
                "position": "across the lower third of the frame",
                "distance_m": 2.2,
                "plane": "midground",
                "interacts_with": ["worker"],
            }
        ],
        "spatial_layout": {
            "foreground": "the near edge of the desk",
            "midground": "the worker and the desk",
            "background": "an even grey wall",
        },
        "lighting": {
            "key": {
                "source": "a large softbox",
                "direction": "front_left",
                "quality": "soft, from a wide source close to the subject",
            },
            "fill": ["a white bounce board on the right"],
            "shadow_direction": "right",
            "color_temperature_k": 5500,
        },
        "composition": {
            "subject_placement": (
                "the worker on the centre line, the desk edge on the lower third"
            ),
            "negative_space": "the upper right quarter of the even grey wall",
            "crop_safety": "the head and the desk edge survive a square crop",
        },
        "background_focus": "blurred",
        "realism": {
            "imperfections": [
                "a scratch in the desk veneer near the front right corner",
                "one sleeve of the grey shirt pushed up further than the other",
            ],
        },
        "physical_invariants": [
            "the worker stands behind the desk, so the desk edge crosses in front "
            "of her upper thighs",
        ],
        "must_not_show": ["a second desk"],
        "text_in_image": "none",
    }


def fixture_review(item: dict, config: dict, image_sha256: str) -> dict:
    """A complete plausibility review: every check answered with evidence."""
    review = image_spec.review_template(item, config)
    review["reviewer"] = "self-test reviewer"
    review["notes"] = "Full-resolution fixture review of the frame and all nine crops."
    review["crops_reviewed"] = 9
    review["image_sha256"] = image_sha256
    review["checks"] = {
        key: "passed" for key in config["images"]["style"]["review_checklist"]
    }
    for entry in review["plausibility"].values():
        entry["status"] = "passed"
        entry["evidence"] = "checked against the centre crop of the fixture plate"
    for entry in review["spec_answers"].values():
        entry["answer"] = "yes"
        entry["evidence"] = "checked against the centre crop of the fixture plate"
    return review


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# An embedded ICC profile on every raw source proves the encoders strip it
SRGB_ICC = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

ARTICLE_MARKDOWN = """Opening copy with enough detail to pass the package validation gate.

[Product](https://example.com/product/)
[Pillar](https://example.com/guide/)
[Related](https://example.com/related/)
[Primary source](https://developers.google.com/search/docs/)
[Secondary source](https://wordpress.org/documentation/)

{{INLINE_IMAGE_1}}

## Useful section

Additional article copy keeps this fixture representative of a real package.
"""


def run(image_format: str = "WEBP") -> None:
    extension = content_pipeline.IMAGE_OUTPUT_FORMATS[image_format]
    with tempfile.TemporaryDirectory(prefix="rainmojo-lite-content-production-") as tmp:
        initialized = content_pipeline.client_workspace.initialize_workspace(
            Path(tmp) / "clients",
            "example.com",
        )
        client = Path(initialized["path"])
        config = content_pipeline.load_json(content_pipeline.DEFAULTS_PATH)
        config = content_pipeline.deep_merge(
            config,
            {
                "config_policy": {"profile": "test"},
                "site": {"domain": "example.com"},
                "images": {
                    "format": image_format,
                    "style": {
                        "mode": "self-test-editorial",
                        "review_checklist": [
                            "composition",
                            "no_unapproved_text",
                            "logo_clear_space",
                            "anatomy_or_subject_integrity",
                            "equipment_or_scene_accuracy",
                            "brand_accuracy",
                        ],
                    },
                    "logo": {
                        "required": True,
                        "apply_to": ["featured", "inline"],
                        "asset_path": "uploads/brand-assets/logo.png",
                        "placement": "top-right",
                        "width_ratio": 0.1,
                        "min_width_px": 100,
                        "max_width_px": 140,
                        "margin_x_ratio": 0.03,
                        "margin_y_ratio": 0.03,
                        "opacity": 1.0,
                    },
                },
            },
        )
        write_json(client / "content-pipeline.json", config)

        logo_path = client / "uploads" / "brand-assets" / "logo.png"
        logo_path.parent.mkdir(parents=True, exist_ok=True)
        logo = Image.new("RGBA", (240, 120), (0, 0, 0, 0))
        ImageDraw.Draw(logo).rectangle((2, 2, 237, 117), fill=(220, 20, 40, 255))
        logo.save(logo_path)

        slug = "test-content-production"
        package = content_pipeline.initialize_package(
            client,
            slug,
            "Test Content Production",
            "test content production",
        )
        article = content_pipeline.load_json(package / "article.json")
        article["seo"]["title"] = "Test Content Production Workflow"
        article["seo"]["description"] = (
            "A regression article that verifies content, images, links, and the spec gate."
        )
        article["links"] = {
            "product_targets": ["https://example.com/product/"],
            "pillar_targets": ["https://example.com/guide/"],
            "related_targets": ["https://example.com/related/"],
            "external_sources": [
                "https://developers.google.com/search/docs/",
                "https://wordpress.org/documentation/",
            ],
        }
        content_pipeline.write_json(package / "article.json", article)
        for state in ("outline_ready", "research_ready", "draft_ready"):
            content_pipeline.set_status(
                client,
                slug,
                state,
                f"Self-test advanced to {state}.",
            )

        (package / "article.md").write_text(ARTICLE_MARKDOWN, encoding="utf-8")
        write_json(
            package / "sources.json",
            {
                "version": "1.0.0",
                "slug": slug,
                "internal": [],
                "external": [
                    {
                        "url": "https://developers.google.com/search/docs/",
                        "claim": "Search documentation is an authoritative primary source.",
                        "accessed_at": "2026-07-16",
                    },
                    {
                        "url": "https://wordpress.org/documentation/",
                        "claim": "WordPress documentation supports the publishing workflow.",
                        "accessed_at": "2026-07-16",
                    },
                ],
            },
        )
        content_pipeline.record_content_review(
            client,
            slug,
            {
                "reviewer": "self-test content reviewer",
                "article_sha256": content_pipeline.file_sha256(package / "article.md"),
                "checklist": {
                    key: "passed"
                    for key in config["quality_gates"]["content_review_checklist"]
                },
                "notes": "Deterministic content review fixture.",
            },
        )
        content_pipeline.set_status(
            client,
            slug,
            "content_qa_passed",
            "Self-test advanced to content_qa_passed.",
        )

        # Refusal 1: no spec, no prompt, no gate.
        try:
            content_pipeline.set_status(
                client,
                slug,
                "image_specs_ready",
                "Self-test tried to skip the image spec.",
            )
        except RuntimeError as exc:
            assert "Image spec gate failed" in str(exc), str(exc)
        else:
            raise AssertionError("Images with no spec reached image_specs_ready.")

        manifest = content_pipeline.load_json(package / "image-manifest.json")
        for item in manifest["items"]:
            item["source"] = "images/raw/" + item["id"] + ".png"
            item["concept"] = "A distinct editorial concept for " + item["id"]
            item["spec"] = fixture_spec(item["id"])
            if item is manifest["items"][0]:
                item["spec"]["style"]["reference"] = {
                    "path": "brand/style-v1.png", "rights": "client_owned", "origin": "approved brand art v1",
                }
            item["alt"] = "Editorial visual for " + item["id"]
            item["title"] = "Editorial visual " + item["id"]
            item["provenance"] = {
                "source_type": "generated",
                "provider": "self-test fixture",
                "source_url": "",
                "rights_record": "Self-test generated asset owned by the fixture.",
                "license_record": "",
                "generation_notes": "Solid-color deterministic Pillow fixture.",
            }
            if item["role"] == "inline":
                item["caption"] = "Useful editorial context"
            source = package / item["source"]
            source.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (1800, 1200), (40, 60, 90)).save(
                source, icc_profile=SRGB_ICC
            )
            assert item["output"].endswith(extension), item["output"]
        content_pipeline.write_json(package / "image-manifest.json", manifest)

        # Refusal 2: a spec that contradicts itself never becomes a prompt. A
        # camera tilted down cannot put the horizon through the middle of the frame.
        broken = content_pipeline.load_json(package / "image-manifest.json")
        broken["items"][0]["spec"]["camera"]["tilt"] = "down"
        content_pipeline.write_json(package / "image-manifest.json", broken)
        try:
            image_production.compile_specs(client, slug)
        except ValueError as exc:
            assert "contradicts tilt" in str(exc), str(exc)
        else:
            raise AssertionError("A contradictory image spec compiled.")
        content_pipeline.write_json(package / "image-manifest.json", manifest)

        compiled = image_production.compile_specs(client, slug)
        assert len(compiled["compiled"]) == len(manifest["items"]), compiled
        # No target_model set: the compile says the exclusions may be dropped.
        assert all(
            any("target_model is not set" in w for w in entry["warnings"])
            for entry in compiled["compiled"]
        ), compiled["compiled"][0]["warnings"]
        assert compiled["target"] == "inline_constraints", compiled["target"]
        # The references reach the manifest for the host to attach.
        written = content_pipeline.load_json(package / "image-manifest.json")["items"]
        assert written[0]["conditioning"] == [
            {"role": "style", "path": "brand/style-v1.png", "rights": "client_owned"}
        ], written[0].get("conditioning")
        assert all(item["conditioning"] == [] for item in written[1:]), [
            i.get("conditioning") for i in written
        ]
        manifest = content_pipeline.load_json(package / "image-manifest.json")
        for item in manifest["items"]:
            assert item["prompt"].startswith("A realistic editorial photograph"), (
                item["prompt"][:80]
            )
            assert "five fingers" in item["prompt"], item["prompt"][-120:]
            assert "contact shadow" in item["prompt"], item["prompt"][-120:]
            # Unset target: the exclusions go inline (owner decision, 2026-10-26),
            # in a Constraints block after the scene, which stays free of negation.
            assert not item["negative_prompt"] and "Constraints: no " in item["prompt"], item["id"]
            scene = item["prompt"].split("Constraints:", 1)[0]
            assert not image_spec.negations(scene), scene
            assert item["spec_compiled"]["questions"], item["id"]
            assert not image_spec.freshness_errors(item), item["id"]

        content_pipeline.set_status(
            client,
            slug,
            "image_specs_ready",
            "Self-test advanced to image_specs_ready with compiled specs.",
        )

        for item in manifest["items"]:
            source = package / item["source"]
            with Image.open(source) as raw:
                raw.load()
                source_width, source_height = raw.size
            review_file = package / "reports" / f"{item['id']}-source-review-input.json"
            write_json(
                review_file,
                {
                    "reviewer": "self-test source reviewer",
                    "source_sha256": content_pipeline.file_sha256(source),
                    "source_width": source_width,
                    "source_height": source_height,
                    "provenance": item["provenance"],
                    "checklist": {
                        key: "passed"
                        for key in config["quality_gates"][
                            "image_source_review_checklist"
                        ]
                    },
                    "notes": "Deterministic raw source approval.",
                },
            )
            image_production.record_source_review(
                client,
                slug,
                item["id"],
                review_file.relative_to(package),
            )

        manifest = content_pipeline.load_json(package / "image-manifest.json")

        # Refusal 3: a prompt edited by hand after compilation is refused, so the
        # picture always matches the brief the reviewer will check it against.
        edited = content_pipeline.load_json(package / "image-manifest.json")
        edited["items"][0]["prompt"] += " Also a golden retriever."
        content_pipeline.write_json(package / "image-manifest.json", edited)
        try:
            image_production.process_manifest(client, slug)
        except RuntimeError as exc:
            assert "edited by hand" in str(exc), str(exc)
        else:
            raise AssertionError("A hand-edited image prompt was processed.")
        content_pipeline.write_json(package / "image-manifest.json", manifest)

        image_report = image_production.process_manifest(client, slug)
        assert image_report["passed"], image_report
        manifest = content_pipeline.load_json(package / "image-manifest.json")
        for item in manifest["items"]:
            with Image.open(package / item["output"]) as processed:
                assert processed.size == (item["width"], item["height"])
                assert processed.format == image_format
                assert "icc_profile" not in processed.info
            assert item["technical_report"]["metadata"]["passed"], item["id"]

            crops = image_production.write_review_crops(client, slug, item["id"])
            assert len(crops["crops"]) == 9, crops
            blank = image_production.write_review_template(client, slug, item["id"])
            assert blank["checks"] and blank["spec_questions"], blank

            review_file = package / "reports" / f"{item['id']}-visual-review.json"
            write_json(review_file, fixture_review(item, config, crops["image_sha256"]))

            # A review that has not answered every plausibility check cannot pass.
            thin_review = fixture_review(item, config, crops["image_sha256"])
            thin_review["plausibility"].pop("contact_shadows")
            thin_file = package / "reports" / f"{item['id']}-thin-review.json"
            write_json(thin_file, thin_review)
            try:
                image_production.mark_reviewed(
                    client,
                    slug,
                    item["id"],
                    "passed",
                    "Self-test incomplete review.",
                    "self-test reviewer",
                    thin_file,
                )
            except RuntimeError as exc:
                assert "contact_shadows" in str(exc), str(exc)
            else:
                raise AssertionError("An unanswered plausibility check passed review.")

            marked = image_production.mark_reviewed(
                client,
                slug,
                item["id"],
                "passed",
                "Self-test visual review.",
                "self-test reviewer",
                review_file,
            )
            assert marked["qa_plausibility"]["crops_reviewed"] == 9, marked
            assert not marked["qa_plausibility"]["failed"], marked
            assert marked["qa_plausibility"]["image_sha256"] == crops["image_sha256"]

        assert (
            content_pipeline.load_json(package / "article.json")["status"]
            == "images_qa_passed"
        )

        validation = content_pipeline.validate_package(client, slug, "publish")
        assert validation["passed"], validation["errors"]
        content_pipeline.set_status(
            client,
            slug,
            "publish_ready",
            "Self-test publish validation passed.",
        )
        assert (
            content_pipeline.load_json(package / "article.json")["status"]
            == "publish_ready"
        )
        print(f"  {image_format}: spec compiled, three refusals held, publish_ready")


def check_compile_spec_file() -> None:
    """compile-spec-file serves a client whose content runs through its own adapter."""
    reference = image_spec.REFERENCE_DIR
    example = reference / "image-spec.example.json"
    report = image_production.compile_spec_file(example, 1200, 630, "openai-gpt-image")
    assert report["valid"] and report["target"] == "inline_constraints", report.get("target")
    assert "Constraints: no " in report["prompt"] and not report["negative_prompt"], report["prompt"][-80:]
    assert report["questions"] and "conditioning" in report, list(report)
    with tempfile.TemporaryDirectory() as tmp:
        place = json.loads((reference / "image-spec.real-place.example.json").read_text(encoding="utf-8"))
        place = place.get("spec", place)
        sources = place["location"]["reference"]["sources"]
        ref_path = sources[0].get("path") or sources[0].get("url")
        place["location"]["reference"]["conditioning_images"] = [ref_path]
        wrapped = Path(tmp) / "hkt-style.json"
        wrapped.write_text(json.dumps({"spec": place}), encoding="utf-8")
        placed = image_production.compile_spec_file(wrapped, 1200, 630, "openai-gpt-image")
        assert placed["valid"], placed["errors"][:2]
        expected = {"role": "place", "path": ref_path, "rights": sources[0].get("rights", "")}
        assert expected in placed["conditioning"], placed["conditioning"]
        broken = dict(place)
        broken["camera"] = dict(place["camera"], tilt="sideways")
        bad = Path(tmp) / "broken.json"
        bad.write_text(json.dumps(broken), encoding="utf-8")
        refused = image_production.compile_spec_file(bad, 1200, 630)
        assert not refused["valid"] and refused["errors"] and "prompt" not in refused, refused
        # The review half, from files.
        picture = Path(tmp) / "cover-01.png"
        Image.new("RGB", (1200, 630), (90, 60, 40)).save(picture)
        crops = image_production.review_crops_file(picture, Path(tmp) / "crops")
        assert len(crops["crops"]) == crops["grid"] ** 2 and crops["image_sha256"], crops
        assert all(Path(c).name.startswith("cover-01-r") for c in crops["crops"]), crops["crops"][:2]
        with Image.open(crops["crops"][0]) as first:
            assert first.width == int((1200 / crops["grid"]) * crops["crop_scale"]), first.size
        review = image_production.review_template_file(
            example, 1200, 630, "openai-gpt-image", image_path=picture
        )
        assert set(review["spec_answers"]) == {q["id"] for q in report["questions"]}, (
            "questions differ from the compile"
        )
        assert review["image_sha256"] == crops["image_sha256"]
        assert review["image_id"] == "image-spec.example", review["image_id"]
        named = image_production.review_template_file(
            example, 1200, 630, "openai-gpt-image", image_id="cover-01"
        )
        assert named["image_id"] == "cover-01", named["image_id"]


def main() -> None:
    check_compile_spec_file()
    for image_format in ("WEBP", "AVIF"):
        run(image_format)
    print("CONTENT_PRODUCTION_SELFTEST_OK")


if __name__ == "__main__":
    main()
