#!/usr/bin/env python3
"""
scope_gate.py - decide whether a site can be graded at all, before any audit step runs.

A site that no crawler may fetch, or one with almost no content, has nothing a level or a
count of checks passed could measure. In the so-audit-lite eval (LITE-007 to LITE-009) runs
on the 13-word "Coming soon" case graded its content, citability and E-E-A-T with check
counts. This script makes the call deterministic; the agents read its verdict and give no
level and no count of checks passed when `scorable` is false (the field keeps its name from
rainmojo-so, where this script comes from: RSO-036, ported in LITE-015).

Checks (standard library fetches; robots.txt parsed by robots_generator.parse_robots):
  blocked_all      robots.txt has a `User-agent: *` group with `Disallow: /` (and no
                   `Allow: /`), and no named group for a search engine or AI crawler
                   re-allows the root
  noindex_pages    fetched pages whose meta robots (or X-Robots-Tag) says noindex or none
  main_text_words  visible text of <main> (or <body> when there is no <main>) without
                   nav, header, footer, script, style, noscript, template and svg;
                   identical paragraphs counted once across the whole set, words counted
                   with text_words.count_words (Thai segmented with pythainlp when it
                   is installed, estimated at one word per 5 Thai characters otherwise)
  client_rendered  a page with under 10 main-text words, an empty app-shell root (id root,
                   app, __next, __nuxt, ___gatsby, svelte or q-app) and at least one
                   <script src>; its emptiness is a client-side rendering finding, not thin
                   content
  scorable         false when blocked_all, when every fetched page is noindex, or when
                   main_text_words < threshold, unless every fetched page under the
                   threshold is client-rendered (THRESHOLD_WORDS = 50, --threshold to tune)

Why 50: on the ten so-audit eval snapshots the lowest positive case (case-06, a clean
Thai law firm) holds 78 main-text words over 5 pages, the "Coming soon" negative case-09
holds 13. A first cut of 150 would have withheld scores from six of the eight scorable
cases (78 to 138 words). The client-rendered case-03 holds 0 words, so no word count alone
separates it from case-09; the app-shell check does.

Pages: --pages URL... when given; otherwise the homepage plus the sitemap URLs (robots.txt
Sitemap lines, else /sitemap.xml; one level of sitemap index), capped at 10. When the sitemap
gives no page URL, same-host links found on the homepage are used instead (HTML pages only,
no fragments, mailto, tel or asset files), under the same cap. Sitemap URLs on another host
are re-based onto the given site URL, so a local mirror of a production site works.
--from-dir DIR reads the same files from a local folder instead of the network.

facts (never affect scorable): robots.txt, sitemap and llms.txt HTTP status, and per
fetched page its title, first H1, whether it has a meta description and a canonical, and its
JSON-LD block count; facts.missing lists in plain words what is absent site-wide, so a closed
gate still hands the agent every non-score finding it must report.

Exit code is 0 for every verdict: the script reports, it never fails the run.

Usage:
  python scope_gate.py https://example.com/
  python scope_gate.py http://127.0.0.1:8000/ --pages http://127.0.0.1:8000/ http://127.0.0.1:8000/about/
  python scope_gate.py https://example.test/ --from-dir evals/so-audit-lite/cases/case-09-thin/site
  python scope_gate.py --self-test
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _isolated_mode  # noqa: E402,F401  python -I leaves out user site-packages (LITE-009)

import ai_platforms  # noqa: E402
from robots_generator import parse_robots, _status_from_rules  # noqa: E402
from text_words import count_words  # noqa: E402

THRESHOLD_WORDS = 50
CLIENT_RENDERED_MAX_WORDS = 10
SHELL_IDS = {"root", "app", "__next", "__nuxt", "___gatsby", "svelte", "q-app"}
MAX_PAGES = 10
TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; RainmojoBot/1.0; +https://rainmojo.com)"

# Named groups that can re-open a site the wildcard group closed: every registry crawler
# except link previews and ad bots, plus search engines the registry does not track.
_EXTRA_SEARCH = {"googlebot-news", "googlebot-image", "yandex", "yandexbot", "baiduspider",
                 "duckduckbot", "slurp", "naverbot", "yeti", "seznambot", "sogou web spider"}


def _search_or_ai_tokens():
    toks = {c["token"].lower() for c in ai_platforms.crawlers() if c["role"] not in ("link_preview", "ads")}
    return toks | _EXTRA_SEARCH


# ---------------------------------------------------------------- fetching

def http_fetch(url):
    """(status, headers dict, text). Status 0 on a network error; never raises."""
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                                "Accept-Language": "th,en;q=0.9"})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(4 * 1024 * 1024)
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, dict(resp.headers.items()), raw.decode(charset, "replace")
    except HTTPError as e:
        return e.code, dict(e.headers.items()) if e.headers else {}, ""
    except (URLError, OSError, ValueError) as e:
        return 0, {"error": str(e)}, ""


def dir_fetcher(root):
    """A fetch function that maps a URL path onto files under root (index.html for folders)."""
    root = os.path.realpath(root)

    def fetch(url):
        path = urlparse(url).path or "/"
        rel = path.lstrip("/")
        cand = os.path.realpath(os.path.join(root, *[p for p in rel.split("/") if p]))
        if not (cand == root or cand.startswith(root + os.sep)):
            return 404, {}, ""
        if os.path.isdir(cand):
            cand = os.path.join(cand, "index.html")
        if not os.path.isfile(cand):
            return 404, {}, ""
        with open(cand, encoding="utf-8", errors="replace") as f:
            return 200, {}, f.read()
    return fetch


# ---------------------------------------------------------------- robots

def robots_verdict(robots_txt):
    """(blocked_all, detail) from robots.txt text, using the plugin's own parser."""
    rules, sitemaps = parse_robots(robots_txt or "")
    wild = rules.get("*")
    if not wild or _status_from_rules(wild) != "BLOCKED":
        return False, sitemaps, []
    search_ai = _search_or_ai_tokens()
    reopened = [v.get("token", k) for k, v in rules.items()
                if k != "*" and k in search_ai and _status_from_rules(v) != "BLOCKED"]
    return not reopened, sitemaps, reopened


