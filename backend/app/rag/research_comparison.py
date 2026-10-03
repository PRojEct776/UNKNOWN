"""
UNKNOWN X - Research Comparison Engine

Compares research entities using only retrieved document evidence.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# MODELS
# ============================================================


class ComparisonValue(BaseModel):
    """Evidence-backed value for one entity and aspect."""

    entity: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    document: str = Field(..., min_length=1)
    page: int | str
    chunk_id: str = Field(..., min_length=1)


class ComparisonAspect(BaseModel):
    """Comparison across entities for one research aspect."""

    aspect: str = Field(..., min_length=1)
    values: list[ComparisonValue] = Field(default_factory=list)


class ResearchComparisonReport(BaseModel):
    """Complete research comparison report."""

    query: str
    entities: list[str] = Field(default_factory=list)
    comparison: list[ComparisonAspect] = Field(
        default_factory=list
    )
    summary: str = Field(..., min_length=1)
    sources: list[dict] = Field(default_factory=list)


# ============================================================
# ENGINE
# ============================================================


class ResearchComparisonEngine:
    """
    Build prompts and parse structured research
    comparison responses.
    """

    # ========================================================
    # PROMPT
    # ========================================================

    def build_comparison_prompt(
        self,
        query: str,
        evidence: list[dict],
    ) -> str:
        """
        Build a strict evidence-grounded comparison prompt.
        """

        evidence_blocks: list[str] = []

        for index, item in enumerate(
            evidence,
            start=1,
        ):
            evidence_blocks.append(
                f"""
EVIDENCE {index}

Document: {item.get("document", "")}
Page: {item.get("page", "")}
Chunk ID: {item.get("chunk_id", "")}

Text:
{item.get("text", "")}
""".strip()
            )

        evidence_text = "\n\n".join(
            evidence_blocks
        )

        return f"""
You are the Research Comparison Engine of UNKNOWN.

Your task is to compare research methods, systems,
papers, datasets, or approaches using ONLY the
supplied document evidence.

USER QUERY:
{query}

DOCUMENT EVIDENCE:
{evidence_text}

STRICT RULES:

1. Use ONLY the supplied evidence.
2. Do not use outside knowledge.
3. Do not invent entities.
4. Do not invent metrics.
5. Do not invent values.
6. Do not invent results.
7. Do not invent conclusions.
8. Every comparison value MUST be traceable to a supplied evidence chunk.
9. Every comparison value MUST contain non-empty evidence.
10. Preserve numerical values exactly as supported by the evidence.
11. If a requested value is not present in the supplied evidence,
    use "NOT_REPORTED".
12. Never estimate missing values.
13. Never calculate missing values.
14. Dataset-specific results must remain dataset-specific.
15. Never combine values from different datasets as though they
    were the same measurement.
16. Every value MUST contain document, page, and chunk_id.
17. The summary must contain only evidence-supported observations.
18. Do not declare an overall winner unless the evidence explicitly
    supports such a conclusion.
19. Return exactly ONE JSON object.
20. Return JSON only.

Identify the relevant comparison entities from the evidence.

Identify the comparison aspects requested by the user.

For each aspect, report the available value for each relevant entity.

If the evidence does not contain a requested value for an entity,
use:

"NOT_REPORTED"

For NOT_REPORTED values, still provide the evidence that shows the
available information is insufficient, when possible.

Every comparison value MUST contain:

- entity
- value
- evidence
- document
- page
- chunk_id

The evidence field MUST NOT be empty.

Return EXACTLY this structure:

{{
  "entities": [
    "Entity A",
    "Entity B"
  ],
  "comparison": [
    {{
      "aspect": "EM",
      "values": [
        {{
          "entity": "Entity A",
          "value": "0.595",
          "evidence": "Supporting passage from supplied evidence.",
          "document": "document.pdf",
          "page": 6,
          "chunk_id": "chunk_10"
        }},
        {{
          "entity": "Entity B",
          "value": "NOT_REPORTED",
          "evidence": "No EM value for Entity B is reported in the supplied evidence.",
          "document": "document.pdf",
          "page": 6,
          "chunk_id": "chunk_10"
        }}
      ]
    }}
  ],
  "summary": "Evidence-grounded comparison summary.",
  "sources": [
    {{
      "document": "document.pdf",
      "page": 6,
      "chunk_id": "chunk_10"
    }}
  ]
}}

