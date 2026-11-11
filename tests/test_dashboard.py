"""Tests for forge-design/dashboard.example.html: the example page is self-contained (no external
request of any kind), every chart in it has a title, and its example numbers add up. And for
forge-design/bars3d.css, the recipe for bars with depth that the example holds a copy of."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

PAGE = os.path.join(ROOT, "forge-design", "dashboard.example.html")
BARS = os.path.join(ROOT, "forge-design", "bars3d.css")
# Where a page can ask for something from outside: src, href and the like, url() and @import in CSS.
EXTERNAL = re.compile(r"""(?:\b(?:src|href|srcset|action|poster|data|xlink:href)\s*=\s*["']?\s*|url\(\s*["']?\s*|@import\s+["']?\s*)"""
                      r"""(?:https?:)?//""", re.IGNORECASE)
NAMESPACE = re.compile(r"""\bxmlns(?::\w+)?\s*=\s*["']https?://[^"']*["']""", re.IGNORECASE)


def external_requests(html):
    """Every place in HTML that would load something from another host. xmlns values are names, not requests."""
    return [match.group(0) for match in EXTERNAL.finditer(NAMESPACE.sub("", html))]


def numbers(cells):
    return [int(cell) for cell in re.findall(r"<td[^>]*>(\d+)</td>", cells)]


class ExamplePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as handle:
            cls.html = handle.read()

    def test_no_external_request(self):
        self.assertEqual(external_requests(self.html), [])
        self.assertEqual(re.findall(r"https?://", NAMESPACE.sub("", self.html)), [], "no URL at all outside xmlns")
        for banned in ("<script", "<link", "<iframe", "<img", "@import", "@font-face", "url("):
            self.assertNotIn(banned, self.html.lower())

    def test_the_check_itself_sees_external_requests(self):
        for bad in ('<script src="https://cdn.example/x.js"></script>', "<link href=http://fonts.example/a.css>",
                    "<style>@import 'https://x.example/a.css';</style>", "<style>a{background:url( 'https://x.example/a.png')}</style>",
                    '<img src="//cdn.example/a.png">', "<style>@import url(https://x.example/a.css);</style>"):
            self.assertTrue(external_requests(bad), bad)
        for fine in ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">',
                     '<a href="#numbers">', '<img src="chart.svg">', "<p>See https in the text</p>"):
            self.assertEqual(external_requests(fine), [], fine)

    def test_every_svg_has_a_title(self):
        charts = re.findall(r"<svg\b.*?</svg>", self.html, re.DOTALL)
        self.assertGreaterEqual(len(charts), 4, "the main chart, the small line chart, the connector, the sparklines")
        self.assertEqual(len(charts), len(re.findall(r"<svg\b", self.html)))
        for svg in charts:
            title = re.search(r"<title\b[^>]*>([^<]+)</title>", svg)
            self.assertTrue(title and title.group(1).strip(), svg[:120])
        described = [svg for svg in charts if "<desc" in svg]
        self.assertGreaterEqual(len(described), 2, "the two charts with axes also have a desc")
        for svg in described:
            ids = set(re.findall(r'\bid="([^"]+)"', svg))
            self.assertEqual(set(re.search(r'aria-labelledby="([^"]+)"', svg).group(1).split()), ids)

    def test_it_is_responsive_themed_and_built_from_custom_properties(self):
        self.assertIn('name="viewport"', self.html)
        self.assertIn("prefers-color-scheme: dark", self.html)
        self.assertRegex(self.html, r"@container \(max-width: \d+px\)")
        self.assertIn("minmax(150px, 1fr)", self.html)  # the strip wraps on its own down to 390px
        self.assertNotIn("style=", self.html, "no inline styles: a strict Content-Security-Policy would block them")
        css = self.html.split("<style>")[1].split("</style>")[0]
        root, rest = css.split("* { box-sizing", 1)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", rest), [], "colours only as custom properties")
        light, dark = root.split("@media (prefers-color-scheme: dark)")
        names = set(re.findall(r"(--color-[\w-]+):", light))
        self.assertGreaterEqual(len(names), 8)
        self.assertEqual(names, set(re.findall(r"(--color-[\w-]+):", dark)), "every colour has a dark value")
        self.assertEqual(set(re.findall(r"var\((--color-[\w-]+)", self.html)) - names, set())
        self.assertNotRegex(css, r"font(?:-size)?:[^;]*\b(?:[0-9]|10)px", "no text under 11px")

    def test_the_parts_of_the_hud_are_there(self):
        for part in ('class="strip"', 'class="link"', 'class="matrix', 'class="dots"', 'class="sparks', 'class="log',
                     'class="bars3d"', 'class="bars3d-value'):
            self.assertIn(part, self.html)
        self.assertEqual(len(re.findall(r'<section class="panel"', self.html)), 7)
        self.assertEqual(len(re.findall(r"<td class=\"t[1-5]\">", self.html)), 9, "a 3 by 3 matrix")
        self.assertLessEqual(len(self.html.splitlines()), 420)

    def test_the_strip_draws_its_lines_per_cell(self):
        """A gap over a border-coloured background paints a half-empty last row as one solid block."""
        strip = re.search(r"\.strip \{(.*?)\}", self.html, re.S).group(1)
        self.assertNotRegex(strip, r"(?<![\w-])gap\s*:")
        self.assertNotIn("background", strip)
        self.assertIn("border-top", strip)
        self.assertRegex(self.html, r"\.strip div \{[^}]*border-right[^}]*border-bottom")

    def test_it_holds_the_bars3d_recipe_as_it_is(self):
        with open(BARS, encoding="utf-8") as handle:
            rules = handle.read().split("*/\n", 1)[1].strip()
        copy = self.html.split("bars3d.css, copied as it is", 1)[1].split("*/\n", 1)[1].split("/* end of bars3d.css */")[0]
        self.assertEqual(copy.strip(), rules)

    def test_the_example_numbers_add_up(self):
        """Honest numbers start with the example: the strip, the chart's table and the matrix agree."""
        orders = int(re.search(r"<dt>Orders</dt><dd><span class=\"v\">(\d+)</span>", self.html).group(1))
        today = numbers(re.search(r"<th scope=\"row\">Today</th>(.*?)</tr>", self.html).group(1))
        yesterday = numbers(re.search(r"<th scope=\"row\">Yesterday</th>(.*?)</tr>", self.html).group(1))
        matrix = numbers(re.search(r"<table class=\"matrix.*?</table>", self.html, re.DOTALL).group(0))
        self.assertEqual((sum(today), sum(matrix), len(today), len(matrix)), (orders, orders, 12, 9))
        self.assertIn("vs %d" % sum(yesterday), self.html)
        self.assertIn("%+.1f%%" % ((orders / sum(yesterday) - 1) * 100), self.html)
        points = re.search(r'<polyline class="s1" points="([^"]+)"', self.html).group(1).split()
        self.assertEqual([100 - int(point.split(",")[1]) for point in points], today, "the line is the table")
        dots = re.search(r'<p class="dots".*?</p>', self.html, re.DOTALL).group(0)
        idle, failed = dots.count('class="idle"'), dots.count('class="fail"')
        self.assertEqual((dots.count("<i"), idle, failed), (32, 5, 1))
        self.assertIn("%d busy, %d idle, %d failed" % (32 - idle - failed, idle, failed), dots)

    def test_the_bars_with_depth_are_the_matrix_and_their_heights_their_values(self):
        rows = re.findall(r"<tr><th scope=\"row\">(\w+)</th>(.*?)</tr>", re.search(
            r"<table class=\"matrix.*?</table>", self.html, re.DOTALL).group(0))
        totals = {name.lower(): sum(numbers(cells)) for name, cells in rows}
        values = {name: int(value) for name, value in re.findall(
            r'class="bars3d-bar (\w+)">.*?class="bars3d-value">(\d+)<', self.html)}
        self.assertEqual(values, totals, "each bar is its region's row of the matrix")
        heights = dict(re.findall(r"\.([a-z-]+) \{ --h: ([.\d]+); \}", self.html))
        for name, value in values.items():
            self.assertAlmostEqual(float(heights[name]) * 300, value, delta=0.5, msg=name)
        label = re.search(r'class="bars3d" role="img" aria-label="([^"]+)"', self.html).group(1)
        before = re.search(r"Yesterday: North (\d+), Central (\d+), South (\d+) \((\d+)\)", self.html).groups()
        self.assertEqual((sum(map(int, before[:3])), int(before[3])), (559, 559), "yesterday, printed, as in the strip")
        for name, value, earlier in zip(("North", "Central", "South"), (values["north"], values["central"],
                                                                         values["south"]), before):
            self.assertIn("%s %d" % (name, value), label)
            self.assertIn("%s %s" % (name, earlier), label)


