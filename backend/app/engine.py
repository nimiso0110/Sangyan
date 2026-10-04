"""Deterministic scam-indicator engine. No network I/O: URLs are analysed as text only (SSRF-safe by design)."""
import io
import os
import re
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlparse

from .locales import L

LEARNED = None  # set by learn.install(): text -> (spans of approved phrases, count of similar scam reports)

W = {"community_pattern": 2, "sensitive_info": 5, "payment_request": 3, "guaranteed_returns": 3, "unrealistic_claims": 3,
     "impersonation": 2, "urgency": 2, "scarcity": 2, "social_engineering": 2}
_V = r"\b(?:send|share|give|tell|provide|submit|enter|forward|confirm)\b"
PAT = {
    "guaranteed_returns": r"guarantee[ds]?|assured\s+(?:returns?|profits?)|risk[- ]?free|100\s?%\s*(?:safe|sure|profit)|sure[- ]?shot|fixed\s+(?:profit|returns?)|double\s+(?:your\s+)?money|पक्का|गारंटी|दोगुना|உத்தரவாத\w*|இரட்டிப்பு",
    "unrealistic_claims": r"\b(?:[2-9]\d|\d{3,})\s?%\s*(?:returns?|profits?|monthly|weekly|daily|in\s+\d+\s+days?|per\s+(?:day|week|month))|(?:₹|rs\.?)\s?\d[\d,]*\s+(?:in|within)\s+\d+\s+(?:days?|hours?|weeks?)",
    "urgency": r"invest\s+(?:now|today)|only\s+today|today\s+only|last\s+chance|act\s+(?:now|immediately|fast)|hurry|only\s+\d+\s+(?:slots?|seats?|spots?)|\b(?:pay|transfer|send|reply|act|invest)\w*\b(?:\s+\w+){0,3}\s+immediately|within\s+\d+\s+(?:hours?|minutes?)|आज\s*ही|तुरंत|இன்றே|உடனடியாக|கடைசி\s*வாய்ப்பு",
    "scarcity": r"exclusive|\bvip\b|\bsecret\b|insider|early\s+access|limited\s+(?:seats?|slots?|period|offer|time)|invitation[- ]only|selected\s+(?:few|members)|private\s+(?:group|channel)|join\s+(?:our\s+)?(?:private\s+)?(?:whatsapp|telegram)|t\.me/\S+",
    "sensitive_info": _V + r"[^.\n]{0,30}?(?:\botp\b|\bpin\b|\bcvv\b|password|passcode|credentials|authentication\s+code)"
    r"|(?:ओटीपी|पासवर्ड|पिन|otp)(?:(?!मत|नहीं|कभी|\bन\b)[^.\n]){0,25}?(?:भेज|बता|साझा|शेयर|दें|दीजिए)"
    r"|(?:ஓடிபி|otp|கடவுச்சொல்)[^.\n]{0,25}?(?:அனுப்புங்கள்|அனுப்பவும்|சொல்லுங்கள்|பகிருங்கள்|பகிரவும்)",
    "payment_request": r"\b(?:pay|send|transfer|deposit|remit)\b[^.\n]{0,30}?(?:fees?\b|charges?\b|amount|money|deposit|margin|₹\s?\d|rs\.?\s?\d)|(?:registration|processing|verification|joining|security)\s+(?:fees?|deposit|charges?)|advance\s+payment|रजिस्ट्रेशन|பணம்\s*அனுப்ப\w*|கட்டணம்\s*செலுத்த\w*",
    "impersonation": r"(?:calling|contacting|writing|messaging)\s+(?:you\s+)?from\s+(?:the\s+)?(?:sebi|nse|bse|nsdl|rbi|regulat\w+|bank|customer\s+(?:care|support)|income\s*tax)|(?:sebi|nse|bse|nsdl|rbi)[\s-]*(?:registered|approved|certified|authori[sz]ed)|official\s+(?:partner|representative)|regulatory\s+(?:department|officer|team)|सेबी\s*(?:रजिस्टर्ड|अधिकारी)",
    "social_engineering": r"account\s+(?:will\s+be\s+|has\s+been\s+|is\s+)?(?:blocked|suspended|closed|frozen|deactivated)|legal\s+action|\barrest\b|kyc\s+(?:expired|expires|pending)|खाता\s*(?:बंद|ब्लॉक)|கணக்கு\s*(?:முடக்க|தடை)\w*",
}
RX = {k: re.compile(v, re.I) for k, v in PAT.items()}
NEG = re.compile(r"(?:\bnot\b|\bno\b|\bnever\b|\bwithout\b|n't)\W+(?:\w+\W+){0,3}$", re.I)
URL_RE = re.compile(r"(?:https?://)?(?:[\w-]+\.)+[a-z]{2,24}(?::\d+)?(?:/[^\s)]*)?", re.I)

