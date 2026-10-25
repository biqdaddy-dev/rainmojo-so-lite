#!/usr/bin/env python3
"""Run every packaged regression test for rainmojo-so-lite.

One entry point so a change can be checked in one command:

    python skills/rainmojo-so-lite/scripts/regression.py

Each test runs in its own process and must print its own OK marker. A test that
exits non-zero, or that exits zero without its marker, fails the run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

TESTS = [
    (
        "T1 content pipeline unit smoke: config merge, placeholder domain, image format",
        [sys.executable, str(SCRIPTS / "content_pipeline.py"), "--self-test"],
        "SELF-TEST PASS",
    ),
    (
        "T2 image spec: physics and logic contradictions refused, prompt compiled, review gated",
        [sys.executable, str(SCRIPTS / "image_spec_contract_test.py")],
        "IMAGE_SPEC_CONTRACT_TEST_OK",
    ),
    (
        "T3 content production end to end: spec, compile, three refusals, publish_ready",
        [sys.executable, str(SCRIPTS / "content_pipeline_selftest.py")],
        "CONTENT_PRODUCTION_SELFTEST_OK",
    ),
]


def main() -> int:
    failures: list[str] = []
    for title, command, marker in TESTS:
        print(title)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0 or marker not in result.stdout:
            tail = (result.stdout + "\n" + result.stderr).strip()[-2000:]
            print("  FAIL\n" + tail)
            failures.append(title)
        else:
            print("  PASS")
    if failures:
        print(f"\nREGRESSION FAIL: {len(failures)} of {len(TESTS)}")
        for title in failures:
            print("  - " + title)
        return 1
    print(f"\nREGRESSION PASS: {len(TESTS)} of {len(TESTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
