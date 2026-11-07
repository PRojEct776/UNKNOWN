import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app, rag_service
from app.rag.research_comparison import (
    ComparisonAspect,
    ComparisonValue,
    ContradictionItem,
    ResearchComparisonEngine,
    ResearchComparisonReport,
    StrengthLimitation,
    UniqueContribution,
)

client = TestClient(app)

SAMPLE_CHUNKS_DOC_A = [
    {
        "chunk_id": "doc_a_c1",
        "document": "paper_a.pdf",
        "page": 1,
        "text": "Paper A introduces an autoregressive decoder achieving 85% accuracy on task X.",
        "rank": 1,
        "hybrid_score": 0.95,
    },
    {
        "chunk_id": "doc_a_c2",
        "document": "paper_a.pdf",
        "page": 3,
        "text": "Paper A assumes high-memory GPUs and requires 32GB VRAM during training.",
        "rank": 2,
        "hybrid_score": 0.85,
    },
]

SAMPLE_CHUNKS_DOC_B = [
    {
        "chunk_id": "doc_b_c1",
        "document": "paper_b.pdf",
        "page": 2,
        "text": "Paper B introduces a bidirectional encoder achieving 82% accuracy on task X with low latency.",
        "rank": 1,
        "hybrid_score": 0.92,
    },
    {
        "chunk_id": "doc_b_c2",
        "document": "paper_b.pdf",
        "page": 4,
        "text": "Paper B is designed for edge devices and runs on 4GB RAM.",
        "rank": 2,
        "hybrid_score": 0.80,
    },
]

SAMPLE_CHUNKS_DOC_C = [
    {
        "chunk_id": "doc_c_c1",
        "document": "paper_c.pdf",
        "page": 1,
        "text": "Paper C presents a hybrid encoder-decoder benchmarked across cross-domain tasks.",
        "rank": 1,
        "hybrid_score": 0.90,
    }
]

MOCK_LLM_JSON = json.dumps({
    "entities": ["paper_a.pdf", "paper_b.pdf"],
    "summary": "Paper A focuses on high-capacity autoregressive modeling, while Paper B focuses on lightweight bidirectional encoding.",
    "similarities": [
        "Both papers evaluate performance on benchmark task X.",
        "Both architectures utilize multi-head attention mechanisms."
    ],
    "differences": [
        "Paper A uses an autoregressive decoder whereas Paper B uses a bidirectional encoder.",
        "Paper A requires 32GB VRAM while Paper B operates within 4GB RAM on edge devices."
    ],
    "comparison": [
        {
            "aspect": "Architecture",
            "values": [
                {
                    "entity": "paper_a.pdf",
                    "value": "Autoregressive decoder",
                    "evidence": "Paper A introduces an autoregressive decoder",
                    "document": "paper_a.pdf",
                    "page": 1,
                    "chunk_id": "doc_a_c1"
                },
                {
                    "entity": "paper_b.pdf",
                    "value": "Bidirectional encoder",
                    "evidence": "Paper B introduces a bidirectional encoder",
                    "document": "paper_b.pdf",
                    "page": 2,
                    "chunk_id": "doc_b_c1"
                }
            ]
        },
        {
            "aspect": "Accuracy on Task X",
            "values": [
                {
                    "entity": "paper_a.pdf",
                    "value": "85%",
                    "evidence": "achieving 85% accuracy on task X",
                    "document": "paper_a.pdf",
                    "page": 1,
                    "chunk_id": "doc_a_c1"
                },
                {
                    "entity": "paper_b.pdf",
                    "value": "82%",
                    "evidence": "achieving 82% accuracy on task X",
                    "document": "paper_b.pdf",
                    "page": 2,
                    "chunk_id": "doc_b_c1"
                }
            ]
        }
    ],
    "contradictions": [
        {
            "topic": "Optimal Pre-training Conditioning",
            "claim_a": "Autoregressive modeling yields superior representations on task X.",
            "document_a": "paper_a.pdf",
            "claim_b": "Bidirectional conditioning achieves comparable accuracy with lower compute.",
            "document_b": "paper_b.pdf",
            "explanation": "Paper A claims autoregressive scaling is necessary for top accuracy, whereas Paper B demonstrates bidirectional encoding suffices for edge efficiency.",
            "evidence_chunks": ["doc_a_c1", "doc_b_c1"]
        }
    ],
    "unique_contributions": [
        {
            "document": "paper_a.pdf",
            "contribution": "Autoregressive scaling recipe for task X.",
            "evidence": "Paper A introduces an autoregressive decoder achieving 85% accuracy",
            "chunk_id": "doc_a_c1"
        },
        {
            "document": "paper_b.pdf",
            "contribution": "Lightweight edge deployment model.",
            "evidence": "Paper B is designed for edge devices and runs on 4GB RAM",
            "chunk_id": "doc_b_c2"
        }
    ],
    "strengths_and_limitations": [
        {
            "document": "paper_a.pdf",
            "strengths": ["Higher absolute accuracy (85%)"],
            "limitations": ["High memory requirement (32GB VRAM)"]
        },
        {
            "document": "paper_b.pdf",
            "strengths": ["Runs on 4GB RAM on edge devices", "Low latency"],
            "limitations": ["Slightly lower accuracy (82%)"]
        }
    ],
    "synthesis": "Paper A is optimal when maximum accuracy is required and hardware is unconstrained, whereas Paper B provides an efficient alternative for resource-constrained environments.",
    "sources": [
        {"document": "paper_a.pdf", "page": 1, "chunk_id": "doc_a_c1"},
        {"document": "paper_b.pdf", "page": 2, "chunk_id": "doc_b_c1"}
    ]
})


