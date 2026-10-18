"""Universal, data-agnostic validation contract for UNKNOWN."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


VALIDATION_CHECKS = (
    "input_schema",
    "metadata_completeness",
    "content_quality",
    "evidence_traceability",
    "semantic_relevance",
    "concept_consistency",
    "relationship_integrity",
    "contradiction_detection",
    "unsupported_claims",
    "confidence_calibration",
    "overall_quality",
)


@dataclass
class ValidationCheck:
    """Result of one validation check."""

    name: str
    status: CheckStatus
    message: str = ""
    score: float | None = None
    evidence: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.name not in VALIDATION_CHECKS:
            raise ValueError(f"Unknown validation check: {self.name}")

        if not isinstance(self.status, CheckStatus):
            try:
                self.status = CheckStatus(self.status)
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid validation status: {self.status}") from error

        if self.score is not None:
            if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
                raise TypeError("Validation score must be numeric or None.")

            if not 0 <= self.score <= 100:
                raise ValueError("Validation score must be between 0 and 100.")

        if not isinstance(self.evidence, list):
            raise TypeError("Validation evidence must be a list.")

        if not isinstance(self.details, dict):
            raise TypeError("Validation details must be a dictionary.")


@dataclass
class ValidationReport:
    """Portable validation report for documents and knowledge objects."""

    input_type: str
    checks: list[ValidationCheck] = field(default_factory=list)
    version: str = "1.0"

    def add_check(self, check: ValidationCheck) -> None:
        """Add one result, preventing duplicate check names."""

        if not isinstance(check, ValidationCheck):
            raise TypeError("check must be a ValidationCheck instance.")

        if any(existing.name == check.name for existing in self.checks):
            raise ValueError(f"Duplicate validation check: {check.name}")

        self.checks.append(check)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report into JSON-compatible primitives."""

        results = [asdict(check) for check in self.checks]

        for result in results:
            result["status"] = result["status"].value

        underlying_checks = {
            name for name in VALIDATION_CHECKS if name != "overall_quality"
        }
        reported_names = {check.name for check in self.checks}

        all_checks_reported = underlying_checks.issubset(reported_names)

        eligible_statuses = {
            CheckStatus.PASSED,
            CheckStatus.WARNING,
            CheckStatus.FAILED,
        }

        underlying_results = [
            check for check in self.checks if check.name != "overall_quality"
        ]

        scored = [
            check.score
            for check in underlying_results
            if check.score is not None and check.status in eligible_statuses
        ]

        applicable = [
            check
            for check in underlying_results
            if check.status
            not in (
                CheckStatus.NOT_APPLICABLE,
                CheckStatus.UNAVAILABLE,
                CheckStatus.ERROR,
            )
        ]

        overall_score_complete = (
            all_checks_reported
            and len(underlying_results) == len(underlying_checks)
            and len(scored) == len(underlying_checks)
        )

        overall_score = (
            round(sum(scored) / len(underlying_checks), 2)
            if overall_score_complete
            else None
        )

        return {
            "version": self.version,
            "input_type": self.input_type,
            "checks": results,
            "summary": {
                "checks_reported": len(self.checks),
                "checks_applicable": len(applicable),
                "checks_passed": sum(
                    c.status == CheckStatus.PASSED for c in self.checks
                ),
                "checks_failed": sum(
                    c.status == CheckStatus.FAILED for c in self.checks
                ),
                "checks_unavailable": sum(
                    c.status
                    in (
                        CheckStatus.UNAVAILABLE,
                        CheckStatus.ERROR,
                    )
                    for c in self.checks
                ),
                "overall_score": overall_score,
                "overall_score_complete": overall_score_complete,
                "checks_remaining": [
                    name
                    for name in VALIDATION_CHECKS
                    if name != "overall_quality" and name not in reported_names
                ],
            },
        }


# ==========================================================
# Universal validation checks — Phase 1
# ==========================================================