# ---------------------------------------------------------------- html

_SKIP = {"nav", "header", "footer", "script", "style", "noscript", "template", "svg"}
_BLOCK = {"p", "div", "section", "article", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
          "table", "tr", "td", "th", "blockquote", "pre", "dl", "dt", "dd", "figure", "figcaption",
          "main", "body", "br", "hr", "form", "address", "details", "summary"}
_VOID = {"br", "hr", "img", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}


class _PageParser(HTMLParser):
    """Collects meta robots and the text blocks of <main> and of <body>, outside skipped tags."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.robots_meta = []
        self.skip = 0
        self.in_body = 0
        self.in_main = 0
        self.has_main = False
        self.body_blocks, self.main_blocks = [], []
        self._body_buf, self._main_buf = [], []
        self.links, self.script_src = [], 0
        self.shell_tag, self.shell_depth, self.shell_text, self.empty_shell = None, 0, [], False
        self.title, self.h1 = None, None
        self.meta_description, self.canonical, self.json_ld = False, False, 0
        self._capture, self._cap_buf = None, []

    def _flush(self):
        for buf, out in ((self._body_buf, self.body_blocks), (self._main_buf, self.main_blocks)):
            text = " ".join("".join(buf).split())
            if text:
                out.append(text)
            del buf[:]

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta" and a.get("name", "").lower() in ("robots", "googlebot", "bingbot"):
            self.robots_meta.append(a.get("content", "").lower())
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"].strip())
        elif tag == "meta" and a.get("name", "").lower() == "description" and a.get("content", "").strip():
            self.meta_description = True
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split() and a.get("href", "").strip():
            self.canonical = True
        elif tag == "script":
            if a.get("src", "").strip():
                self.script_src += 1
            if a.get("type", "").strip().lower() == "application/ld+json":
                self.json_ld += 1
        if self._capture is None and ((tag == "title" and self.title is None) or (tag == "h1" and self.h1 is None)):
            self._capture, self._cap_buf = tag, []
        if (self.shell_tag is None and not self.empty_shell and tag not in _VOID
                and a.get("id", "").strip().lower() in SHELL_IDS):
            self.shell_tag, self.shell_depth, self.shell_text = tag, 0, []
        if tag == self.shell_tag:
            self.shell_depth += 1
        if tag in _VOID:
            if tag in _BLOCK:
                self._flush()
            return
        if tag in _BLOCK:
            self._flush()
        if tag in _SKIP:
            self.skip += 1
        elif tag == "body":
            self.in_body += 1
        elif tag == "main":
            self.in_main += 1
            self.has_main = True

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        if tag == self._capture:
            setattr(self, tag, " ".join("".join(self._cap_buf).split()) or None)
            self._capture = None
        if tag == self.shell_tag:
            self.shell_depth -= 1
            if self.shell_depth <= 0:
                self.empty_shell = not "".join(self.shell_text).strip()
                self.shell_tag = None
        if tag in _BLOCK:
            self._flush()
        if tag in _SKIP and self.skip:
            self.skip -= 1
        elif tag == "body" and self.in_body:
            self.in_body -= 1
        elif tag == "main" and self.in_main:
            self.in_main -= 1

    def handle_data(self, data):
        if self._capture is not None:
            self._cap_buf.append(data)
        if self.skip:
            return
        if self.shell_tag is not None:
            self.shell_text.append(data)
        if self.in_body:
            self._body_buf.append(data)
        if self.in_main:
            self._main_buf.append(data)

    def close(self):
        super().close()
        self._flush()


def parse_page(html):
    """noindex, main-text blocks, links, and the app-shell signals for one HTML document."""
    p = _PageParser()
    p.feed(html or "")
    p.close()
    meta = " ".join(p.robots_meta)
    return {"noindex": bool(re.search(r"\b(noindex|none)\b", meta)),
            "blocks": p.main_blocks if p.has_main else p.body_blocks,
            "links": p.links, "empty_shell": p.empty_shell, "script_src": p.script_src,
            "title": p.title, "h1": p.h1, "meta_description": p.meta_description,
            "canonical": p.canonical, "json_ld_blocks": p.json_ld}


def header_noindex(headers):
    val = " ".join(str(v) for k, v in (headers or {}).items() if k.lower() == "x-robots-tag").lower()
    return bool(re.search(r"\b(noindex|none)\b", val))


# ---------------------------------------------------------------- discovery

_ASSET_RE = re.compile(r"\.(?:jpe?g|png|gif|webp|avif|svg|ico|css|js|mjs|json|xml|txt|pdf|zip|gz|mp4|webm|mp3|"
                       r"woff2?|ttf|eot|docx?|xlsx?|pptx?|csv)$", re.I)


def homepage_links(links, page_url, base):
    """Same-host HTML page links from the homepage, fragment-free, in document order."""
    host = urlparse(base).netloc
    out = []
    for href in links:
        if not href or href.startswith("#") or re.match(r"^(?:mailto|tel|javascript|data|sms):", href, re.I):
            continue
        u = urlparse(urljoin(page_url, href))
        if u.scheme not in ("http", "https") or u.netloc != host or _ASSET_RE.search(u.path or ""):
            continue
        url = urlunparse((u.scheme, u.netloc, u.path or "/", "", u.query, ""))
        if url not in out:
            out.append(url)
    return out


# ---------------------------------------------------------------- sitemap

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)


def _rebase(url, base):
    u, b = urlparse(url), urlparse(base)
    if u.netloc and u.netloc != b.netloc:
        return urlunparse((b.scheme, b.netloc, u.path or "/", "", u.query, ""))
    return url


def first_sitemap(base, declared):
    return ([_rebase(s, base) for s in declared] or [urljoin(base, "/sitemap.xml")])[0]


def sitemap_urls(fetch, base, declared, statuses=None):
    """Page URLs from the sitemap(s), re-based onto base, one level of index followed.
    statuses, when given, receives {sitemap URL: HTTP status} for every sitemap fetched."""
    starts = [_rebase(s, base) for s in declared] or [urljoin(base, "/sitemap.xml")]
    pages, seen = [], set()
    queue = list(starts)
    depth = {u: 0 for u in queue}
    while queue and len(pages) < MAX_PAGES * 3:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        status, _h, text = fetch(sm)
        if statuses is not None:
            statuses[sm] = status
        if status != 200 or not text:
            continue
        locs = [_rebase(x.strip(), base) for x in _LOC_RE.findall(text)]
        if re.search(r"<sitemapindex\b", text, re.I):
            if depth[sm] < 1:
                for loc in locs:
                    depth.setdefault(loc, depth[sm] + 1)
                    queue.append(loc)
            continue
        pages.extend(locs)
    return pages


# ---------------------------------------------------------------- gate

def run_gate(site, pages=None, fetch=http_fetch, threshold=THRESHOLD_WORDS):
    base = site if urlparse(site).scheme else "https://" + site
    if not urlparse(base).path:
        base += "/"
    robots_status, _h, robots_txt = fetch(urljoin(base, "/robots.txt"))
    if robots_status != 200:
        robots_txt = ""
    blocked_all, declared_sitemaps, reopened = robots_verdict(robots_txt)

    home = urljoin(base, "/")
    discovery = "pages"
    sm_url, sm_status = first_sitemap(base, declared_sitemaps), {}
    if pages:
        targets = list(pages)
        sm_status[sm_url] = fetch(sm_url)[0]
    else:
        found = sitemap_urls(fetch, base, declared_sitemaps, sm_status)
        discovery = "sitemap" if found else "homepage_links"
        targets = [home] + found
    ordered = []
    for u in targets:
        if u not in ordered:
            ordered.append(u)
    ordered = ordered[:MAX_PAGES]

    seen_blocks = set()
    page_results, fetched, noindex_pages, total_words, csr_pages = [], 0, 0, 0, 0
    i = 0
    while i < len(ordered):
        url = ordered[i]
        i += 1
        status, headers, html = fetch(url)
        entry = {"url": url, "status": status}
        if status == 200 and html:
            fetched += 1
            parsed = parse_page(html)
            noindex = parsed["noindex"] or header_noindex(headers)
            words = 0
            for block in parsed["blocks"]:
                if block in seen_blocks:
                    continue
                seen_blocks.add(block)
                words += count_words(block)
            client_rendered = (words < CLIENT_RENDERED_MAX_WORDS and parsed["empty_shell"]
                               and parsed["script_src"] > 0)
            noindex_pages += 1 if noindex else 0
            csr_pages += 1 if client_rendered else 0
            total_words += words
            entry.update({"noindex": noindex, "main_text_words": words, "client_rendered": client_rendered,
                          "title": parsed["title"], "h1": parsed["h1"],
                          "meta_description": parsed["meta_description"], "canonical": parsed["canonical"],
                          "json_ld_blocks": parsed["json_ld_blocks"]})
            if discovery == "homepage_links" and url == home:
                for link in homepage_links(parsed["links"], url, base):
                    if link not in ordered and len(ordered) < MAX_PAGES:
                        ordered.append(link)
        page_results.append(entry)

    reasons = []
    if blocked_all:
        reasons.append("blocked: robots.txt disallows / for every crawler (User-agent: * with Disallow: /) "
                       "and no search or AI crawler group re-allows it")
    if fetched and noindex_pages == fetched:
        reasons.append("noindex: all %d fetched pages carry a noindex directive" % fetched)
    # A shortfall explained by client-side rendering is a finding, not thin content.
    short = [p for p in page_results if "main_text_words" in p and p["main_text_words"] < threshold]
    explained = bool(short) and all(p["client_rendered"] for p in short)
    if total_words < threshold and not explained:
        reasons.append("too little content: %d main-text words across %d fetched page%s, under the %d-word threshold"
                       % (total_words, fetched, "" if fetched == 1 else "s", threshold))
    llms_status = fetch(urljoin(base, "/llms.txt"))[0]
    facts = {"robots_txt_status": robots_status, "sitemap_url": sm_url, "sitemap_status": sm_status.get(sm_url),
             "llms_txt_status": llms_status,
             "missing": missing_facts(robots_status, sm_url, sm_status.get(sm_url), llms_status, page_results)}
    return {
        "scorable": not reasons,
        "reasons": reasons,
        "blocked_all": blocked_all,
        "noindex_pages": noindex_pages,
        "pages": fetched,
        "main_text_words": total_words,
        "threshold_words": threshold,
        "client_rendered_pages": csr_pages,
        "discovery": discovery,
        "site": base,
        "robots_status": robots_status,
        "reopened_by": reopened,
        "facts": facts,
        "page_results": page_results,
    }


def _status_text(status):
    return "no response" if not status else "HTTP %s" % status


def missing_facts(robots_status, sm_url, sm_status, llms_status, page_results):
    """Plain-word list of what is absent site-wide. Reported, never scored."""
    out = []
    if robots_status != 200:
        out.append("robots.txt (%s)" % _status_text(robots_status))
    if sm_status != 200:
        name = (urlparse(sm_url).path.rsplit("/", 1)[-1] or "sitemap.xml")
        out.append("%s (%s)" % (name, _status_text(sm_status)))
    if llms_status != 200:
        out.append("llms.txt (%s)" % _status_text(llms_status))
    pages = [p for p in page_results if "main_text_words" in p]
    n = len(pages)
    for key, label, absent in (("title", "title", lambda v: not v),
                               ("meta_description", "meta description", lambda v: not v),
                               ("canonical", "canonical", lambda v: not v),
                               ("json_ld_blocks", "structured data (JSON-LD)", lambda v: not v),
                               ("h1", "H1", lambda v: not v)):
        k = sum(1 for p in pages if absent(p.get(key)))
        if k:
            out.append("%s on %d of %d page%s" % (label, k, n, "" if n == 1 else "s"))
    return out


# ---------------------------------------------------------------- self-test

def _fixture_fetcher(files):
    def fetch(url):
        path = urlparse(url).path or "/"
        if path in files:
            return 200, {}, files[path]
        return 404, {}, ""
    return fetch


def _page(body, head=""):
    return "<!doctype html><html><head>%s</head><body><header><nav>Home About Contact</nav></header>%s" \
           "<footer>Copyright footer text here</footer></body></html>" % (head, body)


def self_test():
    para = "<p>%s</p>" % " ".join("word%d" % i for i in range(20))
    noindex = '<meta name="robots" content="noindex, nofollow">'
    # 1. blocked + noindex
    blocked = _fixture_fetcher({"/robots.txt": "User-agent: *\nDisallow: /\n",
                                "/": _page("<main>" + para * 2 + "</main>", noindex)})
    r = run_gate("https://blocked.test/", fetch=blocked)
    assert r["blocked_all"] and not r["scorable"] and r["noindex_pages"] == 1, r
    # 2. a named search crawler re-allows the root
    reopen = _fixture_fetcher({"/robots.txt": "User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nAllow: /\n",
                               "/": _page("<main>" + "".join("<p>%s %d</p>" % (para[3:-4], i) for i in range(5)) + "</main>")})
    r = run_gate("https://reopen.test/", fetch=reopen)
    assert not r["blocked_all"] and r["scorable"] and r["reopened_by"] == ["Googlebot"], r
    # 3. thin page, nav/header/footer excluded, repeated paragraph counted once
    thin = _fixture_fetcher({"/": _page("<main><h1>Coming soon</h1><p>Opens in December.</p><p>Opens in December.</p></main>")})
    r = run_gate("https://thin.test/", fetch=thin)
    assert r["main_text_words"] == 5 and not r["scorable"], r
    # 4. normal multi-page site from a sitemap on the production host
    site = {"/": _page("<main>" + para + "</main>"),
            "/sitemap.xml": "<urlset><url><loc>https://prod.test/a/</loc></url><url><loc>https://prod.test/b/</loc></url></urlset>",
            "/a/": _page("<main><p>%s alpha</p><p>%s gamma</p></main>" % (para[3:-4], para[3:-4])),
            "/b/": _page("<main><p>%s beta</p></main>" % para[3:-4])}
    r = run_gate("http://127.0.0.1:9/", fetch=_fixture_fetcher(site))
    assert r["pages"] == 3 and r["main_text_words"] == 83 and r["scorable"], r
    # 5. Thai text is segmented, not one word per run
    th = "\u0e04\u0e25\u0e34\u0e19\u0e34\u0e01\u0e40\u0e25\u0e40\u0e0b\u0e2d\u0e23\u0e4c\u0e40\u0e1b\u0e47\u0e19\u0e2a\u0e16\u0e32\u0e19\u0e1e\u0e22\u0e32\u0e1a\u0e32\u0e25"
    r = run_gate("https://th.test/", fetch=_fixture_fetcher({"/": _page("<main><p>%s</p></main>" % th)}))
    assert r["main_text_words"] == count_words(th), r
    # 6. an empty client-rendered app shell is a finding, not thin content
    shell = '<!doctype html><html><body><div id="root"></div><script src="/app.js"></script></body></html>'
    r = run_gate("https://spa.test/", fetch=_fixture_fetcher({"/": shell}))
    assert r["scorable"] and r["client_rendered_pages"] == 1 and r["main_text_words"] == 0, r
    # 7. no sitemap: pages come from homepage links
    nav = ('<main><p>a b c</p><a href="/x/">x</a> <a href="/y/#top">y</a> '
           '<a href="mailto:a@b.test">m</a> <a href="/z.pdf">z</a></main>')
    r = run_gate("https://links.test/", fetch=_fixture_fetcher({
        "/": _page(nav), "/x/": _page("<main>%s</main>" % para),
        "/y/": _page("<main><p>%s more</p></main>" % para[3:-4])}))
    assert r["discovery"] == "homepage_links" and r["pages"] == 3, r
    # 8. facts: a bare page on a host with no robots.txt, sitemap or llms.txt
    r = run_gate("https://bare.test/", fetch=_fixture_fetcher({"/": "<html><body><p>Soon</p></body></html>"}))
    assert r["facts"]["missing"] == ["robots.txt (HTTP 404)", "sitemap.xml (HTTP 404)", "llms.txt (HTTP 404)",
                                     "title on 1 of 1 page", "meta description on 1 of 1 page",
                                     "canonical on 1 of 1 page", "structured data (JSON-LD) on 1 of 1 page",
                                     "H1 on 1 of 1 page"], r["facts"]
    print("SELF-TEST PASS: scope_gate (8 fixtures, threshold %d)" % THRESHOLD_WORDS)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Decide whether a site can be scored (blocked, noindex, or too little content).")
    ap.add_argument("site", nargs="?", help="site URL or local mirror URL")
    ap.add_argument("--pages", nargs="+", help="page URLs to check instead of homepage plus sitemap")
    ap.add_argument("--from-dir", dest="from_dir", help="read robots.txt, sitemaps and pages from this local folder")
    ap.add_argument("--threshold", type=int, default=THRESHOLD_WORDS, help="minimum main-text words (default %(default)s)")
    ap.add_argument("--out", help="also write the JSON here")
    ap.add_argument("--self-test", dest="self_test", action="store_true")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.self_test:
        return self_test()
    if not args.site:
        ap.error("a site URL is required")
    fetch = dir_fetcher(args.from_dir) if args.from_dir else http_fetch
    result = run_gate(args.site, pages=args.pages, fetch=fetch, threshold=args.threshold)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