class BarsRecipe(unittest.TestCase):
    """forge-design/bars3d.css: bars that grow on the compositor, with faces that keep their shape."""

    @classmethod
    def setUpClass(cls):
        with open(BARS, encoding="utf-8") as handle:
            cls.css = handle.read()
        cls.rules = re.sub(r"/\*.*?\*/", "", cls.css, flags=re.S)

    def test_nothing_from_outside_and_colours_from_the_tokens(self):
        self.assertEqual(external_requests(self.css), [])
        for banned in ("@import", "url(", "http"):
            self.assertNotIn(banned, self.rules)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", self.rules), [])
        self.assertTrue(set(re.findall(r"var\((--color-[\w-]+)", self.rules)) <= {
            "--color-chart-1", "--color-text", "--color-text-muted", "--color-surface"})

    def test_a_bar_grows_by_translate_never_by_scale_or_height(self):
        self.assertIn("transform: translateY(calc((1 - var(--h, 0)) * 100%));", self.rules)
        self.assertIn("@keyframes bars3d-rise { from { transform: translateY(100%); } }", self.rules)
        self.assertNotRegex(self.rules, r"scaleY|scale\(")
        self.assertNotRegex(self.rules, r"transition:[^;]*\bheight\b|@keyframes[^}]*\bheight\b")
        self.assertIn("clip-path: inset(-100vh -100vw 0 -100vw)", self.rules, "only below the baseline is cut")

    def test_the_faces_follow_one_depth_vector(self):
        self.assertIn("skewX(calc(atan2(var(--bars3d-dx), var(--bars3d-dy)) * -1))", self.rules)
        self.assertIn("skewY(calc(atan2(var(--bars3d-dy), var(--bars3d-dx)) * -1))", self.rules)
        self.assertNotIn("perspective", self.rules, "no strong perspective: a near bar is never bigger")

    def test_motion_only_without_reduced_motion(self):
        outside = self.rules.split("@media (prefers-reduced-motion: no-preference)")[0]
        self.assertNotRegex(outside, r"\b(?:transition|animation)\s*:")
        self.assertIn("@media (prefers-reduced-motion: no-preference)", self.rules)

    def test_the_comment_shows_the_markup_and_the_lean(self):
        for part in ('data-depth="tilt"', 'data-depth-layer="1"', "--h", "--n", "--i", "role=\"img\"", "table",
                     "scaleY", "setProperty"):
            self.assertIn(part, self.css.split("*/", 1)[0])


if __name__ == "__main__":
    unittest.main()
