import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from app import engine
from app.locales import L
from app.main import app

c = TestClient(app)
EXPECT = {"guaranteed": "HIGH", "urgency": "HIGH", "otp": "HIGH", "impersonation": "HIGH", "benign": "LOW"}


@pytest.mark.parametrize("d", engine.DEMO, ids=lambda d: d["id"])
def test_demo_cases(d):
    assert engine.analyze(d["text"])["state"] == EXPECT[d["id"]]


def test_evidence_offsets_point_at_the_flagged_phrase():
    r = engine.analyze(engine.DEMO[0]["text"])
    assert {"guaranteed_returns", "unrealistic_claims"} <= {f["id"] for f in r["findings"]}
    for f in r["findings"]:
        for e in f["evidence"]:
            assert r["text"][e["start"]:e["end"]] == e["text"]


def test_education_is_not_over_flagged():
    t = "Stock markets, mutual funds and returns are discussed in this SEBI investor awareness article. Investing involves risk."
    assert engine.analyze(t)["state"] == "LOW"


@pytest.mark.parametrize("url,states", [("https://www.sebi.gov.in/", {"LOW"}), ("https://nseindla.com/login", {"HIGH"}),
                                        ("http://203.0.113.5/pay", {"HIGH"}), ("bit.ly/abc", {"VERIFY"}), ("https://example.com/news", {"LOW"})])
def test_url_analysis(url, states):
    assert engine.analyze_url(url)["state"] in states


def test_lookalike_names_the_closest_official_site():
    k = engine.check_url("https://nseindla.com/login")
    assert "look" in k["issues"] and k["x"] == "nseindia.com"


def test_invalid_urls_are_rejected():
    assert engine.analyze_url("not a link") is None and engine.analyze_url("localhost") is None


def test_guardrail_blocks_recommendations_and_predictions():
    for s in ["You should buy this stock now", "This share will double next month", "Target price is 500"]:
        assert engine.guard(s) == L["en"]["refusal"]
    assert engine.guard("Verify the sender independently.") == "Verify the sender independently."


def test_locales_are_complete_and_pass_the_guardrail():
    en = L["en"]
    for lang, T in L.items():
        assert T["cat"].keys() == en["cat"].keys() and T["link"].keys() == en["link"].keys() and len(T["steps"]) == len(en["steps"])
        strings = [*T["state"].values(), *T["sum"].values(), *T["link"].values(), *T["h"].values(), *T["steps"], T["disc"]]
        strings += [x for pair in T["cat"].values() for x in pair]
        assert all(engine.guard(s, lang) == s for s in strings), lang


def test_all_three_languages_render():
    for lang in L:
        r = engine.analyze(engine.DEMO[0]["text"], lang)
        assert r["state_label"] == L[lang]["state"]["HIGH"] and r["findings"][0]["title"] == L[lang]["cat"][r["findings"][0]["id"]][0]


def test_language_detection():
    assert engine.detect_lang("पक्का मुनाफ़ा आज ही") == "hi" and engine.detect_lang("இன்றே முதலீடு செய்யுங்கள்") == "ta" and engine.detect_lang("hello") == "en"


def test_api_text_and_friendly_errors():
    ok = c.post("/api/analyze/text", json={"text": engine.DEMO[2]["text"], "lang": "ta"})
    assert ok.status_code == 200 and ok.json()["state"] == "HIGH"
    for bad in [{"text": ""}, {"text": "   "}, {"text": "x" * 6000}, {"text": "hi", "lang": "fr"}]:
        r = c.post("/api/analyze/text", json=bad)
        assert r.status_code == 422 and isinstance(r.json()["detail"], str) and "Traceback" not in r.text
    assert c.post("/api/analyze/url", json={"url": "nope"}).status_code == 422


def test_api_image_validation_and_ocr():
    assert c.post("/api/analyze/image", files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 415
    img = Image.new("RGB", (900, 120), "white")
    ImageDraw.Draw(img).text((10, 40), "Send your OTP to verify your account", fill="black", font_size=36)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    r = c.post("/api/analyze/image", files={"file": ("s.png", buf.getvalue(), "image/png")}, data={"lang": "en"})
    assert r.status_code in (200, 422, 503)
    if r.status_code == 200:
        assert r.json()["state"] == "HIGH" and "OTP" in r.json()["ocr_text"].upper()


def test_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "2")
    from app import main
    main._hits.clear()
    codes = [c.post("/api/analyze/text", json={"text": "hello"}).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and codes[-1] == 429
    main._hits.clear()


def test_every_teaching_example_triggers_its_own_category():
    for lang in L:
        for i in engine.indicators(lang):
            assert i["id"] in {f["id"] for f in engine.analyze(i["example"], lang)["findings"]}, i["id"]


def test_indicators_and_anonymous_stats_endpoints():
    before = c.get("/api/stats").json()["total"]
    c.post("/api/analyze/text", json={"text": engine.DEMO[1]["text"]})
    s = c.get("/api/stats").json()
    assert s["total"] == before + 1 and "urgency" in s["category"] and "text" not in s and "Only 5" not in str(s)
    assert len(c.get("/api/indicators?lang=ta").json()["indicators"]) == 9


def test_link_details_for_the_anatomy_view():
    k = engine.analyze_url("https://nseindla.com/login")["links"][0]
    assert k["closest"] == "nseindia.com" and k["flagged"] and k["https"] is True


def test_windows_tesseract_is_found_even_when_not_on_path(monkeypatch):
    import os
    import shutil
    import types
    fake = types.SimpleNamespace(pytesseract=types.SimpleNamespace(tesseract_cmd="tesseract"))
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(shutil, "which", lambda n: None)
    monkeypatch.setattr(os.path, "exists", lambda p: p.startswith("C:\\Program Files\\"))
    engine._find_tesseract(fake)
    assert fake.pytesseract.tesseract_cmd == "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    monkeypatch.setenv("TESSERACT_CMD", "X:\\my\\tesseract.exe")
    engine._find_tesseract(fake)
    assert fake.pytesseract.tesseract_cmd == "X:\\my\\tesseract.exe"
