"""Tests for forge-dashboard/dashboard.example.html: the example page is self-contained (no external
request of any kind), every chart in it has a title, and its example numbers add up."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `-m unittest tests.x` works too
from _load import ROOT  # noqa: E402

PAGE = os.path.join(ROOT, "forge-dashboard", "dashboard.example.html")
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
        for part in ('class="strip"', 'class="link"', 'class="matrix', 'class="dots"', 'class="sparks', 'class="log'):
            self.assertIn(part, self.html)
        self.assertEqual(len(re.findall(r'<section class="panel"', self.html)), 6)
        self.assertEqual(len(re.findall(r"<td class=\"t[1-5]\">", self.html)), 9, "a 3 by 3 matrix")
        self.assertLessEqual(len(self.html.splitlines()), 320)

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


if __name__ == "__main__":
    unittest.main()
