"""Original test suite used to produce the real pytest XML fixtures.

This intentionally fails once per phase; it is not part of the project's
regression suite. Run scripts/generate_pytest_fixtures.py to regenerate XML.
"""
import os
import pytest


def test_stays_good():
    assert 2 + 2 == 4


def test_regression():
    assert os.environ["JUNIT_FIXTURE_PHASE"] == "before", "new diagnostic regression"


def test_recovery():
    assert os.environ["JUNIT_FIXTURE_PHASE"] == "after", "previous diagnostic failure"


@pytest.mark.skip(reason="optional feature is disabled")
def test_optional_feature():
    pass