def validate_input_schema(data: Any) -> ValidationCheck:
    """Validate basic input structure without assuming a document domain."""

    if data is None:
        return ValidationCheck(
            name="input_schema",
            status=CheckStatus.FAILED,
            score=0,
            message="Input is missing.",
        )

    if isinstance(data, str):
        if not data.strip():
            return ValidationCheck(
                name="input_schema",
                status=CheckStatus.FAILED,
                score=0,
                message="Input text is empty.",
            )
        return ValidationCheck(
            name="input_schema",
            status=CheckStatus.PASSED,
            score=100,
            message="Non-empty text input.",
        )

    if isinstance(data, dict):
        if not data:
            return ValidationCheck(
                name="input_schema",
                status=CheckStatus.FAILED,
                score=0,
                message="Input object is empty.",
            )
        return ValidationCheck(
            name="input_schema",
            status=CheckStatus.PASSED,
            score=100,
            message="Input object is structurally valid.",
        )

    if isinstance(data, (list, tuple)):
        if not data:
            return ValidationCheck(
                name="input_schema",
                status=CheckStatus.FAILED,
                score=0,
                message="Input collection is empty.",
            )
        return ValidationCheck(
            name="input_schema",
            status=CheckStatus.PASSED,
            score=100,
            message="Input collection is structurally valid.",
        )

    return ValidationCheck(
        name="input_schema",
        status=CheckStatus.PASSED,
        score=100,
        message=f"Input type {type(data).__name__} is present.",
    )


def validate_metadata_completeness(
    metadata: dict[str, Any],
    required_fields: tuple[str, ...] = (),
) -> ValidationCheck:
    """Measure supplied metadata fields without imposing a domain schema."""

    if not isinstance(metadata, dict):
        return ValidationCheck(
            name="metadata_completeness",
            status=CheckStatus.FAILED,
            score=0,
            message="Metadata must be a dictionary.",
        )

    if not metadata:
        return ValidationCheck(
            name="metadata_completeness",
            status=CheckStatus.UNAVAILABLE,
            message="No metadata was supplied.",
        )

    fields = required_fields or tuple(metadata.keys())

    if not fields:
        return ValidationCheck(
            name="metadata_completeness",
            status=CheckStatus.UNAVAILABLE,
            message="No metadata fields can be evaluated.",
        )

    missing = [
        key
        for key in fields
        if key not in metadata
        or metadata[key] is None
        or (isinstance(metadata[key], str) and not metadata[key].strip())
    ]

    score = round(100 * (len(fields) - len(missing)) / len(fields), 2)

    return ValidationCheck(
        name="metadata_completeness",
        status=CheckStatus.PASSED if not missing else CheckStatus.WARNING,
        score=score,
        message=(
            "All evaluated metadata fields are present."
            if not missing
            else f"{len(missing)} metadata field(s) are missing or empty."
        ),
        evidence=missing,
        details={
            "evaluated_fields": list(fields),
            "missing_fields": missing,
            "present_count": len(fields) - len(missing),
            "field_count": len(fields),
        },
    )


def validate_content_quality(content: Any) -> ValidationCheck:
    """Check basic content availability and text usability."""

    if not isinstance(content, str):
        return ValidationCheck(
            name="content_quality",
            status=CheckStatus.UNAVAILABLE,
            message="Content must be supplied as extracted text.",
            details={"received_type": type(content).__name__},
        )

    text = content.strip()

    if not text:
        return ValidationCheck(
            name="content_quality",
            status=CheckStatus.FAILED,
            score=0,
            message="Content is empty.",
        )

    words = text.split()
    replacement_chars = text.count("\ufffd")
    control_chars = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")

    total_chars = max(len(text), 1)
    corruption_ratio = min(
        1.0,
        (replacement_chars + control_chars) / total_chars,
    )

    score = round(100 * (1 - corruption_ratio), 2)

    return ValidationCheck(
        name="content_quality",
        status=(
            CheckStatus.WARNING
            if replacement_chars or control_chars
            else CheckStatus.PASSED
        ),
        score=score,
        message=(
            "Content contains text."
            if score == 100
            else ("Potential text-extraction corruption detected.")
        ),
        details={
            "character_count": len(text),
            "word_count": len(words),
            "replacement_character_count": replacement_chars,
            "control_character_count": control_chars,
        },
    )


def validate_basic_input(
    input_type: str,
    data: Any,
    metadata: dict[str, Any] | None = None,
    content: str | None = None,
) -> ValidationReport:
    """Run the available foundational checks and return one report."""

    report = ValidationReport(input_type=input_type)

    report.add_check(validate_input_schema(data))

    if metadata is None:
        report.add_check(
            ValidationCheck(
                name="metadata_completeness",
                status=CheckStatus.UNAVAILABLE,
                message="Metadata was not supplied.",
            )
        )
    else:
        report.add_check(validate_metadata_completeness(metadata))

    if content is None:
        report.add_check(
            ValidationCheck(
                name="content_quality",
                status=CheckStatus.UNAVAILABLE,
                message="Extracted content was not supplied.",
            )
        )
    else:
        report.add_check(validate_content_quality(content))

    return report


