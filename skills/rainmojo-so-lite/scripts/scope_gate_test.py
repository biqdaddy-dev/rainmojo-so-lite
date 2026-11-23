"""No levels or counts for a site that is blocked or has too little content (LITE-015).

    python -I skills/rainmojo-so-lite/scripts/scope_gate_test.py

Port of rainmojo-so RSO-036 (tests/test_scope_gate.py). In the so-audit-lite eval the only
runs below 100 graded the 13-word "Coming soon" case with check counts for content,
citability and E-E-A-T. scope_gate.py makes the call deterministic and build_summary.py
drops every count and level once the gate says the site cannot be graded. These tests serve
local sites over http.server (blocked, one thin page, a normal five-page site, an empty
client-rendered app shell, a site with no sitemap), pin the 50-word boundary in English and
Thai, check the Thai estimate used when pythainlp is absent, and check the card backstop.
"""

import functools
import json
import math
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import build_summary  # noqa: E402
import scope_gate  # noqa: E402
import text_words  # noqa: E402
from present import lint, validate  # noqa: E402
from text_words import count_words, thai_available  # noqa: E402

NAV = "<header><nav><a href='/'>Home</a> <a href='/about/'>About us and our story</a></nav></header>"
FOOT = "<footer><p>Copyright 2026 Example Company Limited, 1 Example Road, Bangkok 10120</p></footer>"
NOINDEX = '<meta name="robots" content="noindex, nofollow">'

# Thai: "our coffee shop opens every day" (5 words) and "house" (1 word), no spaces.
TH_SENTENCE = "\u0e23\u0e49\u0e32\u0e19\u0e01\u0e32\u0e41\u0e1f\u0e02\u0e2d\u0e07\u0e40\u0e23\u0e32\u0e40\u0e1b\u0e34\u0e14\u0e17\u0e38\u0e01\u0e27\u0e31\u0e19"
TH_WORD = "\u0e1a\u0e49\u0e32\u0e19"


def page(main, head=""):
    return ("<!doctype html><html><head><meta charset='utf-8'>%s<title>t</title></head><body>%s"
            "<main>%s</main>%s</body></html>" % (head, NAV, main, FOOT))


def words(n, tag="w"):
    return " ".join("%s%d" % (tag, i) for i in range(n))


def write_site(root, files):
    for rel, text in files.items():
        path = Path(root, *[p for p in rel.strip("/").split("/") if p])
        if rel.endswith("/"):
            path = path / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Served:
    """A local folder served on 127.0.0.1 for the length of a test class."""

    def __init__(self, files):
        self.tmp = tempfile.TemporaryDirectory()
        write_site(self.tmp.name, files)
        handler = functools.partial(_QuietHandler, directory=self.tmp.name)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.url = "http://127.0.0.1:%d/" % self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()


BLOCKED = {
    "/robots.txt": "User-agent: *\nDisallow: /\n",
    "/sitemap.xml": "<urlset><url><loc>https://greenleaf.test/</loc></url><url><loc>https://greenleaf.test/teas/</loc></url></urlset>",
    "/": page("<h1>Tea</h1><p>%s</p>" % words(120, "a"), NOINDEX),
    "/teas/": page("<h1>Teas</h1><p>%s</p>" % words(120, "b"), NOINDEX),
}
THIN = {
    "/": page("<h1>Coming soon</h1><p>Nimman Yoga Studio opens in December 2026. Follow us for updates on the opening day.</p>"),
}
NORMAL = {
    "/robots.txt": "User-agent: *\nDisallow: /cart/\n\nSitemap: https://roastery.test/sitemap.xml\n",
    "/sitemap.xml": "<urlset>%s</urlset>" % "".join(
        "<url><loc>https://roastery.test/%s</loc></url>" % p for p in ("", "shop/", "about/", "blog/brew/", "contact/")),
    "/": page("<h1>Roastery</h1><p>%s</p>" % words(60, "home")),
    "/shop/": page("<h1>Shop</h1><p>%s</p>" % words(50, "shop")),
    "/about/": page("<h1>About</h1><p>%s</p>" % words(40, "about")),
    "/blog/brew/": page("<h1>Brew</h1><p>%s</p><p>%s</p>" % (words(80, "brew"), words(80, "brew"))),
    "/contact/": page("<h1>Contact</h1><p>Call us on 02 000 0000.</p>"),
}
SPA = {
    "/sitemap.xml": "<urlset><url><loc>https://ledgerly.test/</loc></url><url><loc>https://ledgerly.test/pricing/</loc></url></urlset>",
    "/": "<!doctype html><html><body><div id='root'></div><noscript>Enable JavaScript.</noscript>"
         "<script src='/static/js/main.js'></script></body></html>",
    "/pricing/": "<!doctype html><html><body><div id='root'></div><script src='/static/js/main.js'></script></body></html>",
}
NO_SITEMAP = {
    "/": page("<h1>Bike tours</h1><p>%s</p><a href='/tours/'>Tours</a> <a href='/faq/#q1'>FAQ</a> "
              "<a href='mailto:hi@bike.test'>Mail</a> <a href='tel:+6620000000'>Call</a> "
              "<a href='/brochure.pdf'>Brochure</a> <a href='https://other.test/'>Partner</a>" % words(10, "home")),
    "/tours/": page("<h1>Tours</h1><p>%s</p>" % words(20, "tour")),
    "/faq/": page("<h1>FAQ</h1><p>%s</p>" % words(20, "faq")),
}


class GateVerdictsOverHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sites = {name: Served(files) for name, files in (("blocked", BLOCKED), ("thin", THIN), ("normal", NORMAL), ("spa", SPA), ("nositemap", NO_SITEMAP))}

    @classmethod
    def tearDownClass(cls):
        for s in cls.sites.values():
            s.close()

    def test_blocked_site_is_not_scorable(self):
        r = scope_gate.run_gate(self.sites["blocked"].url)
        self.assertTrue(r["blocked_all"])
        self.assertFalse(r["scorable"])
        self.assertEqual((r["pages"], r["noindex_pages"]), (2, 2))
        self.assertEqual(r["main_text_words"], 2 + 240)  # the two H1 words plus both paragraphs
        self.assertTrue(any(x.startswith("blocked:") for x in r["reasons"]))
        self.assertTrue(any(x.startswith("noindex:") for x in r["reasons"]))

    def test_coming_soon_page_is_not_scorable(self):
        r = scope_gate.run_gate(self.sites["thin"].url)
        self.assertFalse(r["blocked_all"])
        self.assertEqual(r["pages"], 1)
        self.assertEqual(r["main_text_words"], 2 + 15)  # nav, header and footer text not counted
        self.assertFalse(r["scorable"])
        self.assertEqual(r["reasons"], ["too little content: 17 main-text words across 1 fetched page, under the 50-word threshold"])

    def test_closed_gate_still_hands_over_the_missing_facts(self):
        r = scope_gate.run_gate(self.sites["thin"].url)
        self.assertFalse(r["scorable"])
        f = r["facts"]
        self.assertEqual((f["robots_txt_status"], f["sitemap_status"], f["llms_txt_status"]), (404, 404, 404))
        self.assertEqual(f["missing"], ["robots.txt (HTTP 404)", "sitemap.xml (HTTP 404)", "llms.txt (HTTP 404)",
                                        "meta description on 1 of 1 page", "canonical on 1 of 1 page",
                                        "structured data (JSON-LD) on 1 of 1 page"])
        page0 = r["page_results"][0]
        self.assertEqual((page0["title"], page0["h1"], page0["json_ld_blocks"]), ("t", "Coming soon", 0))
        self.assertFalse(page0["meta_description"] or page0["canonical"])

    def test_facts_never_change_the_verdict(self):
        r = scope_gate.run_gate(self.sites["normal"].url)
        self.assertTrue(r["scorable"])
        self.assertIn("llms.txt (HTTP 404)", r["facts"]["missing"])
        self.assertEqual(r["facts"]["sitemap_status"], 200)

    def test_normal_site_is_scorable_and_repeats_count_once(self):
        r = scope_gate.run_gate(self.sites["normal"].url)
        self.assertTrue(r["scorable"], r["reasons"])
        self.assertEqual(r["pages"], 5)  # sitemap on the production host, re-based onto the mirror
        self.assertEqual(r["main_text_words"], 61 + 51 + 41 + 81 + 7)  # the repeated brew paragraph once
        self.assertEqual(r["reasons"], [])

    def test_client_rendered_shell_is_a_finding_not_thin_content(self):
        r = scope_gate.run_gate(self.sites["spa"].url)
        self.assertEqual((r["pages"], r["main_text_words"], r["client_rendered_pages"]), (2, 0, 2))
        self.assertTrue(all(p["client_rendered"] for p in r["page_results"]))
        self.assertTrue(r["scorable"], r["reasons"])

    def test_one_client_rendered_page(self):
        base = self.sites["spa"].url
        r = scope_gate.run_gate(base, pages=[base])
        self.assertEqual((r["pages"], r["client_rendered_pages"], r["scorable"]), (1, 1, True))

    def test_thin_page_without_an_app_shell_stays_thin(self):
        base = self.sites["thin"].url
        r = scope_gate.run_gate(base)
        self.assertEqual(r["client_rendered_pages"], 0)
        self.assertFalse(r["scorable"])

    def test_no_sitemap_reaches_pages_through_homepage_links(self):
        r = scope_gate.run_gate(self.sites["nositemap"].url)
        self.assertEqual(r["discovery"], "homepage_links")
        base = self.sites["nositemap"].url
        # header nav links count for discovery too; /about/ is a 404 here and is not a fetched page
        self.assertEqual([p["url"] for p in r["page_results"]], [base, base + "about/", base + "tours/", base + "faq/"])
        self.assertEqual(r["pages"], 3)
        self.assertEqual(r["main_text_words"], 2 + 10 + 6 + 21 + 21)  # link text inside main counts
        self.assertTrue(r["scorable"], r["reasons"])

    def test_explicit_pages_override_the_sitemap(self):
        base = self.sites["normal"].url
        r = scope_gate.run_gate(base, pages=[base + "contact/"])
        self.assertEqual((r["pages"], r["main_text_words"]), (1, 7))
        self.assertFalse(r["scorable"])

    def test_cli_under_isolated_mode_exits_zero_with_the_contract_keys(self):
        run = subprocess.run([sys.executable, "-I", str(SCRIPTS / "scope_gate.py"), self.sites["blocked"].url],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        out = json.loads(run.stdout)
        for key in ("scorable", "reasons", "blocked_all", "noindex_pages", "pages", "main_text_words", "threshold_words"):
            self.assertIn(key, out)
        self.assertEqual(out["threshold_words"], 50)
        self.assertFalse(out["scorable"])

    def test_unreachable_site_still_exits_zero(self):
        run = subprocess.run([sys.executable, "-I", str(SCRIPTS / "scope_gate.py"), "http://127.0.0.1:9/"],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(json.loads(run.stdout)["scorable"])


class RobotsRule(unittest.TestCase):
    def test_named_search_or_ai_group_reopens_the_root(self):
        for txt in ("User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nAllow: /\n",
                    "User-agent: *\nDisallow: /\n\nUser-agent: OAI-SearchBot\nDisallow:\n"):
            self.assertFalse(scope_gate.robots_verdict(txt)[0], txt)

    def test_tool_bots_and_partial_rules_do_not_count(self):
        self.assertTrue(scope_gate.robots_verdict("User-agent: *\nDisallow: /\n\nUser-agent: SemrushBot\nAllow: /\n")[0])
        self.assertTrue(scope_gate.robots_verdict("User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nDisallow: /\n")[0])
        self.assertFalse(scope_gate.robots_verdict("User-agent: *\nDisallow: /private/\n")[0])
        self.assertFalse(scope_gate.robots_verdict("")[0])


def _gate_on(main_html, threshold=scope_gate.THRESHOLD_WORDS):
    fetch = scope_gate._fixture_fetcher({"/": page(main_html)})
    return scope_gate.run_gate("https://edge.test/", fetch=fetch, threshold=threshold)


class Boundary(unittest.TestCase):
    """49 main-text words is not scorable, 50 is; the cut is a named, overridable constant.

    50 sits between the thin negative eval case-09 (13 words) and the lowest positive case,
    case-06 (78 words over 5 pages)."""

    def test_constant(self):
        self.assertEqual(scope_gate.THRESHOLD_WORDS, 50)

    def test_english_49_and_50(self):
        r49, r50 = _gate_on("<p>%s</p>" % words(49)), _gate_on("<p>%s</p>" % words(50))
        self.assertEqual((r49["main_text_words"], r49["scorable"]), (49, False))
        self.assertEqual((r50["main_text_words"], r50["scorable"]), (50, True))

    @unittest.skipUnless(thai_available(), "pythainlp not installed")
    def test_thai_49_and_50_counted_by_text_words(self):
        t50 = TH_SENTENCE * 10
        t49 = TH_SENTENCE * 9 + TH_WORD * 4
        self.assertEqual((count_words(t49), count_words(t50)), (49, 50))
        r49, r50 = _gate_on("<p>%s</p>" % t49), _gate_on("<p>%s</p>" % t50)
        self.assertEqual((r49["main_text_words"], r49["scorable"]), (49, False))
        self.assertEqual((r50["main_text_words"], r50["scorable"]), (50, True))

    def test_threshold_override(self):
        r = _gate_on("<p>%s</p>" % words(60), threshold=100)
        self.assertFalse(r["scorable"])
        self.assertEqual(r["threshold_words"], 100)
        run = subprocess.run([sys.executable, "-I", str(SCRIPTS / "scope_gate.py"), "--self-test"],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_from_dir_reads_a_local_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_site(tmp, THIN)
            run = subprocess.run([sys.executable, "-I", str(SCRIPTS / "scope_gate.py"), "https://nimman.test/",
                                  "--from-dir", tmp, "--threshold", "10"],
                                 capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = json.loads(run.stdout)
        self.assertEqual((out["main_text_words"], out["threshold_words"], out["scorable"]), (17, 10, True))


class ThaiWithoutPythainlp(unittest.TestCase):
    """Lite does not require pythainlp. Without it a Thai run counts one word per 5 Thai
    characters, so a short Thai site is not mistaken for an empty one (case-06 in the eval
    fell to 33 words, under the cut, when each Thai run counted as one word)."""

    def setUp(self):
        self.saved = text_words._tokenize
        text_words._tokenize = False

    def tearDown(self):
        text_words._tokenize = self.saved

    def test_estimate_is_chars_over_five(self):
        self.assertEqual(count_words(TH_SENTENCE), math.ceil(len(TH_SENTENCE) / 5))
        self.assertEqual(count_words("SEO " + TH_WORD), 2)

    def test_short_thai_site_stays_gradable(self):
        r = _gate_on("<p>%s</p>" % " ".join([TH_SENTENCE] * 12))
        self.assertGreaterEqual(r["main_text_words"], 50)
        self.assertTrue(r["scorable"], r["reasons"])


class BuildSummaryRefusesCounts(unittest.TestCase):
    def setUp(self):
        self.gate = scope_gate.run_gate("https://greenleaf.test/", fetch=scope_gate._fixture_fetcher(
            {"/robots.txt": BLOCKED["/robots.txt"], "/": page("<h1>Tea</h1>", NOINDEX)}))
        self.agent = {"site": {"fetched_at": "2026-11-21T00:00:00+00:00", "pages_audited": 1, "checks_passed": 4,
                               "checks_applicable": 5, "failing_checks_by_pages": {}, "could_not_verify": [], "checks": {}},
                      "pages": []}
        self.checklist = {"platforms": [{"id": "chatgpt", "label": "ChatGPT", "status": "critical",
                                         "crawler_access": "blocked", "note": "blocked"}],
                          "dimensions": [{"key": "platform_checklist", "label": "Platform checklist", "passed": 3, "total": 40}]}

    def _build(self, gate):
        return build_summary.build(agent=self.agent, checklist=self.checklist, client="Greenleaf",
                                   domain="greenleaf.test", lang="en", tier2="work/greenleaf-test/04-reports/r.html",
                                   run_id="t", scope_gate=gate)

    def test_control_without_a_gate_has_counts(self):
        s = self._build(None)
        self.assertTrue(s["dimensions"])
        self.assertTrue(s["platforms"])

    def test_closed_gate_leaves_no_count_or_level_on_the_card(self):
        for gate in (self.gate, {"scope_gate": self.gate}):
            s = self._build(gate)
            for key in ("score", "dimensions", "platforms", "competitors", "query_matrix"):
                self.assertNotIn(key, s)
            self.assertTrue(s["key_risk"]["title"].startswith("Not graded: blocked"), s["key_risk"])
            self.assertIn("50-word threshold", s["key_risk"]["body"])
            self.assertTrue(s["transparency"]["could_not_verify"][0].startswith("scope gate: blocked"))
            self.assertNotIn("19-tab", s["handoff"]["tier2_label"])
            self.assertEqual(len(s["next_steps"]), 1)
            self.assertIn("so-audit-lite", s["next_steps"][0]["prompt"])
            self.assertEqual(validate(s) + lint(s), [])

    def test_thai_card_labels(self):
        s = build_summary.build(agent=self.agent, client="Greenleaf", domain="greenleaf.test", lang="th",
                                tier2="r.html", run_id="t", scope_gate=self.gate)
        self.assertNotIn("19", s["handoff"]["tier2_label"])
        self.assertNotIn("dimensions", s)

    def test_open_gate_changes_nothing(self):
        s = self._build({"scope_gate": {"scorable": True, "reasons": []}})
        self.assertTrue(s["dimensions"])


if __name__ == "__main__":
    unittest.main()
