"""Static verification of the generated board and architecture document.

These run in the normal suite (stdlib only). They pin the properties that
silently rot: the page claiming counts the registry does not support, a script
addressing an element that no longer exists, an unbalanced tag, or a market
value creeping into a page whose whole premise is that it has none.
"""

import re
import unittest
from html.parser import HTMLParser

from macro import board
from macro.board import MODULES, Status, counts, render, render_markdown

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class Balance(HTMLParser):
    """Tag-balance checker. Reports the first structural error it meets."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"</{tag}> at {self.getpos()} closes nothing")
            return
        top, pos = self.stack.pop()
        if top != tag:
            self.errors.append(
                f"</{tag}> at {self.getpos()} does not match <{top}> opened at {pos}"
            )


class TestRegistry(unittest.TestCase):
    def test_names_unique(self):
        names = [m.name for m in MODULES]
        self.assertEqual(len(names), len(set(names)))

    def test_every_module_declares_a_feed(self):
        for m in MODULES:
            self.assertTrue(m.feed.strip(), m.name)

    def test_built_modules_name_an_implementation(self):
        for m in MODULES:
            if m.status is Status.BUILT:
                self.assertTrue(m.module.startswith("macro/"), m.name)

    def test_spec_modules_name_no_implementation(self):
        for m in MODULES:
            if m.status is Status.SPEC:
                self.assertEqual(m.module, "", f"{m.name} is SPEC but names {m.module}")

    def test_claimed_implementations_exist_on_disk(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(board.__file__)))
        for m in MODULES:
            if not m.module:
                continue
            for path in m.module.split(" · "):
                p = path.strip()
                if not p.startswith("macro/"):
                    p = "macro/" + p
                full = os.path.join(root, p)
                self.assertTrue(
                    os.path.exists(full) or os.path.exists(full.rstrip("/")),
                    f"{m.name} claims {p}, which does not exist",
                )

    def test_counts_sum_to_total(self):
        c = counts()
        self.assertEqual(
            c["BUILT"] + c["PARTIAL"] + c["SPEC"], c["TOTAL"]
        )
        self.assertEqual(c["TOTAL"], len(MODULES))


class TestHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = render()

    def test_is_a_complete_document(self):
        self.assertTrue(self.doc.startswith("<!doctype html>"))
        for needle in ('<html lang="en">', "<head>", "</head>", "<body>",
                       "</body>", "</html>", "<title>Cold Start Terminal</title>",
                       '<meta charset="utf-8">', 'name="viewport"'):
            self.assertIn(needle, self.doc, needle)

    def test_tags_balance(self):
        b = Balance()
        b.feed(self.doc)
        self.assertEqual(b.errors, [], "; ".join(b.errors[:3]))
        self.assertEqual([t for t, _ in b.stack], [], "unclosed tags remain")

    def test_every_scripted_id_exists_in_the_markup(self):
        ids = set(re.findall(r'q\("([A-Za-z0-9_-]+)"\)', board.JS))
        ids |= set(re.findall(r'getElementById\("([A-Za-z0-9_-]+)"\)', board.JS))
        # DOM writes now route through the null-safe helpers; scan those too
        ids |= set(re.findall(r'set(?:Text|HTML)\("([A-Za-z0-9_-]+)"', board.JS))
        self.assertGreater(len(ids), 5)
        for i in sorted(ids):
            self.assertIn(f'id="{i}"', self.doc, f'script addresses #{i}, which is not in the page')

    def test_registry_is_embedded_and_complete(self):
        payload = re.search(r"window\.__BOARD__=(\{.*?\});", self.doc, re.S)
        self.assertIsNotNone(payload)
        import json
        data = json.loads(payload.group(1).replace("<\\/", "</"))
        self.assertEqual(len(data["modules"]), len(MODULES))
        self.assertEqual(len(data["chain"]), 10)
        self.assertEqual({m["status"] for m in data["modules"]},
                         {"BUILT", "PARTIAL", "SPEC"})

    def test_footer_counts_match_the_registry(self):
        c = counts()
        self.assertIn(f"Total modules {c['TOTAL']}", self.doc)
        self.assertIn(f"{c['BUILT']} built", self.doc)
        self.assertIn(f"{c['PARTIAL']} partial", self.doc)
        self.assertIn(f"{c['SPEC']} specified", self.doc)

    def test_no_market_values_anywhere(self):
        """The page's premise is that it holds none. Enforce it."""
        body = re.sub(r"<style>.*?</style>", "", self.doc, flags=re.S)
        body = re.sub(r"<script>.*?</script>", "", body, flags=re.S)
        # Any bare 2-4 digit number with decimals would be a price or a yield.
        hits = re.findall(r"\b\d{2,5}\.\d+\b", body)
        self.assertEqual(hits, [], f"market-like literals present: {hits[:5]}")
        for banned in ("$", "bps ", "% y/y", "bn USD"):
            self.assertNotIn(banned, body, banned)

    def test_every_value_slot_is_marked_unfed(self):
        self.assertGreaterEqual(self.doc.count("UNFED"), 10)
        self.assertIn("UNDETERMINED", self.doc)
        flat = " ".join(self.doc.split())
        self.assertIn("no primary source is connected", flat)

    def test_no_stray_non_ascii_glyphs(self):
        # deliberate typography: section sign, middot, dashes, true minus,
        # multiplication sign, arrow, comparison operators, delta
        allowed = set("§·–—−×→≥≤Δ")
        stray = {ch for ch in self.doc if ord(ch) > 127} - allowed
        self.assertEqual(stray, set(),
                         f"unexpected glyphs: {[(c, hex(ord(c))) for c in stray]}")

    def test_fonts_have_a_real_fallback_stack(self):
        for family in ("--mono:", "--sans:", "--disp:"):
            line = re.search(re.escape(family) + r"([^;]+);", board.CSS).group(1)
            self.assertGreaterEqual(len(line.split(",")), 3, family)

    def test_body_paints_its_own_background(self):
        self.assertRegex(board.CSS, r"body\{[^}]*background:var\(--ink\)")

    def test_reduced_motion_is_honoured(self):
        self.assertIn("prefers-reduced-motion:reduce", board.CSS)
        self.assertIn("prefers-reduced-motion: reduce", board.JS)

    def test_grid_rows_are_full(self):
        spans = [int(x) for x in re.findall(r'class="p c(\d+)"', self.doc)]
        self.assertTrue(spans)
        rows, row = [], 0
        for s in spans:
            if row + s > 12:
                rows.append(row)
                row = s
            else:
                row += s
        rows.append(row)
        self.assertTrue(all(r == 12 for r in rows), f"row sums: {rows}")

    def test_wide_content_scrolls_in_its_own_container(self):
        self.assertIn(".flowwrap{overflow-x:auto", board.CSS)
        self.assertIn(".scroll{overflow:auto", board.CSS)

    def test_noscript_fallback_present(self):
        self.assertIn("<noscript>", self.doc)

    def test_dom_writes_are_null_safe(self):
        """A missing node must warn, not throw: an unguarded write to a missing
        element aborts the whole IIFE and blanks every panel after it."""
        self.assertNotRegex(
            board.JS, r'q\("[A-Za-z0-9_-]+"\)\.(textContent|innerHTML)\s*=',
            "direct write to a possibly-missing node; use setText/setHTML")
        self.assertIn("function setText(", board.JS)
        self.assertIn("function setHTML(", board.JS)

    def test_payload_cannot_break_out_of_the_script_tag(self):
        payload = re.search(r"window\.__BOARD__=(\{.*?\});", self.doc, re.S).group(1)
        self.assertNotIn("</", payload)


class TestMarkdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = render_markdown()

    def test_one_table_row_per_module(self):
        rows = [l for l in self.md.splitlines()
                if l.startswith("| ") and "**" in l]
        self.assertEqual(len(rows), len(MODULES))

    def test_headline_counts_match_the_registry(self):
        c = counts()
        self.assertIn(
            f"**{c['TOTAL']} modules: {c['BUILT']} built, {c['PARTIAL']} partial, "
            f"{c['SPEC']} specified.**", self.md)

    def test_states_zero_feeds_connected(self):
        self.assertIn("Zero feeds are connected", self.md)
        self.assertEqual(self.md.count("| not connected |"), len(board.FEEDS))

    def test_names_the_highest_value_gap(self):
        self.assertIn("Market reaction analyzer", self.md)
        self.assertIn("§34", self.md)

    def test_no_market_values(self):
        body = re.sub(r"```.*?```", "", self.md, flags=re.S)
        self.assertEqual(re.findall(r"\b\d{2,5}\.\d+\b", body), [])


class TestGeneratedFilesAreCurrent(unittest.TestCase):
    """The committed artefacts must equal what the generator produces now."""

    def _check(self, path, expected):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(board.__file__)))
        full = os.path.join(root, path)
        if not os.path.exists(full):
            self.skipTest(f"{path} not generated yet")
        with open(full, encoding="utf-8") as fh:
            self.assertEqual(
                fh.read(), expected,
                f"{path} is stale - regenerate with `python -m macro board`")

    def test_html_is_current(self):
        self._check("board/cold-start-terminal.html", render())

    def test_markdown_is_current(self):
        self._check("docs/intelligence-terminal.md", render_markdown())


if __name__ == "__main__":
    unittest.main()