def validate_evidence_traceability(
    evidence: list[dict[str, Any]] | None,
    cited_chunk_ids: list[str] | None = None,
) -> ValidationCheck:
    """Check whether cited chunk IDs resolve to supplied evidence."""

    if evidence is None:
        return ValidationCheck(
            name="evidence_traceability",
            status=CheckStatus.UNAVAILABLE,
            message="Evidence was not supplied.",
        )

    if not isinstance(evidence, list):
        return ValidationCheck(
            name="evidence_traceability",
            status=CheckStatus.FAILED,
            score=0,
            message="Evidence must be a list of objects.",
        )

    if any(not isinstance(item, dict) for item in evidence):
        return ValidationCheck(
            name="evidence_traceability",
            status=CheckStatus.FAILED,
            score=0,
            message="Every evidence entry must be an object.",
        )

    if not evidence:
        if cited_chunk_ids:
            return ValidationCheck(
                name="evidence_traceability",
                status=CheckStatus.FAILED,
                score=0,
                message="Citations were supplied but evidence is empty.",
                evidence=[str(item) for item in cited_chunk_ids],
            )

        return ValidationCheck(
            name="evidence_traceability",
            status=CheckStatus.UNAVAILABLE,
            message="No evidence or citations were supplied.",
        )

    available_ids = {
        str(item.get("chunk_id", "")).strip()
        for item in evidence
        if item.get("chunk_id") not in (None, "")
        and str(item.get("chunk_id")).strip().lower() != "unknown"
    }

    malformed_entries = [
        index
        for index, item in enumerate(evidence)
        if not str(item.get("chunk_id", "")).strip()
        or str(item.get("chunk_id", "")).strip().lower() == "unknown"
        or not str(item.get("document", "")).strip()
        or str(item.get("document", "")).strip().lower() == "unknown document"
    ]

    citations = cited_chunk_ids or []

    if not isinstance(citations, list):
        return ValidationCheck(
            name="evidence_traceability",
            status=CheckStatus.FAILED,
            score=0,
            message="Cited chunk IDs must be supplied as a list.",
        )

    cited_ids = [str(item).strip() for item in citations]
    missing_ids = sorted(set(cited_ids) - available_ids)

    if not citations:
        # Evidence exists, but there are no citations to resolve.
        status = CheckStatus.WARNING if malformed_entries else CheckStatus.PASSED
        score = 0 if malformed_entries else 100
        message = (
            "Evidence entries have incomplete source identifiers."
            if malformed_entries
            else "Evidence entries have source identifiers; no explicit citations to resolve."
        )
    else:
        valid_count = sum(1 for chunk_id in cited_ids if chunk_id in available_ids)
        score = round(100 * valid_count / len(cited_ids), 2)

        if missing_ids or malformed_entries:
            status = CheckStatus.FAILED
            message = "Some citations or evidence entries cannot be traced."
        else:
            status = CheckStatus.PASSED
            message = "All cited chunk IDs resolve to supplied evidence."

    return ValidationCheck(
        name="evidence_traceability",
        status=status,
        score=score,
        message=message,
        evidence=missing_ids,
        details={
            "available_chunk_count": len(available_ids),
            "citation_count": len(cited_ids),
            "unresolved_chunk_ids": missing_ids,
            "malformed_evidence_indexes": malformed_entries,
        },
    )