def test_two_document_comparison():
    """Verify comparing two documents retrieves evidence from both and produces full report."""
    def fake_search(q, top_k=None, document_names=None):
        if document_names == ["paper_a.pdf"]:
            return SAMPLE_CHUNKS_DOC_A
        if document_names == ["paper_b.pdf"]:
            return SAMPLE_CHUNKS_DOC_B
        return SAMPLE_CHUNKS_DOC_A + SAMPLE_CHUNKS_DOC_B

    fake_resp = MagicMock()
    fake_resp.success = True
    fake_resp.answer = MOCK_LLM_JSON

    with patch.object(rag_service, "_search", side_effect=fake_search), \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp):
        report = rag_service.compare_research("Compare Paper A and Paper B", document_names=["paper_a.pdf", "paper_b.pdf"])

        assert len(report.entities) == 2
        assert "paper_a.pdf" in report.entities
        assert "paper_b.pdf" in report.entities
        assert len(report.similarities) == 2
        assert len(report.differences) == 2
        assert len(report.comparison) == 2
        assert len(report.contradictions) == 1
        assert report.contradictions[0].topic == "Optimal Pre-training Conditioning"
        assert len(report.unique_contributions) == 2
        assert len(report.strengths_and_limitations) == 2
        assert "Paper A is optimal" in report.synthesis
        assert len(report.sources) == 2


