"""
Integrity tests for the static site.

Guardrails against the ways a hand-edited static site silently rots: dead asset
paths, nav links pointing at renamed sections, images that lost their alt text,
photos committed straight off the camera.

Standard library only. No pip install, no node_modules. Run from the repo root:

    python3 -m unittest discover -s tests -v

Design note - what fails vs. what warns
---------------------------------------
Tests are split by consequence, not by category:

  * A photo referenced in the markup but missing from disk is a broken image on
    the live site. That fails.
  * A photo sitting in assets/photos that nothing references is untidy, not
    broken. That prints a notice and passes, so an unused file can never block
    a deploy on its own.

Set STRICT_ASSETS=1 to promote the notices to failures (useful before a
release, or in a nightly job).

Environment overrides
---------------------
  SITE_ROOT        repo root (default: parent of this file)
  PHOTO_BUDGET_KB  per-photo size budget in KB (default: 500)
  STRICT_ASSETS    "1" to turn advisory checks into failures
"""

import os
import pathlib
import sys
import unittest
from html.parser import HTMLParser
from urllib.parse import unquote

ROOT = pathlib.Path(
    os.environ.get("SITE_ROOT", pathlib.Path(__file__).resolve().parents[1])
)
INDEX = ROOT / "index.html"

PHOTO_BUDGET_BYTES = int(os.environ.get("PHOTO_BUDGET_KB", "500")) * 1024
STRICT = os.environ.get("STRICT_ASSETS", "").strip() in {"1", "true", "yes"}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:", "//", "#")


def notice(message):
    """Advisory output. Fails only when STRICT_ASSETS is set."""
    print(f"\n  NOTICE: {message}", file=sys.stderr)


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
        """Same-origin file paths the document points at, normalised."""
        refs = set()
        for _tag, attrs in self.tags:
            for key in ("src", "href"):
                val = attrs.get(key, "").strip()
                if not val or val.startswith(EXTERNAL_PREFIXES):
                    continue
                path = unquote(val.split("?")[0].split("#")[0]).lstrip("/")
                if path:
                    refs.add(path)
        return refs

    def gallery_images(self):
        return [
            i for i in self.of("img")
            if i.get("src", "").startswith("assets/photos/")
        ]


def photo_files(directory):
    """Every image in a directory, whatever the extension or case."""
    if not directory.is_dir():
        return set()
    return {
        p.name for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    }


class SiteTestCase(unittest.TestCase):
    page: Page
    photo_dir = ROOT / "assets" / "photos"

    @classmethod
    def setUpClass(cls):
        if not INDEX.is_file():
            raise unittest.SkipTest(f"index.html not found at {INDEX}")
        cls.page = Page()
        cls.page.feed(INDEX.read_text(encoding="utf-8"))

    def advisory(self, problem):
        """Fail under STRICT_ASSETS, otherwise report and continue."""
        if STRICT:
            self.fail(problem + "  (STRICT_ASSETS is set)")
        notice(problem + "  -- advisory, not failing. Set STRICT_ASSETS=1 to enforce.")


class TestStructure(SiteTestCase):
    def test_parses_as_html(self):
        self.assertTrue(self.page.of("html"), "no <html> element parsed")
        self.assertTrue(self.page.of("body"), "no <body> element parsed")

    def test_exactly_one_h1(self):
        count = len(self.page.of("h1"))
        self.assertEqual(count, 1, f"expected exactly one <h1>, found {count}")

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
        """Hard fail: a missing asset is a broken page."""
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


class TestGallery(SiteTestCase):
    def test_every_referenced_photo_exists(self):
        """Hard fail: the markup promises an image the repo does not have."""
        if not self.photo_dir.is_dir():
            self.skipTest("no assets/photos directory")
        on_disk = photo_files(self.photo_dir)
        referenced = {
            pathlib.PurePosixPath(i["src"]).name for i in self.page.gallery_images()
        }
        missing = sorted(referenced - on_disk)
        self.assertFalse(
            missing,
            f"gallery references photos that are not committed (broken images): {missing}",
        )

    def test_no_orphaned_photos(self):
        """Advisory: committed but unused. Untidy, not broken."""
        if not self.photo_dir.is_dir():
            self.skipTest("no assets/photos directory")
        on_disk = photo_files(self.photo_dir)
        referenced = {
            pathlib.PurePosixPath(i["src"]).name for i in self.page.gallery_images()
        }
        orphans = sorted(on_disk - referenced)
        if orphans:
            self.advisory(
                f"{len(orphans)} photo(s) in assets/photos are not referenced by index.html: {orphans}"
            )

    def test_gallery_images_are_lazy_with_dimensions(self):
        gallery = self.page.gallery_images()
        if not gallery:
            self.skipTest("no gallery images")
        for i in gallery:
            with self.subTest(img=i["src"]):
                self.assertEqual(i.get("loading"), "lazy", "gallery image not lazy-loaded")
                self.assertTrue(
                    i.get("width") and i.get("height"),
                    "needs width/height to reserve space and avoid layout shift",
                )

    def test_photos_are_web_sized(self):
        """Advisory: a heavy photo slows the page, it does not break it."""
        if not self.photo_dir.is_dir():
            self.skipTest("no assets/photos directory")
        heavy = {
            name: (self.photo_dir / name).stat().st_size
            for name in sorted(photo_files(self.photo_dir))
            if (self.photo_dir / name).stat().st_size > PHOTO_BUDGET_BYTES
        }
        if heavy:
            budget = PHOTO_BUDGET_BYTES // 1024
            detail = ", ".join(f"{n} ({s // 1024}KB)" for n, s in heavy.items())
            self.advisory(f"over the {budget}KB budget, consider resizing: {detail}")


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