def validate_semantic_relevance(
    query: str | None,
    evidence: list[dict[str, Any]] | None,
    minimum_score: float = 0.2,
) -> ValidationCheck:
    """Evaluate retrieval relevance using UNKNOWN hybrid retrieval signals.

    Hybrid scores are ranking signals, not relevance probabilities.
    This check evaluates supplied scores and does not independently
    prove semantic relevance.
    """

    if query is None or not query.strip():
        return ValidationCheck(
            name="semantic_relevance",
            status=CheckStatus.UNAVAILABLE,
            message="A non-empty query was not supplied.",
        )

    if evidence is None:
        return ValidationCheck(
            name="semantic_relevance",
            status=CheckStatus.UNAVAILABLE,
            message="Retrieved evidence was not supplied.",
        )

    if not isinstance(evidence, list):
        return ValidationCheck(
            name="semantic_relevance",
            status=CheckStatus.FAILED,
            score=0,
            message="Evidence must be a list.",
        )

    if not 0 <= minimum_score <= 1:
        raise ValueError("minimum_score must be between 0 and 1.")

    if not evidence:
        return ValidationCheck(
            name="semantic_relevance",
            status=CheckStatus.FAILED,
            score=0,
            message="No evidence was retrieved for the query.",
        )

    if any(not isinstance(item, dict) for item in evidence):
        return ValidationCheck(
            name="semantic_relevance",
            status=CheckStatus.FAILED,
            score=0,
            message="Every evidence entry must be an object.",
        )

    scored_items = []
    invalid_items = []

    for index, item in enumerate(evidence):
        raw_score = item.get("hybrid_score")

        # Support the canonical evidence schema's "score" field.
        if raw_score is None:
            raw_score = item.get("score")

        try:
            score = float(raw_score)  # type: ignore
        except (TypeError, ValueError):
            invalid_items.append(index)
            continue

        if not 0 <= score <= 1:
            invalid_items.append(index)
            continue

        scored_items.append((index, score))

    if not scored_items:
        return ValidationCheck(
            name="semantic_relevance",
            status=CheckStatus.UNAVAILABLE,
            message="No valid normalized hybrid scores were supplied.",
            details={"invalid_evidence_indexes": invalid_items},
        )

    relevant_items = [
        (index, score) for index, score in scored_items if score >= minimum_score
    ]

    relevance_ratio = len(relevant_items) / len(scored_items)
    score = round(relevance_ratio * 100, 2)

    if invalid_items:
        status = CheckStatus.WARNING
        message = "Some evidence scores were missing or outside [0, 1]."
    elif relevant_items:
        status = CheckStatus.PASSED
        message = "At least one result meets the configured score threshold."
    else:
        status = CheckStatus.FAILED
        message = "No result meets the configured score threshold."

    return ValidationCheck(
        name="semantic_relevance",
        status=status,
        score=score,
        message=message,
        evidence=[
            str(evidence[index].get("chunk_id", "unknown"))
            for index, _ in relevant_items
        ],
        details={
            "query": query,
            "minimum_score": minimum_score,
            "scored_result_count": len(scored_items),
            "relevant_result_count": len(relevant_items),
            "mean_hybrid_score": round(
                sum(value for _, value in scored_items) / len(scored_items),
                4,
            ),
            "invalid_evidence_indexes": invalid_items,
            "score_interpretation": (
                "Relative hybrid retrieval score; not a probability."
            ),
        },
    )


def validate_concept_consistency(
    concepts: list[dict[str, Any]] | None,
) -> ValidationCheck:
    """Validate concept records for basic structural consistency.

    This checks record shape, names, optional identifiers, and duplicates.
    It does not prove semantic correctness or detect contradictions.
    """

    if concepts is None:
        return ValidationCheck(
            name="concept_consistency",
            status=CheckStatus.UNAVAILABLE,
            message="Concept records were not supplied.",
        )

    if not isinstance(concepts, list):
        return ValidationCheck(
            name="concept_consistency",
            status=CheckStatus.FAILED,
            score=0,
            message="Concepts must be supplied as a list of objects.",
        )

    if not concepts:
        return ValidationCheck(
            name="concept_consistency",
            status=CheckStatus.UNAVAILABLE,
            message="No concepts were supplied for consistency checking.",
        )

    malformed_indexes = []
    duplicate_name_indexes = []
    duplicate_id_indexes = []
    seen_names = set()
    seen_ids = set()

    for index, concept in enumerate(concepts):
        if not isinstance(concept, dict):
            malformed_indexes.append(index)
            continue

        name = concept.get(
            "name",
            concept.get("concept", concept.get("label")),
        )
        if not isinstance(name, str) or not name.strip():
            malformed_indexes.append(index)
            continue

        normalized_name = " ".join(name.split()).casefold()
        if normalized_name in seen_names:
            duplicate_name_indexes.append(index)
        else:
            seen_names.add(normalized_name)

        identifier = concept.get("id", concept.get("concept_id"))
        if identifier is not None:
            if not isinstance(identifier, (str, int)) or isinstance(identifier, bool):
                malformed_indexes.append(index)
                continue

            normalized_id = str(identifier).strip().casefold()
            if not normalized_id:
                malformed_indexes.append(index)
            elif normalized_id in seen_ids:
                duplicate_id_indexes.append(index)
            else:
                seen_ids.add(normalized_id)

    issue_count = (
        len(malformed_indexes) + len(duplicate_name_indexes) + len(duplicate_id_indexes)
    )
    score = round(
        100 * (len(concepts) - min(issue_count, len(concepts))) / len(concepts), 2
    )

    if issue_count:
        status = CheckStatus.WARNING
        message = "Some concept records are malformed or duplicated."
    else:
        status = CheckStatus.PASSED
        message = "Concept records have valid names and no detected duplicates."

    return ValidationCheck(
        name="concept_consistency",
        status=status,
        score=score,
        message=message,
        evidence=[
            f"concept_index:{index}"
            for index in sorted(
                set(malformed_indexes + duplicate_name_indexes + duplicate_id_indexes)
            )
        ],
        details={
            "concept_count": len(concepts),
            "malformed_indexes": malformed_indexes,
            "duplicate_name_indexes": duplicate_name_indexes,
            "duplicate_id_indexes": duplicate_id_indexes,
            "semantic_consistency_verified": False,
        },
    )