def test_multiple_document_comparison():
    """Verify comparing 3 or more documents balances retrieval across all selected documents."""
    queried_docs = []

    def fake_search(q, top_k=None, document_names=None):
        if document_names:
            queried_docs.extend(document_names)
        if document_names == ["paper_a.pdf"]:
            return SAMPLE_CHUNKS_DOC_A
        if document_names == ["paper_b.pdf"]:
            return SAMPLE_CHUNKS_DOC_B
        if document_names == ["paper_c.pdf"]:
            return SAMPLE_CHUNKS_DOC_C
        return SAMPLE_CHUNKS_DOC_A + SAMPLE_CHUNKS_DOC_B + SAMPLE_CHUNKS_DOC_C

    fake_resp = MagicMock()
    fake_resp.success = True
    fake_resp.answer = json.dumps({
        "entities": ["paper_a.pdf", "paper_b.pdf", "paper_c.pdf"],
        "summary": "Three-way comparison of architectures A, B, and C.",
        "similarities": ["All three evaluate attention-based neural networks."],
        "differences": ["Differ in encoder vs decoder focus and target compute budgets."],
        "comparison": [
            {
                "aspect": "Architecture",
                "values": [
                    {"entity": "paper_a.pdf", "value": "Autoregressive", "evidence": "AR decoder", "document": "paper_a.pdf", "page": 1, "chunk_id": "doc_a_c1"},
                    {"entity": "paper_b.pdf", "value": "Bidirectional", "evidence": "Bi encoder", "document": "paper_b.pdf", "page": 2, "chunk_id": "doc_b_c1"},
                    {"entity": "paper_c.pdf", "value": "Hybrid", "evidence": "Hybrid encoder-decoder", "document": "paper_c.pdf", "page": 1, "chunk_id": "doc_c_c1"}
                ]
            }
        ],
        "contradictions": [],
        "unique_contributions": [
            {"document": "paper_c.pdf", "contribution": "Cross-domain hybridization", "evidence": "hybrid encoder-decoder", "chunk_id": "doc_c_c1"}
        ],
        "strengths_and_limitations": [
            {"document": "paper_c.pdf", "strengths": ["Cross-domain breadth"], "limitations": ["Higher parameter count"]}
        ],
        "synthesis": "Each paper targets distinct operational regimes.",
        "sources": [{"document": "paper_c.pdf", "page": 1, "chunk_id": "doc_c_c1"}]
    })

    with patch.object(rag_service, "_search", side_effect=fake_search), \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp):
        report = rag_service.compare_research(
            "Compare architectures",
            document_names=["paper_a.pdf", "paper_b.pdf", "paper_c.pdf"]
        )

        assert "paper_a.pdf" in queried_docs
        assert "paper_b.pdf" in queried_docs
        assert "paper_c.pdf" in queried_docs
        assert len(report.entities) == 3
        assert len(report.comparison[0].values) == 3


def test_similarity_and_difference_identification():
    """Verify similarity and difference lists are properly extracted and populated."""
    engine = ResearchComparisonEngine()
    report = engine.parse_response("query", MOCK_LLM_JSON)

    assert any("benchmark task X" in s for s in report.similarities)
    assert any("32GB VRAM" in d for d in report.differences)


def test_contradiction_detection():
    """Verify genuine contradictions are detected with both sides and evidence."""
    engine = ResearchComparisonEngine()
    report = engine.parse_response("query", MOCK_LLM_JSON)

    assert len(report.contradictions) == 1
    c = report.contradictions[0]
    assert c.document_a == "paper_a.pdf"
    assert c.document_b == "paper_b.pdf"
    assert "Autoregressive modeling" in c.claim_a
    assert "Bidirectional conditioning" in c.claim_b
    assert "doc_a_c1" in c.evidence_chunks
    assert "doc_b_c1" in c.evidence_chunks


def test_missing_info_not_treated_as_contradiction():
    """Verify missing values are handled transparently as NOT_REPORTED without fabricating contradictions."""
    mock_json = json.dumps({
        "entities": ["doc_1.pdf", "doc_2.pdf"],
        "summary": "Comparison with partial reporting.",
        "similarities": ["Both study text models."],
        "differences": ["Evaluation metrics reported."],
        "comparison": [
            {
                "aspect": "F1 Score",
                "values": [
                    {"entity": "doc_1.pdf", "value": "91.2", "evidence": "Achieved 91.2 F1", "document": "doc_1.pdf", "page": 2, "chunk_id": "c1"},
                    {"entity": "doc_2.pdf", "value": "NOT_REPORTED", "evidence": "F1 score is not reported in doc_2.", "document": "doc_2.pdf", "page": 1, "chunk_id": "c2"}
                ]
            }
        ],
        "contradictions": [],
        "unique_contributions": [],
        "strengths_and_limitations": [],
        "synthesis": "F1 score is only reported by doc_1; no contradiction exists.",
        "sources": []
    })

    engine = ResearchComparisonEngine()
    report = engine.parse_response("query", mock_json)

    assert len(report.contradictions) == 0
    f1_aspect = report.comparison[0]
    doc2_val = [v for v in f1_aspect.values if v.entity == "doc_2.pdf"][0]
    assert doc2_val.value == "NOT_REPORTED"


def test_evidence_and_citation_attribution():
    """Verify citations point to the correct documents and chunk IDs."""
    engine = ResearchComparisonEngine()
    report = engine.parse_response("query", MOCK_LLM_JSON)

    for aspect in report.comparison:
        for val in aspect.values:
            assert val.chunk_id != ""
            assert val.document != ""
            assert val.evidence != ""


