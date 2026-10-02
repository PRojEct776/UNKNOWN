from __future__ import annotations

"""
UNKNOWN X v2.3 - Adaptive Prompt Engine

Purpose:
    Detect user query intent and generate an adaptive RAG prompt
    for Gemini and future LLM providers.
"""

import re
from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import ClassVar


class QueryType(Enum):
    """Supported query categories."""

    FACT = "fact"
    DEFINITION = "definition"
    REASONING = "reasoning"
    COMPARISON = "comparison"
    CODE = "code"
    SUMMARY = "summary"
    GENERAL = "general"


class PromptEngine:
    """
    Adaptive Prompt Engine for UNKNOWN X.

    Responsibilities:
    - Detect query intent.
    - Generate intent-specific prompts.
    - Prevent hallucinations by restricting answers to retrieved context.
    """

    _TYPE_INSTRUCTIONS: ClassVar[Mapping[QueryType, str]] = MappingProxyType(
        {
            QueryType.FACT: (
                "Answer with the specific fact found in the retrieved context. "
                "Be concise and avoid unnecessary explanation."
            ),
            QueryType.DEFINITION: (
                "Provide a clear academic definition using only the retrieved context."
            ),
            QueryType.REASONING: (
                "Explain the reasoning step by step using evidence from the retrieved context."
            ),
            QueryType.COMPARISON: (
                "Compare the concepts using similarities, differences, advantages, "
                "and disadvantages. Use a table if appropriate."
            ),
            QueryType.CODE: (
                "Provide correct code only if the retrieved context supports it. "
                "Do not invent APIs, functions, or libraries that are not present "
                "in the retrieved context."
            ),
            QueryType.SUMMARY: (
                "Summarize the retrieved context into key points followed by a short conclusion."
            ),
            QueryType.GENERAL: ("Answer naturally using only the retrieved context."),
        }
    )

    @staticmethod
    def _contains_word(query: str, word: str) -> bool:
        """Check whether a complete word exists in the query."""
        return re.search(rf"\b{re.escape(word)}\b", query) is not None

    @staticmethod
    def _contains_language(query: str, language: str) -> bool:
        """Check for programming language names."""
        if language in {"c++", "c#"}:
            return language in query

        return PromptEngine._contains_word(query, language)

    def detect_query_type(self, query: str) -> QueryType:
        """
        Detect query intent using lightweight rules.
        """

        query = query.lower().strip()

        # -------- Summary --------
        if any(
            self._contains_word(query, word)
            for word in ("summarize", "summary", "brief", "overview")
        ):
            return QueryType.SUMMARY

        # -------- Comparison --------
        if any(
            self._contains_word(query, word)
            for word in ("difference", "compare", "vs", "versus")
        ):
            return QueryType.COMPARISON

        # -------- Direct Code Requests --------
        direct_code_phrases = (
            "write code",
            "write a program",
            "write a function",
            "generate code",
            "generate a program",
            "generate a function",
            "create code",
            "create a program",
            "create a function",
            "implement code",
            "implement a program",
            "implement a function",
            "develop code",
            "develop a program",
            "develop a function",
        )

        if any(phrase in query for phrase in direct_code_phrases):
            return QueryType.CODE

        # -------- Programming Language + Code Action --------
        programming_languages = (
            "python",
            "java",
            "c++",
            "javascript",
            "typescript",
            "c#",
            "go",
            "rust",
        )

        code_actions = (
            "write",
            "create",
            "build",
            "develop",
            "implement",
            "generate",
        )

        has_code_action = any(
            self._contains_word(query, action) for action in code_actions
        )

        has_programming_language = any(
            self._contains_language(query, language)
            for language in programming_languages
        )

        if has_code_action and has_programming_language:
            return QueryType.CODE

        # -------- Reasoning --------
        reasoning_phrases = (
            "why",
            "how does",
            "how do",
            "how can",
            "explain why",
            "reason",
            "cause",
        )

        if any(phrase in query for phrase in reasoning_phrases):
            return QueryType.REASONING

        # -------- Definition --------
        if any(query.startswith(prefix) for prefix in ("what is", "who is", "define")):
            return QueryType.DEFINITION

        # -------- Fact --------
        if any(
            query.startswith(prefix)
            for prefix in ("when", "where", "which", "how many")
        ):
            return QueryType.FACT

        # -------- Default --------
        return QueryType.GENERAL

    def build_prompt(
        self,
        query: str,
        context: str,
        query_type: QueryType | None = None,
    ) -> str:
        """
        Build an adaptive RAG prompt for Gemini/OpenRouter/Groq/Cerebras.
        """

        if query_type is None:
            query_type = self.detect_query_type(query)

        instruction = self._TYPE_INSTRUCTIONS[query_type]

        return f"""
You are UNKNOWN AI, an academic Retrieval-Augmented Generation assistant.

Task Type: {query_type.value}

Instructions:
- {instruction}
- Answer ONLY using the retrieved context.
- If the retrieved context does not contain enough information, respond exactly with:
  "The retrieved context does not contain enough information."
- Do not use outside knowledge.
- Do not fabricate facts or citations.
- Keep the answer well-structured and easy to understand.

Retrieved Context:
{context}

User Question:
{query}

Answer:
""".strip()


# ---------------------------------------------------------
# Test Block
# ---------------------------------------------------------

if __name__ == "__main__":

    engine = PromptEngine()

    test_queries = [
        "What is cloud computing?",
        "When was Python created?",
        "Why is RAG useful?",
        "Compare Docker vs Kubernetes.",
        "Write binary search in Java.",
        "Write Python code for binary search.",
        "Implement quicksort using C++.",
        "How do I implement a stack in C#?",
        "Summarize this IEEE paper.",
        "Tell me about virtualization.",
    ]

    print("=" * 55)
    print("UNKNOWN X v2.3 - Prompt Engine Test")
    print("=" * 55)

    for query in test_queries:
        query_type = engine.detect_query_type(query)
        print(f"\nQuery : {query}")
        print(f"Type  : {query_type.value}")

    print("\nPrompt Engine tests completed successfully.")