def validate_relationship_integrity(
    nodes: list[dict[str, Any]] | None,
    relationships: list[dict[str, Any]] | None,
) -> ValidationCheck:
    """Check that relationship endpoints reference known node IDs.

    Supports the source/target schema used by UNKNOWN's knowledge
    mind maps and Knowledge DNA relationships.
    This checks structural integrity, not factual correctness.
    """

    if nodes is None or relationships is None:
        return ValidationCheck(
            name="relationship_integrity",
            status=CheckStatus.UNAVAILABLE,
            message="Both nodes and relationships must be supplied.",
        )

    if not isinstance(nodes, list) or not isinstance(relationships, list):
        return ValidationCheck(
            name="relationship_integrity",
            status=CheckStatus.FAILED,
            score=0,
            message="Nodes and relationships must both be lists.",
        )

    malformed_nodes = []
    seen_node_ids = set()
    duplicate_node_ids = []
    valid_node_ids = set()

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            malformed_nodes.append(index)
            continue

        node_id = node.get("id")
        if not isinstance(node_id, (str, int)) or isinstance(node_id, bool):
            malformed_nodes.append(index)
            continue

        normalized_id = str(node_id).strip()
        if not normalized_id:
            malformed_nodes.append(index)
            continue

        if normalized_id in seen_node_ids:
            duplicate_node_ids.append(index)
        else:
            seen_node_ids.add(normalized_id)
            valid_node_ids.add(normalized_id)

    if not nodes and relationships:
        return ValidationCheck(
            name="relationship_integrity",
            status=CheckStatus.FAILED,
            score=0,
            message="Relationships exist, but no nodes were supplied.",
            details={
                "relationship_count": len(relationships),
                "malformed_node_indexes": malformed_nodes,
                "duplicate_node_indexes": duplicate_node_ids,
            },
        )

    malformed_relationships = []
    unresolved_sources = []
    unresolved_targets = []
    self_references = []

    for index, relationship in enumerate(relationships):
        if not isinstance(relationship, dict):
            malformed_relationships.append(index)
            continue

        source = relationship.get("source")
        target = relationship.get("target")

        if source is None or target is None:
            malformed_relationships.append(index)
            continue

        source_id = str(source).strip()
        target_id = str(target).strip()

        if not source_id or not target_id:
            malformed_relationships.append(index)
            continue

        if source_id not in valid_node_ids:
            unresolved_sources.append(index)

        if target_id not in valid_node_ids:
            unresolved_targets.append(index)

        if source_id == target_id:
            self_references.append(index)

    issue_count = (
        len(malformed_nodes)
        + len(duplicate_node_ids)
        + len(malformed_relationships)
        + len(unresolved_sources)
        + len(unresolved_targets)
    )

    total = len(nodes) + len(relationships)
    score = (
        round(100 * (total - min(issue_count, total)) / total, 2) if total else 100.0
    )

    if issue_count:
        status = CheckStatus.FAILED
        message = "Some nodes or relationship endpoints are structurally invalid."
    else:
        status = CheckStatus.PASSED
        message = "All relationship endpoints reference known node IDs."

    affected_indexes = sorted(
        set(
            malformed_nodes
            + duplicate_node_ids
            + [
                len(nodes) + index
                for index in (
                    malformed_relationships + unresolved_sources + unresolved_targets
                )
            ]
        )
    )

    return ValidationCheck(
        name="relationship_integrity",
        status=status,
        score=score,
        message=message,
        evidence=[f"record_index:{index}" for index in affected_indexes],
        details={
            "node_count": len(nodes),
            "relationship_count": len(relationships),
            "malformed_node_indexes": malformed_nodes,
            "duplicate_node_indexes": duplicate_node_ids,
            "malformed_relationship_indexes": malformed_relationships,
            "unresolved_source_indexes": unresolved_sources,
            "unresolved_target_indexes": unresolved_targets,
            "self_reference_indexes": self_references,
            "structural_integrity_only": True,
        },
    )


