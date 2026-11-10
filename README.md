# junit-change-report

Turn two JUnit XML runs into a reviewable regression report. The tool accepts a
file or a directory of XML shards, keeps nested suite identity, and reports
new failures, recoveries, additions/removals, skipped/error changes, and
material duration regressions. It never executes test commands or fetches data.

## Install and run

```bash
python -m pip install .
python -m junit_change_report demo --output demo.html
python -m junit_change_report compare before/ after/ --output review.html
python -m junit_change_report compare before.xml after.xml --format markdown --output review.md
```

Exit status is `0` for a passing gate, `1` for a selected regression, and `2`
for invalid input or an unsupported report. The default gate fails only for a
test that was not already failed/error. Use `--fail-on any-failure`, `timing`,
`regression`, or `none`. A duration regression needs both `--absolute` seconds
and `--relative` proportion; missing `time` is reported as unknown, never zero.

The default identity is the complete nested suite path, `classname`, and
`name`. Duplicate identities are rejected so merging shards cannot silently
discard a result. Rerun/flaky extension elements produce a warning; this
version does not claim to infer flakiness. XML DTDs and entities are rejected.

Reports are standalone HTML, Markdown, or JSON. HTML escapes all producer
fields and contains no CDN. `demo` runs from an installed wheel in any working
directory. `--version` prints `0.1.0`.

## Fixture provenance and limits

`fixtures/before.xml` and `after.xml` are synthetic, hand-authored JUnit
examples. `fixtures/pytest-before.xml` and `pytest-after.xml` are real outputs
from pytest 9.2.0 on Python 3.13 / Windows, generated from the included
`pytest_cases.py`; see `fixtures/PROVENANCE.md` and
`scripts/generate_pytest_fixtures.py`. The runtime has no pytest dependency.

JUnit XML has producer-specific extensions. This project supports the common
`testsuites`/`testsuite`/`testcase` subset and preserves a source path in each
record. It does not parse arbitrary runner metadata or prove test flakiness.

## Development

```bash
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . --wheel-dir dist
```

MIT licensed. Contributions should include a regression test and fixture
provenance.