def test_missing_evidence_and_uncertainty_handling():
    """When retrieval returns no chunks, compare_research returns honest insufficient evidence report."""
    with patch.object(rag_service, "_search", return_value=[]):
        report = rag_service.compare_research("Nonexistent query topic", document_names=["empty_a.pdf", "empty_b.pdf"])

        assert "Not found in available sources" in report.summary
        assert "Not found in available sources" in report.synthesis
        assert len(report.comparison) == 0
        assert len(report.similarities) == 0
        assert len(report.contradictions) == 0


def test_duplicate_evidence_handling():
    """Verify duplicate chunks returned across targeted and general search are deduplicated."""
    duplicated_chunks = [
        {"chunk_id": "dup_c1", "document": "a.pdf", "page": 1, "text": "Repeated passage.", "hybrid_score": 0.9},
        {"chunk_id": "dup_c1", "document": "a.pdf", "page": 1, "text": "Repeated passage.", "hybrid_score": 0.9},
    ]

    with patch.object(rag_service, "_search", return_value=duplicated_chunks), \
         patch.object(rag_service.research_comparison, "build_comparison_prompt") as mock_prompt, \
         patch.object(rag_service.llm, "generate_structured") as mock_llm:
        mock_llm.return_value.success = True
        mock_llm.return_value.answer = MOCK_LLM_JSON

        rag_service.compare_research("Test duplicate handling", document_names=["a.pdf", "b.pdf"])

        # Check evidence passed to build_comparison_prompt
        call_args = mock_prompt.call_args[1]
        evidence_list = call_args["evidence"]
        chunk_ids = [e["chunk_id"] for e in evidence_list]
        assert chunk_ids.count("dup_c1") == 1


def test_provider_failure_and_fallback():
    """Verify provider failures gracefully fall back to evidence-based partial comparison."""
    fake_resp = MagicMock()
    fake_resp.success = False
    fake_resp.error = "Gemini quota exceeded"
    fake_resp.error_kind = "rate_limit"

    with patch.object(rag_service, "_search", return_value=SAMPLE_CHUNKS_DOC_A + SAMPLE_CHUNKS_DOC_B), \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp):
        report = rag_service.compare_research("Compare docs", document_names=["paper_a.pdf", "paper_b.pdf"])
        assert report.partial is True
        assert "Limited comparison" in report.summary
        assert len(report.comparison) > 0


def test_invalid_document_selection_endpoint():
    """Verify endpoint rejects invalid document counts (<2, >10, 0)."""
    # 1 document
    resp_one = client.post("/compare", json={"query": "Compare", "document_names": ["single.pdf"]})
    assert resp_one.status_code == 400
    assert "at least two documents" in resp_one.json()["detail"].lower()

    # 0 documents
    resp_zero = client.post("/compare", json={"query": "Compare", "document_names": []})
    assert resp_zero.status_code == 400
    assert "no documents" in resp_zero.json()["detail"].lower()

    # 11 documents
    resp_eleven = client.post("/compare", json={"query": "Compare", "document_names": [f"doc_{i}.pdf" for i in range(11)]})
    assert resp_eleven.status_code == 400
    assert "10 documents" in resp_eleven.json()["detail"].lower()


def test_api_response_compatibility():
    """Verify POST /compare response is fully backwards compatible and includes new fields."""
    fake_resp = MagicMock()
    fake_resp.success = True
    fake_resp.answer = MOCK_LLM_JSON

    with patch.object(rag_service, "_search", return_value=SAMPLE_CHUNKS_DOC_A + SAMPLE_CHUNKS_DOC_B), \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp):
        response = client.post(
            "/compare",
            json={"query": "Compare Paper A and Paper B", "document_names": ["paper_a.pdf", "paper_b.pdf"]}
        )

        assert response.status_code == 200
        data = response.json()

        # Contract requirements
        assert "query" in data
        assert "entities" in data
        assert "comparison" in data
        assert "summary" in data
        assert "sources" in data
        # Extended COMPARE fields
        assert "similarities" in data
        assert "differences" in data
        assert "contradictions" in data
        assert "unique_contributions" in data
        assert "strengths_and_limitations" in data
        assert "synthesis" in data
        assert "comparison_table" in data