OFFICIAL = {"sebi.gov.in", "nseindia.com", "bseindia.com", "nsdl.co.in", "cdslindia.com", "rbi.org.in", "amfiindia.com", "cybercrime.gov.in"}
BRANDS = ("sebi", "nsdl", "cdsl", "nseindia", "bseindia")
SHORT = {"bit.ly", "tinyurl.com", "cutt.ly", "rb.gy", "is.gd", "shorturl.at", "t.ly"}
RISKY = re.compile(r"\.(?:xyz|top|icu|vip|click|buzz|cfd|site|online|live|shop|cc|ws)$")
UW = {"look": 5, "brand": 4, "ip": 4, "userinfo": 5, "short": 2, "nohttps": 2, "tld": 2, "odd": 2}

BLOCK = re.compile(
    r"\b(?:you\s+should|i\s+recommend|we\s+recommend|consider)\s+(?:buying|selling|holding|to\s+buy|to\s+sell|buy|sell|hold)\b"
    r"|\b(?:buy|sell|hold)\s+(?:this|these|the)\s+(?:stock|share|fund|scheme)s?\b"
    r"|\b(?:price|return)s?\s+(?:prediction|forecast)\b|\b(?:will|is\s+expected\s+to)\s+(?:rise|fall|double|triple|gain)\b|\btarget\s+price\b", re.I)

DEMO = [  # Fictional examples for demonstration only.
    {"id": "guaranteed", "label": "Guaranteed return", "text": "Invest ₹5,000 today and get guaranteed ₹25,000 in 7 days."},
    {"id": "urgency", "label": "Urgency", "text": "Only 5 slots left. Transfer the amount immediately."},
    {"id": "otp", "label": "Credential request", "text": "Send your OTP to verify your investment account."},
    {"id": "impersonation", "label": "Impersonation", "text": "We are contacting you from the regulatory department. Pay the verification fee immediately."},
    {"id": "benign", "label": "Ordinary information", "text": "Mutual fund investments are subject to market risks. Returns are not guaranteed. Read all scheme documents carefully and never share your OTP with anyone."},
]


def guard(s, lang="en"):
    """Output guardrail: replace anything that reads as an investment recommendation or prediction."""
    return L[lang]["refusal"] if BLOCK.search(s) else s


def detect_lang(t):
    hi, ta = len(re.findall(r"[\u0900-\u097F]", t)), len(re.findall(r"[\u0B80-\u0BFF]", t))
    return "hi" if hi > ta and hi > 3 else "ta" if ta > 3 else "en"


def _reg(h):
    p = h.split(".")
    return ".".join(p[-3:] if len(p) > 2 and ".".join(p[-2:]) in {"gov.in", "co.in", "org.in", "nic.in", "ac.in"} else p[-2:])


def _norm(s):
    return s.replace("rn", "m").replace("vv", "w").replace("0", "o").replace("1", "i").replace("l", "i").replace("-", "")


def check_url(raw):
    raw = raw.strip()
    if not raw or re.search(r"\s", raw):
        return None
    try:
        u = urlparse(raw if "://" in raw else "http://" + raw)
        host = (u.hostname or "").lower()
    except ValueError:
        return None
    if "." not in host:
        return None
    given, iss = "://" in raw, []
    if given and u.scheme == "http":
        iss.append("nohttps")
    if "@" in u.netloc:
        iss.append("userinfo")
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        iss.append("ip")
    r = _reg(host)
    official, look = r in OFFICIAL, None
    if not official:
        if r in SHORT:
            iss.append("short")
        lab = _norm(r.split(".")[0])
        score, best = max((SequenceMatcher(None, lab, _norm(o.split(".")[0])).ratio(), o) for o in OFFICIAL)
        look = best if len(lab) >= 5 and score >= 0.86 else None
        if look:
            iss.append("look")
        elif any(b in lab and lab != b for b in BRANDS):
            iss.append("brand")
        if RISKY.search(r):
            iss.append("tld")
        if "xn--" in host or host.count(".") >= 4:
            iss.append("odd")
    return {"url": raw, "host": host, "https": (u.scheme == "https") if given else None, "official": official, "issues": iss, "x": look}


def _negated(text, s):
    return bool(NEG.search(text[max(0, s - 40):s]))


def _state(total):
    return "HIGH" if total >= 5 else "VERIFY" if total > 0 else "LOW"


