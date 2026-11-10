import contextlib
import io
from importlib.resources import files
import json
from pathlib import Path
import tempfile
import unittest

from junit_change_report.cli import main
from junit_change_report.core import compare, read_run
from junit_change_report.report import render


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.before = self.root / "before.xml"
        self.after = self.root / "after.xml"
        self.write(self.before, '<testcase classname="C" name="x" time="1"/>')
        self.write(self.after, '<testcase classname="C" name="x" time="1"/>')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, content):
        path.write_text('<testsuite name="suite">' + content + '</testsuite>', encoding="utf-8")

    def result(self, **kwargs):
        return compare(self.before, self.after, **kwargs)

    def cli(self, *arguments):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(list(arguments))

    def test_identical_is_pass(self):
        report = self.result()
        self.assertFalse(report["gate_failed"])
        self.assertEqual(report["changes"], [])

    def test_real_pytest_outputs(self):
        fixture = Path(str(files("junit_change_report").joinpath("fixtures")))
        report = compare(fixture / "pytest-before.xml", fixture / "pytest-after.xml")
        self.assertEqual(report["baseline_cases"], 4)
        self.assertEqual(report["current_status"]["skipped"], 1)
        self.assertEqual(report["counts"]["new_failures"], 1)
        self.assertEqual(report["counts"]["recovered"], 1)

    def test_new_failure_and_recovery(self):
        self.write(self.before, '<testcase name="broken"><failure/></testcase><testcase name="good"/>')
        self.write(self.after, '<testcase name="broken"/><testcase name="good"><failure/></testcase>')
        result = self.result()
        self.assertEqual(result["counts"]["new_failures"], 1)
        self.assertEqual(result["counts"]["recovered"], 1)
        self.assertTrue(result["gate_failed"])

    def test_added_error_is_new_failure(self):
        self.write(self.after, '<testcase classname="C" name="x" time="1"/><testcase name="extra"><error/></testcase>')
        report = self.result()
        self.assertEqual(report["counts"]["added"], 1)
        self.assertEqual(report["current_status"]["error"], 1)
        self.assertEqual(report["counts"]["new_failures"], 1)

    def test_failed_to_skipped_is_not_recovery(self):
        self.write(self.before, '<testcase name="x"><failure/></testcase>')
        self.write(self.after, '<testcase name="x"><skipped/></testcase>')
        self.assertEqual(self.result()["counts"]["recovered"], 0)
        self.assertEqual(self.result()["counts"]["status_changes"], 1)

    def test_existing_failure_does_not_fail_new_failure_policy(self):
        for path in (self.before, self.after):
            self.write(path, '<testcase name="x"><failure/></testcase>')
        self.assertFalse(self.result()["gate_failed"])
        self.assertTrue(self.result(fail_on="any-failure")["gate_failed"])

    def test_removed_and_added(self):
        self.write(self.after, '<testcase name="replacement"/>')
        self.assertEqual(self.result()["counts"]["removed"], 1)
        self.assertEqual(self.result()["counts"]["added"], 1)

    def test_timing_requires_absolute_and_relative_threshold(self):
        self.write(self.after, '<testcase classname="C" name="x" time="1.2"/>')
        self.assertEqual(self.result(relative=.25, absolute=.1)["counts"]["timing_regressions"], 0)
        self.assertEqual(self.result(relative=.1, absolute=.5)["counts"]["timing_regressions"], 0)
        self.assertTrue(self.result(relative=.1, absolute=.1, fail_on="timing")["gate_failed"])

    def test_missing_time_is_not_zero(self):
        self.write(self.before, '<testcase classname="C" name="x"/>')
        self.assertEqual(self.result()["counts"]["timing_regressions"], 0)
        self.assertEqual(self.result()["missing_time"]["baseline"], 1)

    def test_zero_duration_is_valid(self):
        self.write(self.before, '<testcase classname="C" name="x" time="0"/>')
        self.assertEqual(self.result()["counts"]["timing_regressions"], 1)

    def test_no_timing_for_failed_tests(self):
        self.write(self.after, '<testcase classname="C" name="x" time="99"><failure/></testcase>')
        self.assertEqual(self.result()["counts"]["timing_regressions"], 0)

    def test_nested_suite_names_distinguish_identity(self):
        self.before.write_text('<testsuites><testsuite name="a"><testsuite name="inner"><testcase name="x"/></testsuite></testsuite><testsuite name="b"><testsuite name="inner"><testcase name="x"/></testsuite></testsuite></testsuites>', encoding="utf-8")
        cases, _ = read_run(self.before)
        self.assertEqual(len(cases), 2)
        self.assertIn((("a", "inner"), "", "x"), cases)

    def test_directory_merges_reports(self):
        directory = self.root / "reports"
        directory.mkdir()
        self.write(directory / "one.xml", '<testcase name="one"/>')
        self.write(directory / "two.xml", '<testcase name="two"/>')
        self.assertEqual(len(read_run(directory)[0]), 2)

    def test_duplicate_within_file_rejected(self):
        self.write(self.before, '<testcase name="x"/><testcase name="x"/>')
        with self.assertRaisesRegex(ValueError, "duplicate testcase"):
            read_run(self.before)

    def test_duplicate_across_files_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate testcase"):
            read_run(self.root)

    def test_invalid_times_rejected(self):
        for value in ("NaN", "inf", "-1", "bad"):
            with self.subTest(value=value):
                self.write(self.before, '<testcase name="x" time="%s"/>' % value)
                with self.assertRaises(ValueError):
                    read_run(self.before)

    def test_bad_root_and_malformed_xml(self):
        for text in ("<other/>", "<testsuite>"):
            self.before.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                read_run(self.before)

    def test_namespaced_xml(self):
        self.before.write_text('<testsuite xmlns="urn:test" name="s"><testcase name="x"/></testsuite>', encoding="utf-8")
        self.assertEqual(len(read_run(self.before)[0]), 1)

    def test_dtd_rejected_in_utf8_and_utf16(self):
        xml = '<!DOCTYPE testsuite [<!ENTITY secret "expanded">]><testsuite><testcase name="&secret;"/></testsuite>'
        for encoding in ("utf-8", "utf-16"):
            with self.subTest(encoding=encoding):
                self.before.write_bytes(xml.encode(encoding))
                with self.assertRaisesRegex(ValueError, "DTD"):
                    read_run(self.before)

    def test_empty_suite_allowed_but_empty_directory_rejected(self):
        self.write(self.before, "")
        self.assertEqual(len(read_run(self.before)[0]), 0)
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "no XML"):
            read_run(empty)

    def test_flaky_extension_warns_without_claiming_detection(self):
        self.write(self.after, '<testcase name="x"><flakyFailure>retry passed</flakyFailure></testcase>')
        cases, warnings = read_run(self.after)
        self.assertEqual(next(iter(cases.values())).status, "passed")
        self.assertIn("does not infer flakiness", warnings[0])

    def test_html_and_markdown_escape_untrusted_fields(self):
        self.write(self.after, '<testcase name="&lt;script&gt;|x"><failure message="&lt;img src=x onerror=alert(1)&gt;"/></testcase>')
        for format in ("html", "markdown"):
            output = render(self.result(), format)
            self.assertNotIn("<script>", output)
            self.assertNotIn("<img src=x", output)
            self.assertIn("&lt;script&gt;", output)

    def test_json_serializes_full_changes(self):
        self.write(self.after, '<testcase name="new"/>')
        data = json.loads(render(self.result(), "json"))
        self.assertEqual(data["counts"]["added"], 1)

    def test_invalid_thresholds(self):
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.result(relative=value)

    def test_cli_all_exit_codes(self):
        output = self.root / "report.json"
        common = ["compare", str(self.before), str(self.after), "--output", str(output), "--format", "json"]
        self.assertEqual(self.cli(*common), 0)
        self.write(self.after, '<testcase classname="C" name="x"><failure/></testcase>')
        self.assertEqual(self.cli(*common), 1)
        self.after.write_text("invalid", encoding="utf-8")
        self.assertEqual(self.cli(*common), 2)
        self.assertTrue(json.loads(output.read_text())["gate_failed"])

    def test_cli_does_not_overwrite_source(self):
        original = self.before.read_bytes()
        self.assertEqual(self.cli("compare", str(self.before), str(self.after), "--output", str(self.before)), 2)
        self.assertEqual(self.before.read_bytes(), original)

    def test_demo_creates_report(self):
        output = self.root / "demo.html"
        self.assertEqual(self.cli("demo", "--output", str(output)), 0)
        self.assertIn("2 new failures", output.read_text(encoding="utf-8"))

    def test_version(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(["--version"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("0.1.0", output.getvalue())


if __name__ == "__main__":
    unittest.main()