def validate_contradictions(
    verification_results: list[dict[str, Any]] | None,
) -> ValidationCheck:
    """Summarize existing claim-verification verdicts.

    This check consumes verdicts produced by an existing verifier.
    It does not independently determine whether claims contradict
    one another or verify whether the supplied verdicts are correct.
    """

    if verification_results is None:
        return ValidationCheck(
            name="contradiction_detection",
            status=CheckStatus.UNAVAILABLE,
            message="Claim verification results were not supplied.",
        )

    if not isinstance(verification_results, list):
        return ValidationCheck(
            name="contradiction_detection",
            status=CheckStatus.FAILED,
            score=0,
            message="Verification results must be a list.",
        )

    if not verification_results:
        return ValidationCheck(
            name="contradiction_detection",
            status=CheckStatus.UNAVAILABLE,
            message="No claim verification results were supplied.",
        )

    allowed_verdicts = {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "CONTRADICTED",
        "NOT_FOUND",
    }

    invalid_indexes = []
    contradicted_indexes = []
    not_found_indexes = []
    partial_indexes = []
    supported_indexes = []

    for index, result in enumerate(verification_results):
        if not isinstance(result, dict):
            invalid_indexes.append(index)
            continue

        verdict = result.get("verdict")
        if hasattr(verdict, "value"):
            verdict = verdict.value  # type: ignore

        if not isinstance(verdict, str):
            invalid_indexes.append(index)
            continue

        verdict = verdict.strip().upper()

        if verdict not in allowed_verdicts:
            invalid_indexes.append(index)
        elif verdict == "CONTRADICTED":
            contradicted_indexes.append(index)
        elif verdict == "NOT_FOUND":
            not_found_indexes.append(index)
        elif verdict == "PARTIALLY_SUPPORTED":
            partial_indexes.append(index)
        else:
            supported_indexes.append(index)

    valid_count = len(verification_results) - len(invalid_indexes)

    if valid_count == 0:
        return ValidationCheck(
            name="contradiction_detection",
            status=CheckStatus.ERROR,
            message="No valid verification verdicts were supplied.",
            details={"invalid_result_indexes": invalid_indexes},
        )

    score = round(
        100 * (valid_count - len(contradicted_indexes)) / valid_count,
        2,
    )

    if invalid_indexes:
        status = CheckStatus.WARNING
        message = "Some verification results contain invalid verdicts."
    elif contradicted_indexes:
        status = CheckStatus.FAILED
        message = "The existing verifier marked one or more claims as contradicted."
    else:
        status = CheckStatus.PASSED
        message = "No supplied claim was marked contradicted by the existing verifier."

    return ValidationCheck(
        name="contradiction_detection",
        status=status,
        score=score,
        message=message,
        evidence=[
            str(
                verification_results[index].get(
                    "claim",
                    f"result_index:{index}",
                )
            )
            for index in contradicted_indexes
        ],
        details={
            "result_count": len(verification_results),
            "valid_result_count": valid_count,
            "contradicted_indexes": contradicted_indexes,
            "not_found_indexes": not_found_indexes,
            "partially_supported_indexes": partial_indexes,
            "supported_indexes": supported_indexes,
            "invalid_result_indexes": invalid_indexes,
            "detection_source": "existing_claim_verifier",
            "independently_verified": False,
        },
    )