def _report(text, lang, hits, links):
    T = L[lang]
    total = sum(W[c] for c in hits if c in W) + sum(UW[i] for k in links for i in k["issues"])
    st = _state(total)
    order = sorted(hits, key=lambda c: -(W.get(c) or 3))
    findings = [{"id": c, "title": guard(T["cat"][c][0], lang), "why": guard(T["cat"][c][1], lang),
                 "evidence": [{"text": text[a:b], "start": a, "end": b} for a, b in hits[c][:3]], "source": "rules"} for c in order]
    lk = [{"url": k["url"], "host": k["host"], "https": k["https"], "official": k["official"], "closest": k["x"], "flagged": bool(k["issues"]),
           "notes": [T["link"][i].replace("{x}", k["x"] or "") for i in k["issues"]] or [T["link"]["ok" if k["official"] else "nothing"]]} for k in links]
    return {"state": st, "state_label": T["state"][st], "summary": guard(T["sum"][st], lang), "findings": findings, "links": lk,
            "steps": [guard(s, lang) for s in T["steps"]], "disclaimer": T["disc"], "headings": T["h"], "text": text,
            "detected_language": detect_lang(text), "lang": lang, "mode": "rules", "_w": total}


def analyze(text, lang="en"):
    hits, links = {}, []
    for cat, rx in RX.items():
        for m in rx.finditer(text):
            if not _negated(text, m.start()):
                hits.setdefault(cat, []).append((m.start(), m.end()))
    if LEARNED:
        spans, sim = LEARNED(text)
        if spans or sim:
            hits.setdefault("community_pattern", []).extend(spans)
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(".,;:!?")
        if m.start() and text[m.start() - 1] == "@":
            continue
        c = check_url(u)
        if c:
            links.append(c)
            if c["issues"]:
                hits.setdefault("suspicious_link", []).append((m.start(), m.start() + len(u)))
    return _report(text, lang, hits, links)


def analyze_url(raw, lang="en"):
    c = check_url(raw)
    if not c:
        return None
    return _report(raw.strip(), lang, {"suspicious_link": [(0, len(raw.strip()))]} if c["issues"] else {}, [c])


class OcrUnavailable(Exception):
    pass


def _find_tesseract(pytesseract):
    """Windows installs Tesseract outside PATH by default; find it (or honour TESSERACT_CMD) so screenshots work out of the box."""
    import shutil
    if os.getenv("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    elif not shutil.which("tesseract"):
        for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break


def ocr(data):
    """Returns text, mean confidence (0-100) and which OCR languages were actually available. Greyscale + auto-contrast + upscale small images for better accuracy."""
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError as e:
        raise OcrUnavailable() from e
    _find_tesseract(pytesseract)
    Image.MAX_IMAGE_PIXELS = 25_000_000
    img = Image.open(io.BytesIO(data))
    img.load()
    img = ImageOps.autocontrast(ImageOps.exif_transpose(img).convert("L"))
    if img.width < 1000:
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    want = [x for x in os.getenv("OCR_LANGS", "eng+hin+tam").split("+") if x]
    try:
        have = set(pytesseract.get_languages(config=""))
        use = [x for x in want if x in have] or ["eng"]
        d = pytesseract.image_to_data(img, lang="+".join(use), output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as e:
        raise OcrUnavailable() from e
    lines, conf = {}, []
    for i, w in enumerate(d["text"]):
        if w.strip():
            lines.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(w)
            if float(d["conf"][i]) >= 0:
                conf.append(float(d["conf"][i]))
    return {"text": "\n".join(" ".join(v) for _, v in sorted(lines.items())), "confidence": round(sum(conf) / len(conf)) if conf else 0,
            "languages": use, "missing": [x for x in want if x not in have]}


EX = {  # Fictional teaching examples; each must trigger its own category (tested).
    "guaranteed_returns": "Join now for guaranteed profit, completely risk-free.", "unrealistic_claims": "Earn 40% returns every month.",
    "urgency": "Last chance! Only 5 slots left, invest now.", "scarcity": "Exclusive VIP access, invitation only.",
    "sensitive_info": "Send your OTP to confirm your account.", "payment_request": "Pay the registration fee of ₹2,000 to start.",
    "impersonation": "We are contacting you from the regulatory department.", "social_engineering": "Your account will be blocked and legal action will follow.",
    "suspicious_link": "Log in at https://nseindla.com/login"}


def indicators(lang="en"):
    T = L[lang]
    return [{"id": c, "title": T["cat"][c][0], "why": T["cat"][c][1], "example": EX[c], "weight": W.get(c, 5)} for c in T["cat"] if c in EX]


STATS = {"total": 0, "state": Counter(), "category": Counter(), "lang": Counter(), "input": Counter()}


def record(kind, r):
    """Anonymous counters only: no text, no identifiers."""
    STATS["total"] += 1
    STATS["state"][r["state"]] += 1
    STATS["lang"][r["lang"]] += 1
    STATS["input"][kind] += 1
    STATS["category"].update(f["id"] for f in r["findings"])


def stats():
    out = {k: dict(v) if isinstance(v, Counter) else v for k, v in STATS.items()}
    out["note"] = "Anonymous counters kept in memory since the server started. No content or identifiers are stored."
    return out
