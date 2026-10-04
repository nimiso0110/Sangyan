"""Opt-in learning loop.
Users who explicitly consent share MASKED 2-3 word fragments plus a label (never the full message). A miner finds phrases that recur in
scam reports and rarely in non-scam reports; a human approves each phrase before it can affect any result. The system also measures its
own accuracy on labelled data and remembers scam templates (similarity). Retention and deletion controls apply."""
import json
import os
import re
import secrets
import sqlite3
import sys
import time
from collections import Counter
from contextlib import closing
from pathlib import Path

from . import engine

K = int(os.getenv("LEARN_MIN_SUPPORT", "3"))
STOP = set("the a an to of and in is for you your on at be it this that with are will our we i me my".split())
PUNCT = " .,;:!?()[]{}\"'“”‘’…*_|/\\-"
DEFAULT_DB = str(Path(__file__).resolve().parent.parent / "data" / "learn.db")


def _db():
    path = os.getenv("LEARN_DB", DEFAULT_DB)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    d = sqlite3.connect(path)
    d.executescript("CREATE TABLE IF NOT EXISTS contrib(token TEXT PRIMARY KEY, ts INT, lang TEXT, label TEXT, pred TEXT, grams TEXT);"
                    "CREATE TABLE IF NOT EXISTS learned(phrase TEXT PRIMARY KEY, status TEXT, support INT, prec REAL, ts INT);")
    return d


def mask(t):
    t = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*", " zzid ", t)
    t = re.sub(r"https?://\S+|\b(?:[\w-]+\.)+[a-z]{2,24}\S*", " zzurl ", t, flags=re.I)
    return re.sub(r"\d+", "#", t)


def grams(text):
    """Masked, lower-cased 2- and 3-word fragments. Links, ids and digits never survive."""
    toks = [w for w in (x.strip(PUNCT) for x in mask(text).lower().split()) if w]
    out = []
    for n in (2, 3):
        for i in range(len(toks) - n + 1):
            g = toks[i:i + n]
            if any(x in ("zzurl", "zzid") for x in g) or all(x in STOP or x == "#" for x in g):
                continue
            out.append(" ".join(g))
    return list(dict.fromkeys(out))[:120]


_cache = None


def _inval():
    global _cache
    _cache = None


def _pat(p):
    return r"[\s.,;:!?'\"-]+".join(r"\d+" if t == "#" else re.escape(t) for t in p.split())


def _load():
    global _cache
    if _cache and time.time() - _cache[0] < 30:
        return _cache
    with closing(_db()) as d:
        ph = [p for (p,) in d.execute("SELECT phrase FROM learned WHERE status='approved'")]
        sc = [set(json.loads(g)) for (g,) in d.execute("SELECT grams FROM contrib WHERE label='scam'")]
    rx = re.compile("|".join(_pat(p) for p in sorted(ph, key=len, reverse=True)), re.I) if ph else None
    _cache = (time.time(), rx, sc)
    return _cache


def matches(text):
    """Used by the engine: (spans of human-approved phrases, number of similar scam reports if >= 3 else 0). Never breaks analysis."""
    try:
        _, rx, sc = _load()
        spans = [(m.start(), m.end()) for m in rx.finditer(text)] if rx else []
        g = set(grams(text))
        sim = sum(1 for s in sc if g and len(g & s) / len(g | s) >= 0.45)
        return spans, (sim if sim >= 3 else 0)
    except Exception:
        return [], 0


def install():
    engine.LEARNED = matches


def contribute(text, lang, label):
    r = engine.analyze(text, lang)  # what the engine predicted at the time (used for self-evaluation)
    token, g = secrets.token_urlsafe(9), grams(text)
    with closing(_db()) as d, d:
        d.execute("DELETE FROM contrib WHERE ts < ?", (int(time.time()) - int(os.getenv("LEARN_RETENTION_DAYS", "90")) * 86400,))
        d.execute("INSERT INTO contrib VALUES(?,?,?,?,?,?)", (token, int(time.time()), lang, label, r["state"], json.dumps(g)))
    _inval()
    return {"token": token, "shared": g}


def delete(token):
    with closing(_db()) as d, d:
        n = d.execute("DELETE FROM contrib WHERE token=?", (token,)).rowcount
    _inval()
    return n > 0


def candidates(limit=20):
    """Phrases frequent in scam reports, rare in non-scam reports, not already covered by rules. Missed scams are prioritised."""
    with closing(_db()) as d:
        rows = d.execute("SELECT label,pred,grams FROM contrib WHERE label IN ('scam','not_scam')").fetchall()
        done = {p for (p,) in d.execute("SELECT phrase FROM learned")}
    sc, ok, miss = Counter(), Counter(), Counter()
    for label, pred, g in rows:
        s = set(json.loads(g))
        (sc if label == "scam" else ok).update(s)
        if label == "scam" and pred == "LOW":
            miss.update(s)
    out = []
    for p, n in sc.items():
        prec = n / (n + ok[p] + 1)
        if n >= K and p not in done and prec >= 0.75 and not engine.analyze(p)["findings"]:
            out.append({"phrase": p, "support": n, "precision": round(prec, 2), "from_missed": miss[p]})
    # keep only the longest phrase when a shorter one is contained in it with the same or lower support (less noise for the reviewer)
    out = [c for c in out if not any(c["phrase"] != o["phrase"] and c["phrase"] in o["phrase"] and o["support"] >= c["support"] for o in out)]
    return sorted(out, key=lambda x: (-x["from_missed"], -x["precision"], -x["support"], x["phrase"]))[:limit]


def decide(phrase, status):
    c = next((x for x in candidates(10 ** 6) if x["phrase"] == phrase), None)
    if c is None:
        raise ValueError("not a current candidate")
    with closing(_db()) as d, d:
        d.execute("INSERT OR REPLACE INTO learned VALUES(?,?,?,?,?)", (phrase, status, c["support"], c["precision"], int(time.time())))
    _inval()


def evaluate():
    with closing(_db()) as d:
        rows = d.execute("SELECT label,pred FROM contrib WHERE label IN ('scam','not_scam')").fetchall()
    tp = sum(l == "scam" and p != "LOW" for l, p in rows)
    miss = sum(l == "scam" and p == "LOW" for l, p in rows)
    fp = sum(l == "not_scam" and p != "LOW" for l, p in rows)
    return {"n": len(rows), "recall": tp / (tp + miss) if tp + miss else None, "precision": tp / (tp + fp) if tp + fp else None, "missed": miss}


def public():
    with closing(_db()) as d:
        by = dict(d.execute("SELECT label,COUNT(*) FROM contrib GROUP BY label").fetchall())
        ap = d.execute("SELECT phrase,support FROM learned WHERE status='approved' ORDER BY ts DESC LIMIT 20").fetchall()
    return {"contributions": sum(by.values()), "by_label": by, "approved": [{"phrase": p, "support": s} for p, s in ap],
            "pending_candidates": len(candidates(10 ** 6)), "evaluation": evaluate(), "min_support": K}


if __name__ == "__main__":  # python -m app.learn candidates | approve "<phrase>" | reject "<phrase>"
    a = sys.argv[1:]
    if a[:1] == ["candidates"]:
        for c in candidates():
            print(f'{c["support"]:>3}  {c["precision"]:.2f}  {c["phrase"]}')
    elif len(a) == 2 and a[0] in ("approve", "reject"):
        decide(a[1], "approved" if a[0] == "approve" else "rejected")
        print("ok")
    else:
        print('usage: python -m app.learn candidates | approve "<phrase>" | reject "<phrase>"')