def validate_unsupported_claims(
    verification_results: list[dict[str, Any]] | None,
) -> ValidationCheck:
    """Summarize existing claim-verification results for unsupported claims.

    This consumes ClaimVerifier verdicts. It does not independently
    verify claims or prove that NOT_FOUND claims are false.
    """

    if verification_results is None:
        return ValidationCheck(
            name="unsupported_claims",
            status=CheckStatus.UNAVAILABLE,
            message="Claim verification results were not supplied.",
        )

    if not isinstance(verification_results, list):
        return ValidationCheck(
            name="unsupported_claims",
            status=CheckStatus.FAILED,
            score=0,
            message="Verification results must be a list.",
        )

    if not verification_results:
        return ValidationCheck(
            name="unsupported_claims",
            status=CheckStatus.UNAVAILABLE,
            message="No claim verification results were supplied.",
        )

    allowed_verdicts = {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "CONTRADICTED",
        "NOT_FOUND",
    }

    invalid_indexes = []
    supported_indexes = []
    partial_indexes = []
    contradicted_indexes = []
    not_found_indexes = []

    for index, result in enumerate(verification_results):
        if not isinstance(result, dict):
            invalid_indexes.append(index)
            continue

        verdict = result.get("verdict")

        if hasattr(verdict, "value"):
            verdict = verdict.value  # type: ignore

        if not isinstance(verdict, str):
            invalid_indexes.append(index)
            continue

        verdict = verdict.strip().upper()

        if verdict not in allowed_verdicts:
            invalid_indexes.append(index)
        elif verdict == "SUPPORTED":
            supported_indexes.append(index)
        elif verdict == "PARTIALLY_SUPPORTED":
            partial_indexes.append(index)
        elif verdict == "CONTRADICTED":
            contradicted_indexes.append(index)
        else:
            not_found_indexes.append(index)

    valid_count = len(verification_results) - len(invalid_indexes)

    if valid_count == 0:
        return ValidationCheck(
            name="unsupported_claims",
            status=CheckStatus.ERROR,
            message="No valid claim-verification results were supplied.",
            details={
                "invalid_result_indexes": invalid_indexes,
                "independently_verified": False,
            },
        )

    # NOT_FOUND and PARTIALLY_SUPPORTED are flagged as insufficiently
    # supported. CONTRADICTED is reported separately, not conflated with
    # a lack of evidence.
    flagged_indexes = sorted(not_found_indexes + partial_indexes)
    score = round(
        100 * len(supported_indexes) / valid_count,
        2,
    )

    if invalid_indexes:
        status = CheckStatus.WARNING
        message = "Some verification results contain invalid verdicts."
    elif flagged_indexes or contradicted_indexes:
        status = CheckStatus.WARNING
        message = "Some claims lack full supporting evidence or were contradicted."
    else:
        status = CheckStatus.PASSED
        message = "All supplied claims were marked supported by the existing verifier."

    return ValidationCheck(
        name="unsupported_claims",
        status=status,
        score=score,
        message=message,
        evidence=[
            str(
                verification_results[index].get(
                    "claim",
                    f"result_index:{index}",
                )
            )
            for index in flagged_indexes + contradicted_indexes
        ],
        details={
            "result_count": len(verification_results),
            "valid_result_count": valid_count,
            "supported_indexes": supported_indexes,
            "partially_supported_indexes": partial_indexes,
            "not_found_indexes": not_found_indexes,
            "contradicted_indexes": contradicted_indexes,
            "flagged_insufficient_support_indexes": flagged_indexes,
            "invalid_result_indexes": invalid_indexes,
            "detection_source": "existing_claim_verifier",
            "independently_verified": False,
            "score_interpretation": (
                "Percentage of valid results marked SUPPORTED; "
                "not a calibrated probability or factual accuracy measure."
            ),
        },
    )