def test_compare_retrieval_optimization_and_deduplication():
    """Verify optimized retrieval fetches scoped candidates and deduplicates repeated texts."""
    fake_resp = MagicMock()
    fake_resp.success = True
    fake_resp.answer = MOCK_LLM_JSON

    chunk_dup1 = {
        "chunk_id": "c_dup1",
        "document": "paper_a.pdf",
        "page": 1,
        "text": "Repeated text paragraph for deduplication testing.",
        "rank": 1,
        "hybrid_score": 0.95,
    }
    chunk_dup2 = {
        "chunk_id": "c_dup2",
        "document": "paper_a.pdf",
        "page": 2,
        "text": "Repeated text paragraph for deduplication testing.",
        "rank": 2,
        "hybrid_score": 0.85,
    }
    chunk_b = {
        "chunk_id": "c_b1",
        "document": "paper_b.pdf",
        "page": 1,
        "text": "Paper B distinct text paragraph.",
        "rank": 1,
        "hybrid_score": 0.90,
    }

    with patch.object(rag_service, "_search", return_value=[chunk_dup1, chunk_dup2, chunk_b]) as mock_search, \
         patch.object(rag_service.llm, "generate_structured", return_value=fake_resp), \
         patch.object(rag_service.research_comparison, "build_comparison_prompt", wraps=rag_service.research_comparison.build_comparison_prompt) as mock_prompt:

        report = rag_service.compare_research("Compare docs", document_names=["paper_a.pdf", "paper_b.pdf"])

        call_args = mock_prompt.call_args[1]
        ev_texts = [e["text"] for e in call_args["evidence"]]
        assert ev_texts.count("Repeated text paragraph for deduplication testing.") == 1
        assert "Paper B distinct text paragraph." in ev_texts

def test_compare_prompt_size_within_groq_budget():
    """Verify that generated comparison prompt stays strictly below Groq 8k TPM budget."""
    chunks = []
    # 4 documents with 4 chunks each
    for doc_idx in range(1, 5):
        doc_name = f"doc_{doc_idx}.pdf"
        for c_idx in range(1, 5):
            chunks.append({
                "chunk_id": f"c_{doc_idx}_{c_idx}",
                "document": doc_name,
                "page": c_idx,
                "text": f"This is detailed research findings from {doc_name} section {c_idx} describing experimental benchmarks, numerical metrics, and technical limitations in depth. " * 10,
                "rank": c_idx,
                "hybrid_score": 0.9 - (c_idx * 0.05),
            })

    fake_resp = MagicMock()
    fake_resp.success = True
    fake_resp.answer = MOCK_LLM_JSON

    with patch.object(rag_service, "_search", return_value=chunks),          patch.object(rag_service.llm, "generate_structured", return_value=fake_resp) as mock_gen:
        rag_service.compare_research("Compare all 4 documents", document_names=[f"doc_{i}.pdf" for i in range(1, 5)])

        sent_prompt = mock_gen.call_args[0][0]
        word_count = len(sent_prompt.split())
        assert word_count <= 3500, f"Prompt word count {word_count} exceeds safe 8k TPM budget margin"


def test_gemini_daily_quota_exhaustion_benched_and_skipped():
    """Verify daily quota exhaustion (429 / RESOURCE_EXHAUSTED per day) benches Gemini for 1800s."""
    from app.llm.base_provider import LLMResponse, ErrorKind
    from app.llm.health import HealthTracker, HealthPolicy

    tracker = HealthTracker(policy=HealthPolicy())

    gemini_daily_exhausted = LLMResponse(
        answer="",
        provider="gemini",
        model="gemini-3.6-flash",
        latency_ms=120.0,
        success=False,
        error="APIError: 429 Resource has been exhausted (e.g. check quota). Quota exceeded for quota metric 'Generate Content API requests per day'",
        error_kind=ErrorKind.FATAL,
    )

    tracker.record(gemini_daily_exhausted)

    rem_s = tracker.seconds_until_available("gemini")
    assert rem_s > 1000.0, f"Expected long cooldown for daily quota exhaustion, got {rem_s}s"
    assert not tracker.is_available("gemini")


