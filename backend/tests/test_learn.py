import re
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import engine, learn, main

c = TestClient(main.app)
T = "Join the Moonshot Wealth Circle today. Wire the entry amount of {amt} to {name} to confirm your seat."
NAMES = [("5000", "Ravi"), ("7500", "Anita"), ("6000", "Joseph")]


@pytest.fixture(autouse=True)
def _clean():
    main._hits.clear()


def seed(label="scam"):
    return [learn.contribute(T.format(amt=a, name=n), "en", label) for a, n in NAMES]


def test_nothing_is_learned_or_stored_without_contributions():
    assert learn.public()["contributions"] == 0 and learn.candidates() == []


def test_fragments_are_masked_and_hold_no_digits_links_or_ids():
    g = learn.grams("Pay raj@okaxis 98765 via https://evil.example/x or call 9876543210 now")
    assert g and not any(re.search(r"\d|raj|evil|okaxis|zz", x.replace("#", "")) for x in g)


def test_miner_finds_recurring_scam_phrases_but_never_names_or_one_offs():
    seed()
    assert engine.analyze(T.format(amt="1", name="Meena"))["state"] != "HIGH"
    ph = {x["phrase"] for x in learn.candidates(10 ** 6)}
    assert "moonshot wealth circle" in ph and "moonshot wealth" not in ph and "the entry amount" in ph
    assert not any(n.lower() in p for p in ph for _, n in NAMES)  # names appear once, below the support threshold


def test_human_approval_gates_detection_and_rejected_phrases_stay_out():
    seed()
    probe = "We kindly request the entry amount from you"
    assert "community_pattern" not in {f["id"] for f in engine.analyze(probe)["findings"]}
    with pytest.raises(ValueError):
        learn.decide("never seen phrase", "approved")
    learn.decide("the entry amount", "approved")
    learn.decide("wealth circle today", "rejected")
    f = {x["id"]: x for x in engine.analyze(probe)["findings"]}["community_pattern"]
    assert f["evidence"][0]["text"] == "the entry amount"
    assert "wealth circle today" not in {x["phrase"] for x in learn.candidates(10 ** 6)}


def test_similar_reports_are_recognised_after_three_but_not_before():
    learn.contribute(T.format(amt="1", name="A"), "en", "scam")
    learn.contribute(T.format(amt="2", name="B"), "en", "scam")
    new = T.format(amt="9", name="Meena")
    assert "community_pattern" not in {f["id"] for f in engine.analyze(new)["findings"]}
    learn.contribute(T.format(amt="3", name="C"), "en", "scam")
    r = engine.analyze(new)
    assert "community_pattern" in {f["id"] for f in r["findings"]} and r["state"] == "VERIFY"


def test_not_scam_reports_block_a_phrase():
    seed()
    for i in range(4):
        learn.contribute(f"Our club newsletter: the entry amount is listed in the notice {i}", "en", "not_scam")
    assert "the entry amount" not in {x["phrase"] for x in learn.candidates(10 ** 6)}


def test_it_measures_its_own_accuracy_and_counts_missed_scams():
    seed()
    learn.contribute("Guaranteed 40% returns, send your OTP now", "en", "scam")
    learn.contribute("Mutual fund investments are subject to market risks.", "en", "not_scam")
    e = learn.evaluate()
    assert e["n"] == 5 and e["missed"] == 3 and e["recall"] == pytest.approx(0.25) and e["precision"] == 1.0


def test_api_requires_consent_and_supports_deletion():
    body = {"text": T.format(amt="5", name="Z"), "lang": "en", "label": "scam", "consent": False}
    assert c.post("/api/contribute", json=body).status_code == 400
    j = c.post("/api/contribute", json={**body, "consent": True}).json()
    assert j["shared"] and learn.public()["contributions"] == 1
    assert c.delete(f"/api/contribute/{j['token']}").json() == {"deleted": True} and learn.public()["contributions"] == 0
    assert c.delete("/api/contribute/nope").json() == {"deleted": False}
    assert c.post("/api/contribute", json={**body, "consent": True, "label": "maybe"}).status_code == 422


def test_admin_endpoints_are_locked_without_the_token(monkeypatch):
    seed()
    assert c.get("/api/admin/candidates").status_code == 403
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    assert c.get("/api/admin/candidates", headers={"x-admin-token": "wrong"}).status_code == 403
    cands = c.get("/api/admin/candidates", headers={"x-admin-token": "s3cret"}).json()["candidates"]
    assert len(cands) <= 20
    assert cands and all(x["support"] >= 3 for x in cands)
    assert c.post("/api/admin/decide", json={"phrase": "the entry amount", "decision": "approved"}, headers={"x-admin-token": "s3cret"}).status_code == 200
    assert c.post("/api/admin/decide", json={"phrase": "nope nope", "decision": "approved"}, headers={"x-admin-token": "s3cret"}).status_code == 422
    pub = c.get("/api/learning").json()
    assert [a["phrase"] for a in pub["approved"]] == ["the entry amount"] and "candidates" not in pub


def test_retention_deletes_old_contributions():
    with closing(learn._db()) as d, d:
        d.execute("INSERT INTO contrib VALUES('old',1,'en','scam','LOW','[]')")
    assert learn.public()["contributions"] == 1
    learn.contribute("a fresh message to keep", "en", "scam")
    assert learn.public()["contributions"] == 1 and learn.delete("old") is False