FINAL OUTPUT REQUIREMENTS:

- Valid JSON only.
- No Markdown.
- No ```json fences.
- No introductory sentence.
- No concluding sentence.
- No single quotes.
- Use double quotes for JSON strings.
- Do not leave evidence empty.
- Do not invent source identifiers.
- Do not invent missing values.
- Use "NOT_REPORTED" for missing requested values.
- Return exactly one JSON object.
""".strip()

    # ========================================================
    # BALANCED JSON EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_balanced_json(
        text: str,
    ) -> str:
        """
        Extract the first complete JSON object.

        Handles:
        - nested objects
        - arrays
        - braces inside strings
        - escaped quotes
        """

        start = text.find("{")

        if start == -1:
            raise ValueError(
                "Provider returned no JSON object "
                "for research comparison."
            )

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):
            char = text[index]

            if in_string:

                if escaped:
                    escaped = False

                elif char == "\\":
                    escaped = True

                elif char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    return text[
                        start : index + 1
                    ]

        raise ValueError(
            "Provider returned incomplete "
            "research comparison JSON."
        )

    # ========================================================
    # JSON EXTRACTION
    # ========================================================

    @classmethod
    def _extract_json(
        cls,
        text: str,
    ) -> dict:
        """
        Extract JSON from an LLM response.

        Supports:
        - raw JSON
        - fenced JSON
        - JSON surrounded by text
        - nested JSON
        """

        if not isinstance(
            text,
            str,
        ):
            raise ValueError(
                "Provider returned a non-text "
                "research comparison response."
            )

        cleaned = text.strip()

        if not cleaned:
            raise ValueError(
                "Provider returned an empty "
                "research comparison response."
            )

        # ----------------------------------------------------
        # 1. Direct JSON
        # ----------------------------------------------------

        try:
            parsed = json.loads(cleaned)

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except json.JSONDecodeError:
            pass

        # ----------------------------------------------------
        # 2. Markdown fenced JSON
        # ----------------------------------------------------

        fenced_match = re.search(
            r"```(?:json)?\s*(.*?)\s*```",
            cleaned,
            flags=re.IGNORECASE
            | re.DOTALL,
        )

        if fenced_match:

            fenced_content = (
                fenced_match
                .group(1)
                .strip()
            )

            try:
                parsed = json.loads(
                    fenced_content
                )

                if isinstance(
                    parsed,
                    dict,
                ):
                    return parsed

            except json.JSONDecodeError:
                pass

            try:
                candidate = (
                    cls._extract_balanced_json(
                        fenced_content
                    )
                )

                parsed = json.loads(
                    candidate
                )

                if isinstance(
                    parsed,
                    dict,
                ):
                    return parsed

            except (
                ValueError,
                json.JSONDecodeError,
            ):
                pass

        # ----------------------------------------------------
        # 3. Embedded JSON
        # ----------------------------------------------------

        try:
            candidate = (
                cls._extract_balanced_json(
                    cleaned
                )
            )

            parsed = json.loads(
                candidate
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except (
            ValueError,
            json.JSONDecodeError,
        ):
            pass

        raise ValueError(
            "Provider returned invalid "
            "research comparison JSON."
        )

    # ========================================================
    # VALUE PARSER
    # ========================================================

    @staticmethod
    def _parse_value(
        data: dict,
    ) -> ComparisonValue:
        """
        Parse and validate one comparison value.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Comparison value must be a JSON object."
            )

        entity = str(
            data.get(
                "entity",
                "",
            )
        ).strip()

        value = str(
            data.get(
                "value",
                "",
            )
        ).strip()

        evidence = str(
            data.get(
                "evidence",
                "",
            )
        ).strip()

        document = str(
            data.get(
                "document",
                "",
            )
        ).strip()

        page = data.get(
            "page",
            "",
        )

        chunk_id = str(
            data.get(
                "chunk_id",
                "",
            )
        ).strip()

        if not entity:
            raise ValueError(
                "Comparison value is missing entity."
            )

        if not value:
            raise ValueError(
                "Comparison value is missing "
                f"value for entity: {entity}"
            )

        if not evidence:
            raise ValueError(
                "Comparison value contains "
                f"no evidence: {entity}"
            )

        if not document:
            raise ValueError(
                "Comparison value contains "
                f"no document: {entity}"
            )

        if not chunk_id:
            raise ValueError(
                "Comparison value contains "
                f"no chunk_id: {entity}"
            )

        return ComparisonValue(
            entity=entity,
            value=value,
            evidence=evidence,
            document=document,
            page=page,
            chunk_id=chunk_id,
        )

    # ========================================================
    # ASPECT PARSER
    # ========================================================

    @staticmethod
    def _parse_aspect(
        data: dict,
    ) -> ComparisonAspect:
        """
        Parse and validate one comparison aspect.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "Comparison aspect must be a JSON object."
            )

        aspect = str(
            data.get(
                "aspect",
                "",
            )
        ).strip()

        if not aspect:
            raise ValueError(
                "Comparison aspect is missing aspect name."
            )

        raw_values = data.get(
            "values",
            [],
        )

        if not isinstance(
            raw_values,
            list,
        ):
            raise ValueError(
                f"Comparison aspect '{aspect}' "
                "values must be a list."
            )

        values: list[ComparisonValue] = []

        for value in raw_values:

            if not isinstance(
                value,
                dict,
            ):
                continue

            values.append(
                ResearchComparisonEngine
                ._parse_value(value)
            )

        return ComparisonAspect(
            aspect=aspect,
            values=values,
        )

    # ========================================================
    # SOURCE PARSER
    # ========================================================

    @staticmethod
    def _parse_sources(
        raw_sources: Any,
    ) -> list[dict]:
        """
        Validate source metadata.
        """

        if raw_sources is None:
            return []

        if not isinstance(
            raw_sources,
            list,
        ):
            raise ValueError(
                "Comparison response "
                "'sources' must be a list."
            )

        sources: list[dict] = []

        for source in raw_sources:

            if not isinstance(
                source,
                dict,
            ):
                continue

            sources.append(source)

        return sources

    # ========================================================
    # RESPONSE PARSER
    # ========================================================

    def parse_response(
        self,
        query: str,
        response_text: str,
    ) -> ResearchComparisonReport:
        """
        Parse and validate the LLM comparison response.
        """

        data = self._extract_json(
            response_text
        )

        raw_entities = data.get(
            "entities",
            [],
        )

        raw_comparison = data.get(
            "comparison",
            [],
        )

        summary = str(
            data.get(
                "summary",
                "",
            )
        ).strip()

        # ----------------------------------------------------
        # Validate top-level fields
        # ----------------------------------------------------

        if not isinstance(
            raw_entities,
            list,
        ):
            raise ValueError(
                "Comparison response "
                "'entities' must be a list."
            )

        if not isinstance(
            raw_comparison,
            list,
        ):
            raise ValueError(
                "Comparison response "
                "'comparison' must be a list."
            )

        if not summary:
            raise ValueError(
                "Comparison response is "
                "missing summary."
            )

        # ----------------------------------------------------
        # Entities
        # ----------------------------------------------------

        entities: list[str] = []

        for entity in raw_entities:

            entity_text = str(
                entity
            ).strip()

            if (
                entity_text
                and entity_text not in entities
            ):
                entities.append(
                    entity_text
                )

        # ----------------------------------------------------
        # Comparison aspects
        # ----------------------------------------------------

        comparison: list[
            ComparisonAspect
        ] = []

        for item in raw_comparison:

            if not isinstance(
                item,
                dict,
            ):
                continue

            comparison.append(
                self._parse_aspect(item)
            )

        # ----------------------------------------------------
        # Sources
        # ----------------------------------------------------

        sources = self._parse_sources(
            data.get(
                "sources",
                [],
            )
        )

        # ----------------------------------------------------
        # Final validated report
        # ----------------------------------------------------

        return ResearchComparisonReport(
            query=query,
            entities=entities,
            comparison=comparison,
            summary=summary,
            sources=sources,
        )