def test_groq_413_payload_compaction_and_retry():
    """Verify Groq 413 / rate limit exceeded triggers compaction and allows retry."""
    from app.llm.orchestrator import LLMOrchestrator
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind

    class MockGroqProvider(BaseProvider):
        provider_name = "groq"
        def __init__(self):
            super().__init__("groq-model")
            self.attempts = []

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            self.attempts.append(prompt)
            if len(self.attempts) == 1:
                return LLMResponse(
                    answer="",
                    provider="groq",
                    model="groq-model",
                    latency_ms=50.0,
                    success=False,
                    error="Error 413: rate_limit_exceeded: 12005 tokens requested against 8000 TPM limit",
                    error_kind=ErrorKind.PAYLOAD_TOO_LARGE,
                )
            return LLMResponse(
                answer=MOCK_LLM_JSON,
                provider="groq",
                model="groq-model",
                latency_ms=50.0,
                success=True,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    mock_groq = MockGroqProvider()
    orch = LLMOrchestrator(providers=[mock_groq])

    oversized_prompt = "USER QUERY: Compare\nDOCUMENT EVIDENCE CATALOG:\n" + ("Sample evidence line.\n" * 500) + "STRICT RULES:\nFollow rules."
    resp = orch.generate_structured(oversized_prompt)

    assert resp.success
    assert len(mock_groq.attempts) == 2
    assert len(mock_groq.attempts[1]) < len(mock_groq.attempts[0])


def test_openrouter_finish_reason_length_and_fallback():
    """Verify finish_reason=length with incomplete JSON is rejected and falls back to next provider."""
    from app.llm.orchestrator import LLMOrchestrator
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind
    from app.llm.openrouter_provider import OpenRouterProvider
    import openai
    import httpx

    trunc_body = {
        "id": "gen-1",
        "object": "chat.completion",
        "created": 0,
        "model": "openrouter-model",
        "choices": [{
            "index": 0,
            "finish_reason": "length",
            "message": {
                "role": "assistant",
                "content": '{"entities": ["Paper A"], "summary": "Truncated comparison that was cut',
            },
        }],
    }

    with patch("app.llm.openrouter_provider.settings") as mock_settings:
        mock_settings.OPENROUTER_MODEL = "openrouter-model"
        mock_settings.OPENROUTER_API_KEY = "mock-key"
        mock_settings.LLM_TIMEOUT_S = 10.0
        mock_settings.TEMPERATURE = 0.0
        mock_settings.MAX_OUTPUT_TOKENS = 1000
        p_openrouter = OpenRouterProvider()

    p_openrouter.client = openai.OpenAI(
        api_key="mock",
        base_url="http://mock-or/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=trunc_body))),
    )

    # 1. Direct call to openrouter provider returns failure with PAYLOAD_TOO_LARGE because JSON is cut off
    direct_resp = p_openrouter.generate_structured("Compare papers")
    assert not direct_resp.success
    assert direct_resp.error_kind is ErrorKind.PAYLOAD_TOO_LARGE

    # 2. In orchestrator, when openrouter gets finish_reason=length with truncated JSON, it falls back
    class FallbackCloudflareProvider(BaseProvider):
        provider_name = "cloudflare"
        def __init__(self):
            super().__init__("cf-model")

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            return LLMResponse(
                answer=MOCK_LLM_JSON,
                provider="cloudflare",
                model="cf-model",
                latency_ms=150.0,
                success=True,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    p2 = FallbackCloudflareProvider()
    orch = LLMOrchestrator(providers=[p_openrouter, p2])

    resp = orch.generate_structured("Compare papers")
    assert resp.success
    assert resp.provider == "cloudflare"


def test_cohere_and_cloudflare_timeout_fallback():
    """Verify Cohere ReadTimeout and Cloudflare timeout trigger fast fallback."""
    from app.llm.orchestrator import LLMOrchestrator
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind

    class TimingOutCohereProvider(BaseProvider):
        provider_name = "cohere"
        def __init__(self):
            super().__init__("command-r")

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            return LLMResponse(
                answer="",
                provider="cohere",
                model="command-r",
                latency_ms=10000.0,
                success=False,
                error="ReadTimeout: Request timed out after 10.0s",
                error_kind=ErrorKind.TRANSIENT,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    class WorkingOpenRouterProvider(BaseProvider):
        provider_name = "openrouter"
        def __init__(self):
            super().__init__("or-model")

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            return LLMResponse(
                answer=MOCK_LLM_JSON,
                provider="openrouter",
                model="or-model",
                latency_ms=250.0,
                success=True,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    cohere_p = TimingOutCohereProvider()
    or_p = WorkingOpenRouterProvider()
    orch = LLMOrchestrator(providers=[cohere_p, or_p])

    resp = orch.generate_structured("Compare methods")
    assert resp.success
    assert resp.provider == "openrouter"



def test_groq_tpm_failure_no_repeated_retry():
    """Verify Groq does not repeatedly retry after TPM limit failure."""
    from app.llm.orchestrator import LLMOrchestrator
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind

    class MockGroqProvider(BaseProvider):
        provider_name = "groq"
        def __init__(self):
            super().__init__("groq-model")
            self.calls = 0

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            self.calls += 1
            return LLMResponse(
                answer="",
                provider="groq",
                model="groq-model",
                latency_ms=100.0,
                success=False,
                error="Rate limit reached for model on tokens per minute (TPM). Limit: 8000, Requested: 8200.",
                error_kind=ErrorKind.PAYLOAD_TOO_LARGE,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    class FallbackProvider(BaseProvider):
        provider_name = "fallback"
        def __init__(self):
            super().__init__("fb-model")
            self.calls = 0

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            self.calls += 1
            return LLMResponse(
                answer=MOCK_LLM_JSON,
                provider="fallback",
                model="fb-model",
                latency_ms=120.0,
                success=True,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    groq = MockGroqProvider()
    fallback = FallbackProvider()
    orch = LLMOrchestrator(providers=[groq, fallback])

    resp = orch.generate_structured("Compare papers", max_attempts=2)
    assert resp.success
    assert resp.provider == "fallback"
    assert groq.calls == 1  # No repeated retry on groq after TPM failure
    assert fallback.calls == 1


def test_max_provider_attempt_limit():
    """Verify structured generation strictly obeys max_attempts limit."""
    from app.llm.orchestrator import LLMOrchestrator
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind

    class CountingFailingProvider(BaseProvider):
        def __init__(self, name: str):
            super().__init__(f"{name}-model")
            self.provider_name = name
            self.calls = 0

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            self.calls += 1
            return LLMResponse(
                answer="",
                provider=self.provider_name,
                model=f"{self.provider_name}-model",
                latency_ms=50.0,
                success=False,
                error="Provider failure",
                error_kind=ErrorKind.TRANSIENT,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    p1 = CountingFailingProvider("p1")
    p2 = CountingFailingProvider("p2")
    p3 = CountingFailingProvider("p3")
    p4 = CountingFailingProvider("p4")

    orch = LLMOrchestrator(providers=[p1, p2, p3, p4])
    resp = orch.generate_structured("Compare papers", max_attempts=2)

    assert not resp.success
    assert p1.calls == 1
    assert p2.calls == 1
    assert p3.calls == 0  # Not attempted because max_attempts was 2
    assert p4.calls == 0


def test_llm_failure_with_evidence_returns_partial_comparison():
    """Verify when all LLM providers fail, compare_research returns an evidence-based partial comparison."""
    from app.main import rag_service
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind
    from unittest.mock import patch

    class AllFailingProvider(BaseProvider):
        provider_name = "failing"
        def __init__(self):
            super().__init__("failing-model")

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            return LLMResponse(
                answer="",
                provider="failing",
                model="failing-model",
                latency_ms=100.0,
                success=False,
                error="All LLM free tiers exhausted (429 Rate limit)",
                error_kind=ErrorKind.RATE_LIMIT,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    original_llm = rag_service.llm
    try:
        from app.llm.orchestrator import LLMOrchestrator
        rag_service.llm = LLMOrchestrator(providers=[AllFailingProvider()])

        with patch.object(rag_service, "_search", return_value=SAMPLE_CHUNKS_DOC_A + SAMPLE_CHUNKS_DOC_B):
            report = rag_service.compare_research(
                "Compare encoding density and error rates",
                document_names=["Paper_A.pdf", "Paper_B.pdf"],
            )

        assert report.partial is True
        assert report.notice is not None
        assert "Limited comparison" in report.notice
        assert "Limited comparison" in report.summary
        assert len(report.comparison) > 0
        assert report.contradictions == []  # No fabricated contradictions
        assert report.sources != []
    finally:
        rag_service.llm = original_llm


def test_no_llm_citations_and_attribution_correct():
    """Verify no-LLM comparison accurately attributes chunks, documents, and pages."""
    from app.rag.research_comparison import ResearchComparisonEngine

    engine = ResearchComparisonEngine()
    mock_evidence = [
        {
            "chunk_id": "docA_c1",
            "document": "Document_A.pdf",
            "page": 3,
            "text": "Document A employs a high density Reed-Solomon encoding codec achieving 1.8 bits per nucleotide.",
        },
        {
            "chunk_id": "docB_c1",
            "document": "Document_B.pdf",
            "page": 7,
            "text": "Document B utilizes an enzymatic synthesis approach with Illumina sequencing for error readout.",
        },
    ]

    report = engine.build_no_llm_comparison(
        query="Compare encoding and synthesis",
        evidence=mock_evidence,
        document_names=["Document_A.pdf", "Document_B.pdf"],
    )

    assert report.partial is True
    assert report.entities == ["Document_A.pdf", "Document_B.pdf"]
    
    # Check that comparison values cite the correct chunk_id and document
    found_encoding = False
    for aspect in report.comparison:
        for val in aspect.values:
            if val.document == "Document_A.pdf" and val.value != "Insufficient evidence in retrieved sources.":
                assert val.chunk_id == "docA_c1"
                assert val.page == 3
                found_encoding = True

    assert found_encoding


def test_no_llm_no_fabricated_similarities_or_contradictions():
    """Verify no-LLM comparison never invents false contradictions or unsupported similarities."""
    from app.rag.research_comparison import ResearchComparisonEngine

    engine = ResearchComparisonEngine()
    mock_evidence = [
        {
            "chunk_id": "c1",
            "document": "Doc_X.pdf",
            "page": 1,
            "text": "Quantum computer architecture using superconducting qubits operating at 15 millikelvin.",
        },
        {
            "chunk_id": "c2",
            "document": "Doc_Y.pdf",
            "page": 2,
            "text": "Marine biology analysis of benthic coral reefs in tropical ocean temperatures.",
        },
    ]

    report = engine.build_no_llm_comparison(
        query="Compare quantum computing and marine biology",
        evidence=mock_evidence,
        document_names=["Doc_X.pdf", "Doc_Y.pdf"],
    )

    # Completely different topics: contradictions must be empty
    assert report.contradictions == []
    # Similarities should state no explicit shared methodologies
    assert any("No explicit shared methodologies" in s for s in report.similarities)


def test_compare_endpoint_returns_200_partial_on_llm_exhaustion():
    """Verify FastAPI /compare endpoint returns HTTP 200 with partial=True and does not 500."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.main import rag_service
    from app.llm.base_provider import BaseProvider, LLMResponse, ErrorKind
    from app.llm.orchestrator import LLMOrchestrator

    class ExhaustedLLMProvider(BaseProvider):
        provider_name = "exhausted"
        def __init__(self):
            super().__init__("exhausted-model")

        def generate_structured(self, prompt: str, system: str | None = None) -> LLMResponse:
            return LLMResponse(
                answer="",
                provider="exhausted",
                model="exhausted-model",
                latency_ms=50.0,
                success=False,
                error="Rate limit exceeded (TPM)",
                error_kind=ErrorKind.RATE_LIMIT,
            )

        def _call(self, prompt: str, system: str | None = None) -> str:
            return ""

    client = TestClient(app)
    orig_llm = rag_service.llm
    try:
        rag_service.llm = LLMOrchestrator(providers=[ExhaustedLLMProvider()])
        resp = client.post(
            "/compare",
            json={
                "query": "Compare encoding density and error rates",
                "document_names": ["acsnano.2c06748.pdf", "UNKNOWN_RAG_Test_Document.pdf"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("partial") is True
        assert data.get("notice") is not None
        assert "Limited comparison" in data["notice"]
        assert "Limited comparison" in data["summary"]
        assert isinstance(data.get("comparison"), list)
        assert len(data["comparison"]) > 0
    finally:
        rag_service.llm = orig_llm
