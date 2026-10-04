import json
import re

from fastapi.testclient import TestClient

from app import main

c = TestClient(main.app)
PAGES = ["/", "/about", "/privacy", "/terms", "/resources", "/offline"]


def test_every_page_is_a_complete_html_document_with_site_chrome():
    for p in PAGES:
        r = c.get(p)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html"), p
        assert "ScamShield" in r.text and 'name="description"' in r.text and 'rel="manifest"' in r.text and "skip" in r.text.lower(), p
        assert 'href="/privacy"' in r.text and 'href="/terms"' in r.text, p


def test_internal_links_resolve_and_external_links_are_safe():
    seen = set()
    for p in PAGES:
        for href in re.findall(r'href="(/[^"#]*)"', c.get(p).text):
            if href not in seen:
                seen.add(href)
                assert c.get(href).status_code == 200, (p, href)
        for tag in re.findall(r'<a [^>]*href="https?://[^"]+"[^>]*>', c.get(p).text):
            assert "noopener" in tag, tag


def test_pages_are_csp_compatible_no_external_scripts_or_inline_handlers():
    for p in PAGES:
        t = c.get(p).text
        assert not re.search(r'<script[^>]+src="https?:', t) and not re.search(r'\son[a-z]+="', t) and "javascript:" not in t, p


def test_security_headers_and_docs_exception():
    h = c.get("/").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and "connect-src 'self'" in h["content-security-policy"] and h["cache-control"] == "no-cache"
    assert "content-security-policy" not in c.get("/api/docs").headers


def test_pwa_files():
    m = json.loads(c.get("/manifest.webmanifest").text)
    assert m["start_url"] == "/" and m["display"] == "standalone" and {i["sizes"] for i in m["icons"]} >= {"192x192", "512x512"}
    for i in m["icons"]:
        assert c.get(i["src"]).status_code == 200, i["src"]
    sw = c.get("/sw.js")
    assert sw.headers["content-type"].startswith("text/javascript") and 'startsWith("/api/")' in sw.text and sw.headers["service-worker-allowed"] == "/"
    assert c.get("/favicon.svg").headers["content-type"].startswith("image/svg") and c.get("/favicon.ico").status_code == 200
    assert "serviceWorker" in c.get("/").text


def test_robots_and_sitemap():
    assert "Disallow: /api/" in c.get("/robots.txt").text and "http://testserver/sitemap.xml" in c.get("/robots.txt").text
    s = c.get("/sitemap.xml").text
    assert "<loc>http://testserver/about</loc>" in s and "/api/" not in s


def test_404_is_a_page_for_browsers_and_json_for_the_api():
    r = c.get("/nope")
    assert r.status_code == 404 and "Page not found" in r.text and r.headers["content-type"].startswith("text/html")
    r = c.get("/api/nope")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}
    assert c.post("/api/analyze/text", json={"text": ""}).status_code == 422


def test_responses_are_compressed():
    r = c.get("/", headers={"accept-encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip" and r.num_bytes_downloaded < len(r.content) / 2  # wire size vs decoded size
