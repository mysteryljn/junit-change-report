import argparse
from importlib.resources import files
from pathlib import Path
import sys

from . import __version__
from .core import compare
from .report import render, write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare JUnit XML runs and publish an offline review report.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("compare", help="Compare two XML files or directories")
    check.add_argument("baseline", type=Path)
    check.add_argument("current", type=Path)
    demo = commands.add_parser("demo", help="Run packaged synthetic JUnit examples offline")
    for subparser in (check, demo):
        subparser.add_argument("--output", type=Path, default=Path("junit-report.html"))
        subparser.add_argument("--format", choices=("html", "markdown", "json"), default="html")
        subparser.add_argument("--relative", type=float, default=0.25, help="Minimum proportional duration growth (default .25)")
        subparser.add_argument("--absolute", type=float, default=0.1, help="Minimum duration growth in seconds")
        subparser.add_argument("--fail-on", choices=("new-failure", "any-failure", "timing", "regression", "none"), default="new-failure")
    demo.set_defaults(fail_on="none")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            fixture = files("junit_change_report").joinpath("fixtures")
            baseline, current = Path(str(fixture.joinpath("before.xml"))), Path(str(fixture.joinpath("after.xml")))
        else:
            baseline, current = args.baseline, args.current
        output = args.output.resolve()
        for source in (baseline, current):
            if output == source.resolve() or (source.is_dir() and output in [p.resolve() for p in source.rglob("*.xml")]):
                raise ValueError("report output must not overwrite an input XML file")
        data = compare(baseline, current, args.relative, args.absolute, args.fail_on)
        write_report(args.output, render(data, args.format))
        print("%s: wrote %s (%d new failures, %d timing regressions)" %
              ("FAIL" if data["gate_failed"] else "PASS", args.output,
               data["counts"]["new_failures"], data["counts"]["timing_regressions"]))
        return 1 if data["gate_failed"] else 0
    except (OSError, ValueError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
