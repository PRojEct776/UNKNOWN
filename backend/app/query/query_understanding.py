from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class QueryType(str, Enum):
    FACT = "FACT"
    DEFINITION = "DEFINITION"
    REASONING = "REASONING"
    COMPARISON = "COMPARISON"
    CODE = "CODE"
    SUMMARY = "SUMMARY"
    GENERAL = "GENERAL"


@dataclass(frozen=True)
class QueryUnderstandingResult:
    query: str
    query_type: QueryType


class QueryUnderstanding:
    """
    Query Understanding module for UNKNOWN.

    Responsibility:
        Classify a user's natural-language query into one of the
        seven query types already used by the UNKNOWN RAG pipeline.
    """

    _DEFINITION_PATTERNS = (
        r"\bwhat is\b",
        r"\bwhat are\b",
        r"\bdefine\b",
        r"\bdefinition of\b",
        r"\bmeaning of\b",
        r"\bexplain the meaning\b",
    )

    _REASONING_PATTERNS = (
        r"\bwhy\b",
        r"\bhow does\b",
        r"\bhow do\b",
        r"\bhow can\b",
        r"\bexplain why\b",
        r"\breason\b",
        r"\bcause\b",
    )

    _COMPARISON_PATTERNS = (
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bversus\b",
        r"\bvs\.?\b",
        r"\bdifference between\b",
        r"\bdifferences between\b",
        r"\bwhich is different\b",
    )

    _CODE_ACTION_PATTERNS = (
        r"\bwrite\b",
        r"\bimplement\b",
        r"\bcreate\b",
        r"\bcode\b",
        r"\bprogram\b",
        r"\bfunction\b",
        r"\bscript\b",
        r"\bdebug\b",
        r"\bfix\b",
    )

    _PROGRAMMING_LANGUAGES = (
        "python",
        "java",
        "javascript",
        "typescript",
        "c++",
        "c#",
        "c",
        "go",
        "golang",
        "rust",
        "kotlin",
        "swift",
        "php",
        "ruby",
        "scala",
    )

    _SUMMARY_PATTERNS = (
        r"\bsummarize\b",
        r"\bsummary\b",
        r"\bbriefly explain\b",
        r"\bgive me a summary\b",
        r"\bkey points\b",
        r"\bmain points\b",
        r"\bhighlights\b",
    )

    _FACT_PATTERNS = (
        r"\bwhen\b",
        r"\bwhen was\b",
        r"\bwhen were\b",
        r"\bwho\b",
        r"\bwhere\b",
        r"\bhow many\b",
        r"\bhow much\b",
        r"\bwhich year\b",
        r"\bwhat year\b",
    )

    def analyze(self, query: str) -> QueryUnderstandingResult:
        """
        Classify a user query.

        Raises:
            TypeError: if query is not a string.
            ValueError: if query is empty or contains only whitespace.
        """
        if not isinstance(query, str):
            raise TypeError("query must be a string")

        normalized = query.strip()

        if not normalized:
            raise ValueError("query must not be empty")

        query_type = self._detect_query_type(normalized)

        return QueryUnderstandingResult(
            query=normalized,
            query_type=query_type,
        )

    def _detect_query_type(self, query: str) -> QueryType:
        text = query.lower()

        # CODE gets priority over general words such as "when", "what",
        # or "how", because programming requests can contain them.
        if self._is_code_query(text):
            return QueryType.CODE

        if self._matches_any(text, self._COMPARISON_PATTERNS):
            return QueryType.COMPARISON

        if self._matches_any(text, self._SUMMARY_PATTERNS):
            return QueryType.SUMMARY

        if self._matches_any(text, self._DEFINITION_PATTERNS):
            return QueryType.DEFINITION

        if self._matches_any(text, self._REASONING_PATTERNS):
            return QueryType.REASONING

        if self._matches_any(text, self._FACT_PATTERNS):
            return QueryType.FACT

        return QueryType.GENERAL

    def _is_code_query(self, text: str) -> bool:
        has_code_action = self._matches_any(text, self._CODE_ACTION_PATTERNS)
        has_programming_language = self._contains_programming_language(text)

        return has_code_action and has_programming_language

    def _contains_programming_language(self, text: str) -> bool:
        for language in self._PROGRAMMING_LANGUAGES:
            # C++ and C# are handled as literal substrings because
            # regex word boundaries do not behave correctly with
            # their punctuation.
            if language in {"c++", "c#"}:
                if language in text:
                    return True
                continue

            if re.search(rf"\b{re.escape(language)}\b", text):
                return True

        return False

    @staticmethod
    def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)