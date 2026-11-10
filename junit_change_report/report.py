"""Portable report rendering. No external scripts, images, fonts or services."""
from html import escape
import json
import os
from pathlib import Path
import tempfile


def _label(case):
    return " / ".join(case["suites"] + [case["classname"], case["name"]]) if isinstance(case["suites"], list) else " / ".join(list(case["suites"]) + [case["classname"], case["name"]])


def _md(value):
    return escape(str(value)).replace("|", "\\|").replace("\n", "<br>").replace("\r", "")


def render(data, format="html"):
    if format == "json":
        return json.dumps(data, indent=2, ensure_ascii=True) + "\n"
    rows = []
    for change in data["changes"]:
        before, after = change["before"], change["after"]
        case = after or before
        old_time = "unknown" if not before or before["seconds"] is None else str(before["seconds"])
        new_time = "unknown" if not after or after["seconds"] is None else str(after["seconds"])
        rows.append([_label(case), ", ".join(change["reasons"]),
                     before["status"] if before else "absent", after["status"] if after else "absent",
                     old_time + " → " + new_time, case["message"]])
    verdict = "FAIL" if data["gate_failed"] else "PASS"
    summary = ("%s · %s baseline / %s current cases · %s new failures · %s recoveries · %s timing regressions"
               % (verdict, data["baseline_cases"], data["current_cases"], data["counts"]["new_failures"],
                  data["counts"]["recovered"], data["counts"]["timing_regressions"]))
    notes = ["Policy: %s. Timing needs both >= %.3fs and >= %.1f%% growth on passing tests."
             % (data["policy"]["fail_on"], data["policy"]["absolute_seconds"], data["policy"]["relative"] * 100),
             "Missing times are unknown, not zero. Skipped tests are not recoveries. Duplicate identities are rejected."] + data["warnings"]
    headers = ["Test", "Changes", "Before", "After", "Seconds", "Message"]
    if format == "markdown":
        return ("# JUnit change report\n\n" + _md(summary) + "\n\n| " + " | ".join(headers) +
                " |\n| " + " | ".join(["---"] * len(headers)) + " |\n" +
                "".join("| " + " | ".join(_md(cell) for cell in row) + " |\n" for row in rows) +
                "\n" + "\n".join("- " + _md(note) for note in notes) + "\n")
    if format != "html":
        raise ValueError("unsupported report format")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            "<title>JUnit change report</title><style>body{font:16px system-ui;margin:32px;color:#172b43;background:#f6f8fb}"
            "h1{color:#163963}table{border-collapse:collapse;background:white;width:100%}td,th{padding:10px;border:1px solid #ccd5df;"
            "text-align:left;overflow-wrap:anywhere}th{background:#e2edf7}pre{white-space:pre-wrap}.summary{padding:18px;background:#e2edf7}"
            "</style><h1>JUnit change report</h1><p class='summary'>" + escape(summary) + "</p><table><thead><tr>" +
            "".join("<th>" + escape(h) + "</th>" for h in headers) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join("<td>" + escape(str(cell)) + "</td>" for cell in row) + "</tr>" for row in rows) +
            "</tbody></table><ul>" + "".join("<li>" + escape(note) + "</li>" for note in notes) + "</ul></html>\n")


def write_report(path, content):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
