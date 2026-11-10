"""Tests for forge-dashboard/chart.py: every chart type is valid, accessible SVG; data is escaped,
never run; axis ticks are 1-2-5 steps; nonsense is refused with exit 2 and nothing is written."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT, load, symlink  # noqa: E402

chart = load("forge-dashboard", "chart")
SCRIPT = os.path.join(ROOT, "forge-dashboard", "chart.py")
TOKENS = os.path.join(ROOT, "forge-design", "tokens.json")
SVG = "{http://www.w3.org/2000/svg}"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
REVENUE = [1200, 1100, 1450, 1380, 1720, 1900]


def series(name, values, labels=MONTHS):
    return {"name": name, "points": [[label, value] for label, value in zip(labels, values)]}


def run(*args):
    """Run main() and return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = chart.main(list(args))
    return code, out.getvalue(), err.getvalue()


class ChartCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)

    def write(self, data, name="data.json"):
        path = os.path.join(self.folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def draw(self, data, kind, *more):
        """The SVG text for DATA; fails the test when chart.py refuses it."""
        code, out, err = run(self.write(data), "--type", kind, *more)
        self.assertEqual(code, 0, err)
        return out

    def refuse(self, data, kind, *more):
        """The error message for DATA; fails the test when chart.py accepts it."""
        code, out, err = run(self.write(data), "--type", kind, *more)
        self.assertEqual(code, 2, "expected a refusal, got: " + out[:200])
        self.assertEqual(out, "", "nothing is written on bad input")
        self.assertTrue(err.startswith("error: "), err)
        return err


class EveryType(ChartCase):
    DATA = {"title": "Revenue per month", "unit": "EUR", "series": [series("Revenue", REVENUE)]}

    def test_each_type_is_valid_accessible_svg(self):
        for kind in ("line", "area", "bar", "spark", "donut"):
            with self.subTest(kind=kind):
                svg = self.draw(self.DATA, kind)
                root = ET.fromstring(svg)  # well-formed XML
                self.assertEqual(root.tag, SVG + "svg")
                self.assertEqual(root.get("role"), "img")
                title, desc = root.find(SVG + "title"), root.find(SVG + "desc")
                self.assertEqual(title.text, "Revenue per month")
                self.assertEqual(root.get("aria-labelledby"), "%s %s" % (title.get("id"), desc.get("id")))
                self.assertIn("EUR", desc.text)
                self.assertTrue(svg.isascii())

    def test_summary_has_first_last_lowest_and_highest(self):
        desc = ET.fromstring(self.draw(self.DATA, "line")).find(SVG + "desc").text
        for part in ("Revenue: 6 points", "first 1,200 (2026-01)", "last 1,900 (2026-06)",
                     "lowest 1,100 (2026-02)", "highest 1,900 (2026-06)"):
            self.assertIn(part, desc)

    def test_donut_summary_has_the_total_and_shares(self):
        data = {"series": [series("Channel", [60, 30, 10], ["Web", "App", "Phone"])]}
        desc = ET.fromstring(self.draw(data, "donut")).find(SVG + "desc").text
        self.assertIn("Total 100", desc)
        self.assertIn("Web 60 (60%)", desc)

    def test_output_is_self_contained(self):
        for kind in ("line", "area", "bar", "spark", "donut"):
            svg = self.draw(self.DATA, kind, "--tokens", TOKENS)
            self.assertEqual(svg.count("http"), 1, "only the xmlns namespace")
            for banned in ("<script", "style=", "href", "url(", "@import", "onload", "<image", "<foreignObject"):
                self.assertNotIn(banned, svg)

    def test_title_option_and_sizes(self):
        root = ET.fromstring(self.draw(self.DATA, "line", "--title", "Omzet", "--width", "800", "--height", "300"))
        self.assertEqual(root.find(SVG + "title").text, "Omzet")
        self.assertEqual((root.get("width"), root.get("height"), root.get("viewBox")), ("800", "300", "0 0 800 300"))
        spark = ET.fromstring(self.draw(self.DATA, "spark"))
        self.assertEqual((spark.get("width"), spark.get("height")), ("120", "32"))
        self.assertIsNone(spark.find(SVG + "text"), "a sparkline has no axis labels")

    def test_two_charts_on_one_page_get_different_ids(self):
        one = ET.fromstring(self.draw(self.DATA, "line")).find(SVG + "title").get("id")
        two = ET.fromstring(self.draw(self.DATA, "bar")).find(SVG + "title").get("id")
        self.assertNotEqual(one, two)


class Escaping(ChartCase):
    def test_markup_in_data_comes_out_as_text(self):
        attack = "<script>alert(1)</script>"
        breakout = '"><svg onload="alert(2)">'
        data = {"title": attack, "unit": "<b>", "series": [
            series(attack, [1, 2, 3], [attack, breakout, "ok"]), series(breakout, [3, 2, 1], ["a", "b", "c"])]}
        for kind in ("line", "area", "bar"):
            with self.subTest(kind=kind):
                svg = self.draw(data, kind)
                self.assertNotIn("<script", svg)
                self.assertNotIn("onload=\"", svg)
                self.assertIn("&lt;script&gt;", svg)
                root = ET.fromstring(svg)
                self.assertEqual({node.tag for node in root.iter()} - {
                    SVG + name for name in ("svg", "title", "desc", "line", "text", "rect", "polyline",
                                            "polygon", "circle")}, set())
                self.assertEqual(root.find(SVG + "title").text, attack)  # shown as text, not run
                self.assertEqual(len(root.findall(SVG + "svg")), 0)

    def test_donut_and_title_option_are_escaped_too(self):
        data = {"series": [series("x", [1, 2], ["<img src=x onerror=alert(1)>", "b & c"])]}
        svg = self.draw(data, "donut", "--title", "</title><script>x</script>")
        self.assertNotIn("<script", svg)
        self.assertNotIn("<img", svg)
        self.assertIn("b &amp; c", svg)
        ET.fromstring(svg)

    def test_other_alphabets_and_control_characters(self):
        data = {"title": "Café € \U0001f600", "series": [series("Ж", [1, 2], ["a\x00b\x1b[31m", "\ud800"])]}
        svg = self.draw(json.dumps(data), "line")
        self.assertTrue(svg.isascii())
        self.assertNotIn("\x1b", svg)
        root = ET.fromstring(svg)
        self.assertEqual(root.find(SVG + "title").text, "Café € \U0001f600")

    def test_long_labels_are_cut_in_the_chart_but_whole_in_the_summary(self):
        name = "A very long series name that would run off the side of the chart"
        data = {"series": [series(name, [1, 2, 3], ["a", "b", "c"]), series("Short", [3, 2, 1], ["a", "b", "c"])]}
        root = ET.fromstring(self.draw(data, "line"))
        shown = [node.text for node in root.iter(SVG + "text")]
        self.assertIn("A very long...", shown)
        self.assertIn(name, root.find(SVG + "desc").text)


class Axes(ChartCase):
    def test_ticks_are_1_2_5_steps(self):
        self.assertEqual(chart.ticks(0, 1900), [0, 500, 1000, 1500, 2000])
        self.assertEqual(chart.ticks(0, 9), [0, 2, 4, 6, 8, 10])
        self.assertEqual(chart.ticks(0, 43), [0, 10, 20, 30, 40, 50])
        self.assertEqual(chart.ticks(-40, 120), [-50, 0, 50, 100, 150])
        self.assertEqual(chart.ticks(0.1, 0.9), [0, 0.2, 0.4, 0.6, 0.8, 1])
        self.assertEqual(chart.ticks(1100, 1900), [1000, 1200, 1400, 1600, 1800, 2000])
        for low, high in ((0, 7), (3, 3), (0, 0), (-5, -5), (12345, 987654), (0.001, 0.002)):
            marks = chart.ticks(low, high)
            self.assertTrue(marks[0] <= low and marks[-1] >= high and 2 <= len(marks) <= 12, (low, high, marks))
            step = marks[1] - marks[0]
            digit = step / 10 ** __import__("math").floor(__import__("math").log10(step))
            self.assertIn(round(digit, 6), (1, 2, 5, 10), (low, high, marks))

    def test_number_format(self):
        self.assertEqual([chart.fmt(value) for value in (1200, 0.5, 1234.5, -40, 2.0, 0, -0.001, 1e6)],
                         ["1,200", "0.5", "1,234.5", "-40", "2", "0", "0", "1,000,000"])

    def labels(self, data, kind, *more):
        return [node.text for node in ET.fromstring(self.draw(data, kind, *more)).iter(SVG + "text")]

    def test_bars_and_areas_stand_on_zero_and_a_line_fits_its_data(self):
        data = {"series": [series("Revenue", REVENUE)]}
        self.assertIn("0", self.labels(data, "bar"))
        self.assertIn("0", self.labels(data, "area"))
        line = self.labels(data, "line")
        self.assertNotIn("0", line)
        self.assertIn("1,000", line)

    def test_negative_bars_hang_under_the_zero_line(self):
        data = {"series": [series("Result", [50, -40, 20], ["a", "b", "c"])]}
        root = ET.fromstring(self.draw(data, "bar"))
        zero = [node for node in root.iter(SVG + "line") if node.get("stroke-opacity") is None][0]
        bars = list(root.iter(SVG + "rect"))
        self.assertEqual(len(bars), 3)
        baseline = float(zero.get("y1"))
        self.assertAlmostEqual(float(bars[0].get("y")) + float(bars[0].get("height")), baseline, delta=0.2)
        self.assertAlmostEqual(float(bars[1].get("y")), baseline, delta=0.2)  # the negative one starts at zero
        self.assertEqual(bars[1].find(SVG + "title").text, "b, Result: -40")

    def test_extreme_values_draw(self):
        for values in ([0, 0, 0], [5], [1e12, 2e12], [-3, -1], [0.001, 0.002], [7, 7, 7]):
            data = {"series": [series("x", values, ["a", "b", "c"])]}
            for kind in ("line", "area", "bar", "spark"):
                svg = self.draw(data, kind)
                self.assertNotIn("nan", svg.lower())
                self.assertNotIn("inf", svg.lower())

    def test_many_points_thin_out_the_x_labels(self):
        data = {"series": [series("x", list(range(200)), ["d%03d" % day for day in range(200)])]}
        shown = [text for text in self.labels(data, "line") if text.startswith("d")]
        self.assertTrue(2 <= len(shown) <= 10, shown)


class SeriesLabels(ChartCase):
    def many(self, count):
        return {"series": [series("S%d" % index, [index, index + 1, index + 2], ["a", "b", "c"])
                           for index in range(1, count + 1)]}

    def test_every_series_is_labelled_by_name(self):
        for kind, count in (("line", 2), ("line", 4), ("line", 6), ("area", 3), ("bar", 2), ("bar", 6)):
            with self.subTest(kind=kind, count=count):
                root = ET.fromstring(self.draw(self.many(count), kind))
                shown = [node.text for node in root.iter(SVG + "text")]
                for index in range(1, count + 1):
                    self.assertIn("S%d" % index, shown)

    def test_one_series_needs_no_label(self):
        shown = [node.text for node in ET.fromstring(self.draw(self.many(1), "line")).iter(SVG + "text")]
        self.assertNotIn("S1", shown)

    def test_direct_labels_sit_at_the_line_ends_and_do_not_overlap(self):
        data = {"series": [series("A", [1, 5], ["a", "b"]), series("B", [2, 5], ["a", "b"]), series("C", [9, 5.01], ["a", "b"])]}
        root = ET.fromstring(self.draw(data, "line"))
        spots = sorted(float(node.get("y")) for node in root.iter(SVG + "text") if node.text in ("A", "B", "C"))
        self.assertTrue(all(later - earlier >= 12.9 for earlier, later in zip(spots, spots[1:])), spots)

    def test_lines_differ_by_dash_pattern_as_well_as_colour(self):
        root = ET.fromstring(self.draw(self.many(4), "line"))
        dashes = [node.get("stroke-dasharray") for node in root.iter(SVG + "polyline")]
        self.assertEqual(len(set(dashes)), 4)

    def test_donut_lists_each_part_with_value_and_share(self):
        data = {"unit": "orders", "series": [series("Channel", [60, 30, 10, 0], ["Web", "App", "Phone", "Fax"])]}
        root = ET.fromstring(self.draw(data, "donut"))
        shown = [node.text for node in root.iter(SVG + "text")]
        for line in ("Web: 60 (60%)", "App: 30 (30%)", "Phone: 10 (10%)", "Fax: 0 (0%)", "100", "orders"):
            self.assertIn(line, shown)
        self.assertEqual(len(list(root.iter(SVG + "circle"))), 3, "a part of zero has no arc")


class Colours(ChartCase):
    DATA = {"series": [series("A", [1, 2], ["a", "b"]), series("B", [2, 1], ["a", "b"]), series("C", [3, 3], ["a", "b"])]}

    def tokens(self, **colour):
        base = {"bg": "#ffffff", "text": "#14171c", "accent": "#0f766e"}
        base.update(colour)
        return self.write({"color": {key: value for key, value in base.items() if value is not None}}, "tokens.json")

    def report(self, *more):
        code, out, err = run(self.write(self.DATA), "--type", "line", "--json", *more)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_without_tokens_the_theme_styles_it(self):
        svg = self.draw(self.DATA, "line")
        self.assertIn("var(--color-chart-1, var(--color-accent, currentColor))", svg)
        self.assertIn("var(--color-chart-3, var(--color-accent, currentColor))", svg)
        self.assertIn("var(--color-text, currentColor)", svg)
        self.assertNotIn("#", svg.split("</desc>")[1])
        self.assertIsNone(self.report()["background"])

    def test_with_tokens_the_accent_leads_and_the_rest_is_derived(self):
        report = self.report("--tokens", self.tokens())
        self.assertEqual(report["background"], "#ffffff")
        self.assertEqual(report["colours"][0], "#0f766e")
        self.assertEqual(len(set(report["colours"])), 3)
        for colour in report["colours"]:
            self.assertRegex(colour, r"^#[0-9a-f]{6}$")
        self.assertIn('stroke="#0f766e"', report["svg"])
        self.assertNotIn("var(", report["svg"])

    def test_derived_colours_can_be_seen_on_light_and_on_dark(self):
        contrast = load("forge-design", "contrast")
        for bg, accent in (("#ffffff", "#0f766e"), ("#0b1014", "#5ad1c0"), ("#fff", "#777"), ("#f6f7f9", "#e0b000")):
            colours = self.report("--tokens", self.tokens(bg=bg, accent=accent))["colours"]
            for colour in colours[1:]:  # the accent itself is the tokens' own pair to check
                self.assertGreaterEqual(contrast.ratio(colour, bg), 3.0, (colour, bg))

    def test_chart_roles_in_the_tokens_win(self):
        path = self.tokens(**{"chart-1": "#111111", "chart-2": "#222", "chart-3": "#333333"})
        self.assertEqual(self.report("--tokens", path)["colours"], ["#111111", "#222", "#333333"])

    def test_the_packs_own_token_file_works(self):
        self.assertEqual(self.report("--tokens", TOKENS)["colours"][0], "#3f4856")

    def test_bad_tokens_are_refused(self):
        for path in (self.tokens(accent=None), self.tokens(bg="white"), self.tokens(text="javascript:alert(1)"),
                     self.tokens(**{"chart-2": '"/><script>'}), self.write("[1, 2]", "list.json"),
                     self.write("{not json", "broken.json"), os.path.join(self.folder, "missing.json")):
            code, out, err = run(self.write(self.DATA), "--type", "line", "--tokens", path)
            self.assertEqual((code, out), (2, ""), path)
            self.assertIn("tokens file", err)


class Refusals(ChartCase):
    def test_no_points(self):
        for data in ({}, {"series": []}, {"series": "x"}, {"series": [{"name": "A", "points": []}]},
                     {"series": [{"name": "A"}]}, {"series": ["A"]}):
            self.assertRegex(self.refuse(data, "line"), "no data|no points")

    def test_values_that_are_not_numbers(self):
        for value in ("12", None, True, [1], {"a": 1}):
            with self.subTest(value=value):
                self.assertIn("not [label, number]", self.refuse({"series": [series("A", [1, value], ["a", "b"])]}, "bar"))
        for raw in ("NaN", "Infinity", "-Infinity", "1e999", "1" + "0" * 400):
            with self.subTest(raw=raw):
                text = '{"series": [{"name": "A", "points": [["a", 1], ["b", %s]]}]}' % raw
                self.assertIn("not [label, number]", self.refuse(text, "line"))
        self.assertIn("not [label, number]", self.refuse({"series": [{"points": [[1, 2, 3]]}]}, "line"))
        self.assertIn("not [label, number]", self.refuse({"series": [{"points": [[["x"], 2]]}]}, "line"))

    def test_donut_with_negative_values_or_too_many_parts(self):
        negative = self.refuse({"series": [series("A", [5, -1], ["a", "b"])]}, "donut")
        self.assertIn("negative", negative)
        self.assertIn("use a bar chart", negative)
        many = self.refuse({"series": [series("A", [1] * 7, list("abcdefg"))]}, "donut")
        self.assertIn("7 parts", many)
        self.assertIn("use a bar chart", many)
        self.draw({"series": [series("A", [1] * 6, list("abcdef"))]}, "donut")  # six is still fine
        self.assertIn("total above zero", self.refuse({"series": [series("A", [0, 0], ["a", "b"])]}, "donut"))

    def test_stacked_series_of_different_lengths(self):
        data = {"series": [series("A", [1, 2, 3], ["a", "b", "c"]), series("B", [1, 2], ["a", "b"])]}
        self.assertIn("different lengths", self.refuse(data, "area"))
        self.assertIn("different lengths", self.refuse(data, "bar"))
        self.draw(data, "line")  # lines are not stacked
        negative = {"series": [series("A", [1, -2], ["a", "b"]), series("B", [1, 2], ["a", "b"])]}
        self.assertIn("negative", self.refuse(negative, "area"))

    def test_too_many_series_and_one_series_types(self):
        seven = {"series": [series("S%d" % index, [1, 2], ["a", "b"]) for index in range(7)]}
        self.assertIn("7 series", self.refuse(seven, "line"))
        two = {"series": seven["series"][:2]}
        self.assertIn("one series", self.refuse(two, "donut"))
        self.assertIn("one series", self.refuse(two, "spark"))

    def test_unreadable_input(self):
        self.assertIn("not valid JSON", self.refuse("{oops", "line"))
        self.assertIn("JSON object", self.refuse("[1, 2]", "line"))
        self.assertIn("not valid JSON", self.refuse("[" * 100000, "line"))
        code, out, err = run(os.path.join(self.folder, "missing.json"), "--type", "line")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read", err)
        self.assertEqual(run(self.folder, "--type", "line")[0], 2)  # a folder
        big = self.write(" " * (chart.MAX_BYTES + 1) + "{}", "big.json")
        self.assertEqual(run(big, "--type", "line")[0], 2)

    def test_sizes_out_of_range(self):
        data = {"series": [series("A", [1, 2], ["a", "b"])]}
        for size in (("--width", "5"), ("--width", "99999"), ("--height", "-5"), ("--height", "50")):
            self.assertIn("--width and --height", self.refuse(data, "line", *size))
        self.draw(data, "spark", "--width", "60", "--height", "16")

    def test_usage_errors_exit_2(self):
        for args in ([], ["x.json"], ["x.json", "--type", "pie"], ["x.json", "--type", "heat"]):
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
                chart.main(args)
            self.assertEqual(caught.exception.code, 2)


class Output(ChartCase):
    DATA = {"title": "Café", "series": [series("A", [1, 2], ["a", "b"])]}

    def test_out_writes_the_file_and_says_so(self):
        target = os.path.join(self.folder, "chart.svg")
        code, out, err = run(self.write(self.DATA), "--type", "bar", "--out", target)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("wrote", out)
        with open(target, "rb") as handle:
            data = handle.read()
        self.assertTrue(data.startswith(b"<svg ") and data.endswith(b"</svg>\n"))
        self.assertNotIn(b"\r", data)
        ET.fromstring(data.decode("ascii"))

    def test_bad_input_writes_nothing(self):
        target = os.path.join(self.folder, "chart.svg")
        code, _, _ = run(self.write({"series": []}), "--type", "bar", "--out", target)
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(target))
        code, _, err = run(self.write(self.DATA), "--type", "bar", "--out", os.path.join(self.folder, "no", "x.svg"))
        self.assertEqual(code, 2)
        self.assertIn("cannot write", err)

    def test_out_never_goes_through_a_symlink(self):
        victim, link = os.path.join(self.folder, "victim.txt"), os.path.join(self.folder, "chart.svg")
        with open(victim, "w") as handle:
            handle.write("keep me")
        symlink(self, victim, link)
        code, out, err = run(self.write(self.DATA), "--type", "bar", "--out", link)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("symlink", err)
        with open(victim) as handle:
            self.assertEqual(handle.read(), "keep me")
        dangling = os.path.join(self.folder, "dangling.svg")
        os.symlink(os.path.join(self.folder, "nowhere.txt"), dangling)
        self.assertEqual(run(self.write(self.DATA), "--type", "bar", "--out", dangling)[0], 2)
        self.assertFalse(os.path.exists(os.path.join(self.folder, "nowhere.txt")))

    def test_json_shape(self):
        code, out, _ = run(self.write(self.DATA), "--type", "line", "--json")
        report = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(report), ["background", "colours", "height", "out", "series", "summary", "svg",
                                          "title", "type", "width"])
        self.assertEqual(report["series"], [{"name": "A", "points": 2, "first": 1, "last": 2, "min": 1, "max": 2}])
        self.assertEqual((report["type"], report["width"], report["height"], report["out"]), ("line", 640, 280, None))
        self.assertTrue(report["svg"].startswith("<svg "))
        self.assertTrue(out.isascii())
        target = os.path.join(self.folder, "chart.svg")
        code, out, _ = run(self.write(self.DATA), "--type", "line", "--json", "--out", target)
        self.assertEqual((json.loads(out)["svg"], json.loads(out)["out"]), (None, target))

    def test_command_line(self):
        done = subprocess.run([sys.executable, SCRIPT, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=60)
        self.assertEqual(done.returncode, 0)
        for word in ("Usage:", "Exit codes:", "--tokens", "donut"):
            self.assertIn(word, done.stdout)
        env = dict(os.environ, PYTHONIOENCODING="cp1252")  # a Windows pipe
        done = subprocess.run([sys.executable, SCRIPT, self.write(self.DATA), "--type", "line"], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(b"Caf&#233;", done.stdout)
        bad = self.write({"series": [series("A", [1, "€"], ["a", "b"])]}, "bad.json")
        done = subprocess.run([sys.executable, SCRIPT, bad, "--type", "line"], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual((done.returncode, done.stdout), (2, b""))


if __name__ == "__main__":
    unittest.main()
