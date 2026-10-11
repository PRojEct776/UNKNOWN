import importlib.util
from pathlib import Path

from app.api.schemas import (
    ClaimVerificationRequest,
    ConceptDiscoveryRequest,
    DebateRequest,
    KnowledgeDNARequest,
    KnowledgeMindMapRequest,
    QueryRequest,
)

_PAYLOAD_PATH = (
    Path(__file__).resolve().parents[2] / "frontend" / "request_payload.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "frontend_request_payload",
    _PAYLOAD_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_payload = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_payload)


def test_verify_payload_matches_api_schema():
    payload = _payload.build_request_payload(
        _payload.FEATURE_VERIFY,
        "SAC-RAG saves tokens.",
    )
    ClaimVerificationRequest.model_validate(payload)


def test_discover_payload_matches_api_schema():
    payload = _payload.build_request_payload(
        _payload.FEATURE_DISCOVER,
        "adaptive retrieval",
    )
    ConceptDiscoveryRequest.model_validate(payload)


def test_debate_payload_matches_api_schema():
    payload = _payload.build_request_payload(
        _payload.FEATURE_DEBATE,
        "Should we compress?",
        "Yes",
        "No",
    )
    DebateRequest.model_validate(payload)


def test_query_style_payloads_match_api_schema():
    QueryRequest.model_validate(
        _payload.build_request_payload("Research Assistant", "What is SAC-RAG?")
    )
    KnowledgeDNARequest.model_validate(
        _payload.build_request_payload("Knowledge DNA", "Map SAC-RAG")
    )
    KnowledgeMindMapRequest.model_validate(
        _payload.build_request_payload("Knowledge Mind Map", "Map SAC-RAG")
    )
