"""Read JUnit reports without trusting producer counters or executing XML DTDs."""
from dataclasses import asdict, dataclass
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from xml.parsers import expat


@dataclass(frozen=True)
class Case:
    suites: tuple
    classname: str
    name: str
    status: str
    seconds: float | None
    message: str
    source: str

    @property
    def identity(self):
        return self.suites, self.classname, self.name

    def record(self):
        return asdict(self)


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _safe_xml(data, source):
    # Expat detects declarations after encoding detection (including UTF-16).
    # Scanning raw bytes for <!DOCTYPE would miss such encodings.
    parser = expat.ParserCreate()

    def reject(*args):
        raise ValueError("DTD and entity declarations are not supported: " + source)

    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    try:
        parser.Parse(data, True)
        root = ET.fromstring(data)
    except (expat.ExpatError, ET.ParseError) as exc:
        raise ValueError("invalid XML in %s: %s" % (source, exc)) from exc
    if _tag(root) not in ("testsuite", "testsuites"):
        raise ValueError("expected testsuite or testsuites root: " + source)
    return root


def read_run(location):
    location = Path(location)
    if location.is_dir():
        files = sorted(location.rglob("*.xml"))
        if not files:
            raise ValueError("no XML reports in " + str(location))
    else:
        files = [location]
    cases, warnings = {}, []
    for path in files:
        data = path.read_bytes()
        if len(data) > 64 * 1024 * 1024:
            raise ValueError("XML file exceeds the 64 MiB input limit: " + str(path))
        root = _safe_xml(data, str(path))
        stack = [(root, ())]
        while stack:
            node, suites = stack.pop()
            kind = _tag(node)
            if kind == "testsuite":
                suites = suites + (node.get("name") or "<unnamed>",)
            if kind == "testcase":
                name = node.get("name")
                if not name:
                    raise ValueError("testcase requires a non-empty name: " + str(path))
                seconds = node.get("time")
                if seconds is not None:
                    try:
                        seconds = float(seconds)
                    except ValueError as exc:
                        raise ValueError("invalid testcase time: " + name) from exc
                    if not math.isfinite(seconds) or seconds < 0:
                        raise ValueError("testcase time must be finite and non-negative: " + name)
                children = {_tag(child) for child in node}
                status = ("error" if "error" in children else "failed" if "failure" in children
                          else "skipped" if "skipped" in children else "passed")
                messages = []
                for child in node:
                    if _tag(child) in ("failure", "error", "skipped"):
                        messages.append(" ".join(filter(None, (child.get("message"), child.text))))
                if children.intersection({"flakyFailure", "flakyError", "rerunFailure", "rerunError"}):
                    warnings.append("Rerun/flaky extension ignored for %s; this tool does not infer flakiness." % name)
                case = Case(suites, node.get("classname", ""), name, status, seconds,
                            "\n".join(messages), str(path))
                if case.identity in cases:
                    previous = cases[case.identity]
                    raise ValueError("duplicate testcase identity %r in %s and %s; merge shards with unique suite names first"
                                     % (case.identity, previous.source, path))
                cases[case.identity] = case
            else:
                stack.extend((child, suites) for child in reversed(list(node))
                             if _tag(child) in ("testsuite", "testsuites", "testcase"))
    return cases, sorted(set(warnings))


def compare(baseline, current, relative=0.25, absolute=0.1, fail_on="new-failure"):
    if not math.isfinite(relative) or not math.isfinite(absolute) or relative < 0 or absolute < 0:
        raise ValueError("timing thresholds must be finite and non-negative")
    if fail_on not in ("new-failure", "any-failure", "timing", "regression", "none"):
        raise ValueError("unknown failure policy")
    before, before_warnings = read_run(baseline)
    after, after_warnings = read_run(current)
    changes = []
    counts = {key: 0 for key in ("added", "removed", "new_failures", "recovered", "status_changes", "timing_regressions")}
    failures = {"failed", "error"}
    for identity in sorted(before.keys() | after.keys()):
        old, new = before.get(identity), after.get(identity)
        reasons = []
        if old is None:
            reasons.append("added")
        if new is None:
            reasons.append("removed")
        if new and new.status in failures and (old is None or old.status not in failures):
            reasons.append("new_failures")
        if old and new:
            if old.status in failures and new.status == "passed":
                reasons.append("recovered")
            if old.status != new.status:
                reasons.append("status_changes")
            if (old.status == new.status == "passed" and old.seconds is not None and
                    new.seconds is not None):
                delta = new.seconds - old.seconds
                if delta > 0 and delta >= absolute and delta >= old.seconds * relative:
                    reasons.append("timing_regressions")
        if reasons:
            for reason in reasons:
                counts[reason] += 1
            changes.append({"reasons": reasons, "before": old.record() if old else None,
                            "after": new.record() if new else None})
    current_status = {status: sum(case.status == status for case in after.values())
                      for status in ("passed", "failed", "error", "skipped")}
    fail = (fail_on == "new-failure" and counts["new_failures"] > 0 or
            fail_on == "any-failure" and current_status["failed"] + current_status["error"] > 0 or
            fail_on == "timing" and counts["timing_regressions"] > 0 or
            fail_on == "regression" and counts["new_failures"] + counts["timing_regressions"] > 0)
    return {"tool": "junit-change-report", "schema_version": 1,
            "baseline_cases": len(before), "current_cases": len(after),
            "current_status": current_status, "counts": counts, "changes": changes,
            "warnings": sorted(set(before_warnings + after_warnings)),
            "missing_time": {"baseline": sum(c.seconds is None for c in before.values()),
                             "current": sum(c.seconds is None for c in after.values())},
            "policy": {"fail_on": fail_on, "relative": relative, "absolute_seconds": absolute},
            "gate_failed": bool(fail)}
