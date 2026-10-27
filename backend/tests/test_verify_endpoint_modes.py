from fastapi.testclient import TestClient

from app.api.schemas import ClaimVerificationResponse
from app.main import app, rag_service

client = TestClient(app)


def _ok(claim):
    return ClaimVerificationResponse(
        claim=claim, verdict="SUPPORTED", confidence=0.9, explanation="e",
        evidence=[], supporting_evidence=[], contradicting_evidence=[],
        source_chunk_ids=[], sources=[])


def _stub(monkeypatch):
    calls = []

    def fake(claim, **kwargs):
        calls.append(kwargs)
        return _ok(claim)

    monkeypatch.setattr(rag_service, "verify_claim", fake)
    return calls


def test_verify_invalid_source_mode_is_400_and_never_reaches_service(monkeypatch):
    calls = _stub(monkeypatch)
    r = client.post("/verify", json={"claim": "x", "source_mode": "everything"})
    assert r.status_code == 400
    assert calls == []


def test_verify_without_source_mode_keeps_legacy_call(monkeypatch):
    calls = _stub(monkeypatch)
    r = client.post("/verify", json={"claim": "x"})
    assert r.status_code == 200
    assert len(calls) == 1 and "source_mode" not in calls[0]


def test_verify_passes_valid_source_mode_through(monkeypatch):
    calls = _stub(monkeypatch)
    r = client.post("/verify", json={"claim": "x", "source_mode": "web"})
    assert r.status_code == 200
    assert calls[0]["source_mode"] == "web"
