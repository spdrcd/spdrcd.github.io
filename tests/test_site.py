"""
Integrity tests for the static site.

Guardrails against the ways a hand-edited static site silently rots: dead asset
paths, nav links pointing at renamed sections, images that lost their alt text,
photos committed straight off the camera.

Standard library only. No pip install, no node_modules. Run from the repo root:

    python3 -m unittest discover -s tests -v
"""

import os
import pathlib
import unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(
    os.environ.get("SITE_ROOT", pathlib.Path(__file__).resolve().parents[1])
)
INDEX = ROOT / "index.html"

PHOTO_BUDGET_BYTES = 400 * 1024
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "data:", "//")


class Page(HTMLParser):
    """Collects just enough of the document to assert against."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.ids = set()
        self.open_stack = []
        self.text_runs = []

    def _record(self, tag, attrs):
        d = {k: (v or "") for k, v in attrs}
        self.tags.append((tag, d))
        if d.get("id"):
            self.ids.add(d["id"])
        return d

    def handle_starttag(self, tag, attrs):
        self._record(tag, attrs)
        self.open_stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self._record(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self.open_stack:
            while self.open_stack and self.open_stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self.open_stack and data.strip():
            self.text_runs.append((self.open_stack[-1], data.strip()))

    def of(self, tag):
        return [attrs for t, attrs in self.tags if t == tag]

    def local_refs(self):
        """Every same-origin file path the document points at."""
        refs = set()
        for _tag, attrs in self.tags:
            for key in ("src", "href"):
                val = attrs.get(key, "").strip()
                if not val or val.startswith("#") or val.startswith(EXTERNAL):
                    continue
                refs.add(val.split("?")[0].split("#")[0])
        return refs


class SiteTestCase(unittest.TestCase):
    page: Page

    @classmethod
    def setUpClass(cls):
        if not INDEX.is_file():
            raise unittest.SkipTest(f"index.html not found at {INDEX}")
        cls.page = Page()
        cls.page.feed(INDEX.read_text(encoding="utf-8"))


class TestStructure(SiteTestCase):
    def test_parses_as_html(self):
        self.assertTrue(self.page.of("html"), "no <html> element parsed")
        self.assertTrue(self.page.of("body"), "no <body> element parsed")

    def test_exactly_one_h1(self):
        self.assertEqual(len(self.page.of("h1")), 1, "a page should have exactly one <h1>")

    def test_has_title(self):
        titles = [t for tag, t in self.page.text_runs if tag == "title"]
        self.assertTrue(titles and titles[0].strip(), "<title> is missing or empty")

    def test_meta_description_is_useful(self):
        descs = [
            m.get("content", "").strip()
            for m in self.page.of("meta")
            if m.get("name", "").lower() == "description"
        ]
        self.assertTrue(descs, "no meta description")
        self.assertGreater(
            len(descs[0]), 50, "meta description too short to be useful in search results"
        )

    def test_html_declares_a_language(self):
        self.assertTrue(self.page.of("html")[0].get("lang"), "<html> needs a lang attribute")

    def test_non_english_blocks_declare_their_language(self):
        """CJK blocks need lang= so browsers pick the right font and screen readers switch voice."""
        langs = {a.get("lang") for _t, a in self.page.tags if a.get("lang")}
        self.assertIn("ja", langs, 'the Japanese profile block is missing lang="ja"')
        self.assertTrue(
            any(l.startswith("zh") for l in langs),
            "the Chinese profile block is missing a zh lang attribute",
        )


class TestLinksAndAssets(SiteTestCase):
    def test_every_local_asset_exists(self):
        missing = sorted(r for r in self.page.local_refs() if not (ROOT / r).exists())
        self.assertFalse(missing, f"index.html points at files not in the repo: {missing}")

    def test_every_in_page_anchor_has_a_target(self):
        hrefs = {
            a["href"]
            for a in self.page.of("a")
            if a.get("href", "").startswith("#") and a["href"] != "#"
        }
        dangling = sorted(h for h in hrefs if h[1:] not in self.page.ids)
        self.assertFalse(dangling, f"anchor links with no matching id: {dangling}")

    def test_nav_targets_are_real_sections(self):
        nav_targets = {
            a["href"][1:]
            for a in self.page.of("a")
            if a.get("href", "").startswith("#") and a["href"] != "#"
        }
        self.assertTrue(nav_targets, "expected in-page nav links")
        self.assertLessEqual(nav_targets, self.page.ids)

    def test_no_insecure_http_links(self):
        bad = sorted(
            attrs[key]
            for _t, attrs in self.page.tags
            for key in ("src", "href")
            if attrs.get(key, "").startswith("http://")
        )
        self.assertFalse(bad, f"insecure http:// refs cause mixed-content warnings: {bad}")


class TestAccessibility(SiteTestCase):
    def test_every_image_has_alt_text(self):
        missing = [i.get("src", "?") for i in self.page.of("img") if not i.get("alt", "").strip()]
        self.assertFalse(missing, f"images without alt text: {missing}")

    def test_iframes_are_titled_and_lazy(self):
        for f in self.page.of("iframe"):
            src = f.get("src", "?")
            with self.subTest(iframe=src):
                self.assertTrue(f.get("title", "").strip(), "iframe needs a title for screen readers")
                self.assertEqual(f.get("loading"), "lazy", "iframe should not block first paint")

    def test_icon_links_have_accessible_names(self):
        labelled = [a for a in self.page.of("a") if a.get("aria-label", "").strip()]
        self.assertTrue(labelled, "icon-only social links need aria-label")


class TestPerformanceBudgets(SiteTestCase):
    photo_dir = ROOT / "assets" / "photos"

    def test_gallery_markup_matches_photos_on_disk(self):
        if not self.photo_dir.is_dir():
            self.skipTest("no assets/photos directory")
        on_disk = {p.name for p in self.photo_dir.glob("*.jpg")}
        referenced = {
            pathlib.PurePosixPath(i["src"]).name
            for i in self.page.of("img")
            if i.get("src", "").startswith("assets/photos/")
        }
        self.assertEqual(
            referenced,
            on_disk,
            f"only in markup: {sorted(referenced - on_disk)}; only on disk: {sorted(on_disk - referenced)}",
        )

    def test_photos_are_web_sized(self):
        if not self.photo_dir.is_dir():
            self.skipTest("no assets/photos directory")
        heavy = {
            p.name: p.stat().st_size
            for p in self.photo_dir.glob("*.jpg")
            if p.stat().st_size > PHOTO_BUDGET_BYTES
        }
        self.assertFalse(
            heavy, f"over the {PHOTO_BUDGET_BYTES // 1024}KB budget, resize before committing: {heavy}"
        )

    def test_gallery_images_are_lazy_with_dimensions(self):
        gallery = [i for i in self.page.of("img") if i.get("src", "").startswith("assets/photos/")]
        if not gallery:
            self.skipTest("no gallery images")
        for i in gallery:
            with self.subTest(img=i["src"]):
                self.assertEqual(i.get("loading"), "lazy", "gallery image not lazy-loaded")
                self.assertTrue(
                    i.get("width") and i.get("height"),
                    "needs width/height to reserve space and avoid layout shift",
                )


class TestLightbox(SiteTestCase):
    def test_script_is_wired_up(self):
        srcs = [s.get("src", "") for s in self.page.of("script")]
        self.assertIn("js/site.js", srcs, "the gallery lightbox script is not included")

    def test_script_is_defensive_and_keyboard_accessible(self):
        site_js = ROOT / "js" / "site.js"
        if not site_js.is_file():
            self.skipTest("js/site.js not present")
        src = site_js.read_text(encoding="utf-8")
        self.assertRegex(
            src,
            r"if\s*\(\s*!\s*grid\s*\)\s*return",
            "site.js should bail out when the gallery is absent instead of throwing",
        )
        for key in ("Escape", "ArrowLeft", "ArrowRight"):
            with self.subTest(key=key):
                self.assertIn(key, src, "lightbox should support keyboard navigation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
