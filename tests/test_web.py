from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import web


SAMPLE_HTML = """
<html>
  <head><title>Apache Foo &mdash; the Foo software</title></head>
  <body>
    <header><h1>Apache Foo&trade;</h1></header>
    <p>Apache Foo software is a thing. <a href="https://www.apache.org/">Apache</a></p>
    <script>noisy()</script>
    <footer>
      <a href="https://www.apache.org/licenses/">License</a>
      <a href="https://www.apache.org/security/">Security</a>
      <img src="/img/logo.png" alt="Foo logo" />
    </footer>
  </body>
</html>
"""


class ParseHtmlTests(unittest.TestCase):
    def test_extracts_title(self) -> None:
        title, _h, _l, _i, _t = web.parse_html(SAMPLE_HTML)
        self.assertIn("Apache Foo", title)

    def test_extracts_heading(self) -> None:
        _t, headings, _l, _i, _t2 = web.parse_html(SAMPLE_HTML)
        self.assertTrue(any("Apache Foo" in h for h in headings))

    def test_strips_scripts_from_visible_text(self) -> None:
        _t, _h, _l, _i, text = web.parse_html(SAMPLE_HTML)
        self.assertNotIn("noisy()", text)
        self.assertIn("Apache Foo software", text)

    def test_collects_links_and_images(self) -> None:
        _t, _h, links, images, _t2 = web.parse_html(SAMPLE_HTML)
        hrefs = [link.href for link in links]
        self.assertIn("https://www.apache.org/licenses/", hrefs)
        self.assertIn("https://www.apache.org/security/", hrefs)
        self.assertEqual(images[0].src, "/img/logo.png")
        self.assertEqual(images[0].alt, "Foo logo")


class HostHelpersTests(unittest.TestCase):
    def test_is_apache_host(self) -> None:
        self.assertTrue(web.is_apache_host("kafka.apache.org"))
        self.assertTrue(web.is_apache_host("apache.org"))
        self.assertFalse(web.is_apache_host("example.com"))
        self.assertFalse(web.is_apache_host("apachefake.org"))

    def test_second_level_domain(self) -> None:
        self.assertEqual(web.second_level_domain("tomcat.com"), "tomcat")
        self.assertEqual(web.second_level_domain("foo.tomcat.com"), "tomcat")
        self.assertEqual(web.second_level_domain(""), "")


class FetchPageRejectsBadSchemesTests(unittest.TestCase):
    def test_non_http_url_returns_error(self) -> None:
        page = web.fetch_page("file:///etc/passwd")
        self.assertEqual(page.status, 0)
        self.assertIsNotNone(page.error)
        self.assertIn("http://", page.error or "")


if __name__ == "__main__":
    unittest.main()
