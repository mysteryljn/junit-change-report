"""Regenerate real pytest-produced XML; requires pytest==9.2.0 only for this script."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for phase in ("before", "after"):
    environment = dict(os.environ, JUNIT_FIXTURE_PHASE=phase)
    result = subprocess.run([
        sys.executable, "-m", "pytest", "junit_change_report/fixtures/pytest_cases.py",
        "--junitxml=junit_change_report/fixtures/pytest-%s.xml" % phase,
        "-o", "junit_suite_name=pytest-integration", "-q",
    ], cwd=root, env=environment)
    if result.returncode != 1:
        raise SystemExit("Expected exactly one intentionally failing pytest case; exit was " + str(result.returncode))
