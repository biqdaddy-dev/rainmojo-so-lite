"""Unit checks for version_gate.py: python -I tooling/version_gate_test.py"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import version_gate  # noqa: E402


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plugin(root: Path, version: str = "1.2.3", copies: str | None = None) -> None:
    manifest = json.dumps({"name": "p", "version": version})
    write(root, ".claude-plugin/plugin.json", manifest)
    write(root, "plugin.json", json.dumps({"name": "p", "version": copies or version}))
    write(root, ".claude-plugin/marketplace.json",
          json.dumps({"plugins": [{"name": "p", "version": version}]}))
    write(root, "CHANGELOG.md", f"# Changelog\n\n## {version} (2026-11-12)\n")
    write(root, "README.md", "See [CHANGELOG.md](CHANGELOG.md).\n")
    write(root, "skills/a/SKILL.md", "---\nname: a\ndescription: x\n---\nbody version: 9\n")


class GateTest(unittest.TestCase):
    def check(self, **kw) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin(root, **{k: v for k, v in kw.items() if k in ("version", "copies")})
            for rel, text in (kw.get("extra") or {}).items():
                write(root, rel, text)
            return version_gate.check(root)

    def test_clean(self):
        self.assertEqual(self.check(), [])

    def test_stale_copy(self):
        self.assertIn("plugin.json: version 1.0.0 != .claude-plugin/plugin.json 1.2.3",
                      self.check(copies="1.0.0"))

    def test_marketplace(self):
        found = self.check(extra={".claude-plugin/marketplace.json":
                                  json.dumps({"plugins": [{"name": "p", "version": "1.0"}]})})
        self.assertTrue(any("marketplace.json" in f for f in found))

    def test_frontmatter_version(self):
        found = self.check(extra={"agents/x.md": "---\nname: x\nmetadata:\n  version: 2.0\n---\n"})
        self.assertTrue(any("agents/x.md" in f for f in found))

    def test_readme_version(self):
        found = self.check(extra={"README.md": "Free edition. เวอร์ชัน 1.2.3\n"})
        self.assertTrue(any(f.startswith("README.md") for f in found))

    def test_changelog_behind(self):
        found = self.check(extra={"CHANGELOG.md": "## 1.2.2 (2026-11-01)\n"})
        self.assertIn("CHANGELOG.md: newest section is 1.2.2, .claude-plugin/plugin.json is 1.2.3",
                      found)

    def test_unreleased_on_top_is_fine(self):
        self.assertEqual(self.check(extra={"CHANGELOG.md":
                                           "## Unreleased\n\n- x\n\n## 1.2.3 (2026-11-12)\n"}), [])

    def test_this_repo(self):
        self.assertEqual(version_gate.check(), [])


if __name__ == "__main__":
    unittest.main()
