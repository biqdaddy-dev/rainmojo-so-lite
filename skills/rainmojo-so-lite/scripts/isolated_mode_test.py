"""Plugin scripts keep working under ``python -I`` (LITE-009, port of rainmojo-so RSO-012).

    python skills/rainmojo-so-lite/scripts/isolated_mode_test.py

Agents run scripts with ``-I``, which leaves out both the script's own folder
and the user site-packages. In the DP-024 baseline, 26 of 30 so-audit runs lost
a step to "Missing dependency" or "No module named client_workspace"; lite has the
same scripts. The fix is
``_isolated_mode``, imported first by every script that needs a third-party or
sibling module. These tests check two things:
  1. every such script imports it before the first of those imports;
  2. under ``-I`` the module really brings back the user site-packages, using a
     probe package placed in a temporary user site.
"""

import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
THIRD_PARTY = {
    "requests", "bs4", "lxml", "PIL", "numpy", "playwright", "yaml",
    "jsonschema", "markdown", "weasyprint", "pypdf", "openpyxl", "pandas", "mcp",
}
# Tests, selftests and CI gates run under plain python in CI, never from an agent.
NOT_AGENT_RUN = re.compile(r"(_test|_selftest|_gate)\.py$")


def _imported(node):
    """Top-level module names a statement imports, at any depth inside it."""
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            names.add(n.module.split(".")[0])
    return names


class EveryScriptImportsIsolatedMode(unittest.TestCase):
    def test_import_comes_before_third_party_and_sibling_imports(self):
        siblings = {p.stem for p in SCRIPTS.glob("*.py")} - {"_isolated_mode"}
        needed = THIRD_PARTY | siblings
        checked, missing = 0, []
        for path in sorted(SCRIPTS.glob("*.py")):
            if NOT_AGENT_RUN.search(path.name) or path.stem == "_isolated_mode":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if not (_imported(tree) & (needed - {path.stem})):
                continue
            checked += 1
            for stmt in tree.body:
                names = _imported(stmt)
                if "_isolated_mode" in names:
                    break
                if names & (needed - {path.stem}):
                    missing.append(f"{path.name}:{stmt.lineno} imports {sorted(names & needed)} first")
                    break
                if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
                    missing.append(f"{path.name}: no top-level import of _isolated_mode")
                    break
        self.assertGreaterEqual(checked, 9, "the scan found too few scripts; did the folder move?")
        self.assertEqual(missing, [], "\n".join(missing))


class IsolatedModeRestoresUserSite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        # site.getusersitepackages() reads APPDATA on Windows and HOME elsewhere;
        # -I ignores PYTHON* variables but not these.
        self.env = dict(os.environ, APPDATA=str(home / "AppData"), HOME=str(home))
        for key in ("PYTHONUSERBASE", "PYTHONPATH", "PYTHONIOENCODING"):
            self.env.pop(key, None)
        user_site = self._python("import site; print(site.getusersitepackages())").stdout.strip()
        self.assertTrue(user_site.startswith(str(home)), user_site)
        probe = Path(user_site) / "lite009_probe"
        probe.mkdir(parents=True)
        (probe / "__init__.py").write_text("FOUND = True\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _python(self, code):
        return subprocess.run(
            [sys.executable, "-I", "-c", code], capture_output=True, text=True,
            encoding="utf-8", env=self.env, cwd=self.tmp.name, timeout=60,
        )

    def test_without_the_module_the_user_site_is_hidden(self):
        run = self._python("import lite009_probe")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("No module named 'lite009_probe'", run.stderr)

    def test_with_the_module_the_user_site_is_back(self):
        code = (
            f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); "
            "import _isolated_mode, lite009_probe; print(lite009_probe.FOUND)"
        )
        run = self._python(code)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "True")

    def test_current_directory_stays_off_the_path(self):
        (Path(self.tmp.name) / "planted_lite009.py").write_text("raise SystemExit('planted ran')\n", encoding="utf-8")
        code = (
            f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); import _isolated_mode\n"
            "try:\n    import planted_lite009\nexcept ModuleNotFoundError:\n    print('not importable')"
        )
        run = self._python(code)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "not importable")


if __name__ == "__main__":
    unittest.main()