def validate_confidence_calibration(
    predictions: list[dict[str, Any]] | None,
    minimum_sample_size: int = 30,
    ece_threshold: float = 0.1,
    bin_count: int = 10,
) -> ValidationCheck:
    """Evaluate confidence against labeled binary outcomes.

    Each record must contain:
      - confidence: a numeric probability in [0, 1]
      - correct: a Boolean ground-truth outcome

    Brier score measures prediction error. ECE measures the gap between
    confidence and empirical accuracy across confidence bins. Neither
    metric alone proves that a model is universally calibrated.
    """

    if predictions is None or predictions == []:
        return ValidationCheck(
            name="confidence_calibration",
            status=CheckStatus.UNAVAILABLE,
            message="Labeled confidence predictions were not supplied.",
        )

    if not isinstance(predictions, list):
        return ValidationCheck(
            name="confidence_calibration",
            status=CheckStatus.FAILED,
            score=0,
            message="Predictions must be supplied as a list.",
        )

    if (
        isinstance(minimum_sample_size, bool)
        or not isinstance(minimum_sample_size, int)
        or minimum_sample_size < 1
    ):
        raise ValueError("minimum_sample_size must be a positive integer.")

    if isinstance(bin_count, bool) or not isinstance(bin_count, int) or bin_count < 1:
        raise ValueError("bin_count must be a positive integer.")

    if (
        isinstance(ece_threshold, bool)
        or not isinstance(ece_threshold, (int, float))
        or not 0 <= ece_threshold <= 1
    ):
        raise ValueError("ece_threshold must be between 0 and 1.")

    valid = []
    invalid_indexes = []

    for index, item in enumerate(predictions):
        if not isinstance(item, dict):
            invalid_indexes.append(index)
            continue

        confidence = item.get("confidence")
        correct = item.get("correct")

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
            or not isinstance(correct, bool)
        ):
            invalid_indexes.append(index)
            continue

        valid.append((float(confidence), int(correct)))

    if not valid:
        return ValidationCheck(
            name="confidence_calibration",
            status=CheckStatus.FAILED,
            score=0,
            message="No valid labeled confidence predictions were supplied.",
            details={
                "invalid_result_indexes": invalid_indexes,
                "valid_result_count": 0,
                "brier_score": None,
                "ece": None,
                "evaluation_basis": "labeled_ground_truth",
                "calibration_is_proven": False,
            },
        )

    count = len(valid)

    brier_score = (
        sum((confidence - outcome) ** 2 for confidence, outcome in valid) / count
    )

    bins = [
        {
            "count": 0,
            "confidence_sum": 0.0,
            "correct_sum": 0,
        }
        for _ in range(bin_count)
    ]

    for confidence, outcome in valid:
        # Confidence 1.0 belongs to the final bin.
        bin_index = min(int(confidence * bin_count), bin_count - 1)
        bins[bin_index]["count"] += 1
        bins[bin_index]["confidence_sum"] += confidence
        bins[bin_index]["correct_sum"] += outcome

    ece = 0.0
    bin_results = []

    for index, bucket in enumerate(bins):
        bucket_count = bucket["count"]

        if bucket_count == 0:
            continue

        mean_confidence = bucket["confidence_sum"] / bucket_count
        accuracy = bucket["correct_sum"] / bucket_count

        ece += (bucket_count / count) * abs(mean_confidence - accuracy)

        bin_results.append(
            {
                "bin_index": index,
                "count": bucket_count,
                "mean_confidence": round(mean_confidence, 6),
                "accuracy": round(accuracy, 6),
            }
        )

    brier_score = round(brier_score, 6)
    ece = round(ece, 6)

    if invalid_indexes:
        status = CheckStatus.WARNING
        message = "Some prediction records were invalid and excluded."
    elif count < minimum_sample_size:
        status = CheckStatus.WARNING
        message = "Insufficient labeled samples for a reliable calibration assessment."
    elif ece > ece_threshold:
        status = CheckStatus.WARNING
        message = "Observed calibration error exceeds the configured threshold."
    else:
        status = CheckStatus.PASSED
        message = (
            "Calibration metrics meet the configured threshold on this dataset; "
            "this does not establish universal calibration."
        )

    # Higher score means lower Brier error. This is a descriptive score,
    # not a probability of correctness or a calibration guarantee.
    quality_score = round(100 * (1 - brier_score), 2)

    return ValidationCheck(
        name="confidence_calibration",
        status=status,
        score=quality_score,
        message=message,
        details={
            "sample_count": len(predictions),
            "valid_result_count": count,
            "invalid_result_indexes": invalid_indexes,
            "brier_score": brier_score,
            "ece": ece,
            "ece_threshold": float(ece_threshold),
            "bin_count": bin_count,
            "bins": bin_results,
            "minimum_sample_size": minimum_sample_size,
            "evaluation_basis": "labeled_ground_truth",
            "calibration_is_proven": False,
            "score_interpretation": (
                "100 times one minus Brier score; descriptive prediction quality, "
                "not a probability or proof of calibration."
            ),
        },
    )
