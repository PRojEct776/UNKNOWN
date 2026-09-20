import pytest

from app.query.query_understanding import QueryType, QueryUnderstanding


@pytest.fixture
def analyzer():
    return QueryUnderstanding()


@pytest.mark.parametrize(
    "query,expected_type",
    [
        # Capitalization and punctuation
        ("WHAT IS SAC-RAG?", QueryType.DEFINITION),
        ("What is SAC-RAG!!!", QueryType.DEFINITION),
        ("WHY is hybrid retrieval useful?", QueryType.REASONING),

        # Definition variations
        ("Define FAISS.", QueryType.DEFINITION),
        ("What are embeddings?", QueryType.DEFINITION),
        ("What is the meaning of semantic search?", QueryType.DEFINITION),

        # Reasoning variations
        ("Why does BM25 help retrieval?", QueryType.REASONING),
        ("How does FAISS work?", QueryType.REASONING),
        ("How can hybrid retrieval improve search?", QueryType.REASONING),

        # Comparison variations
        ("BM25 vs FAISS", QueryType.COMPARISON),
        ("Compare BM25 and vector search.", QueryType.COMPARISON),
        ("What is the difference between BM25 and FAISS?", QueryType.COMPARISON),

        # Summary variations
        ("Summarize the retrieval pipeline.", QueryType.SUMMARY),
        ("Give me a summary of SAC-RAG.", QueryType.SUMMARY),
        ("What are the key points of the architecture?", QueryType.SUMMARY),

        # Fact variations
        ("When was FAISS created?", QueryType.FACT),
        ("Who created Python?", QueryType.FACT),
        ("What year was JavaScript introduced?", QueryType.FACT),

        # Code variations
        ("Write Python code for binary search.", QueryType.CODE),
        ("Implement a stack in Java.", QueryType.CODE),
        ("Create a C++ program for sorting.", QueryType.CODE),
        ("How do I implement a linked list in C#?", QueryType.CODE),

        # General queries
        ("Tell me about retrieval.", QueryType.GENERAL),
        ("I need information about semantic search.", QueryType.GENERAL),
        ("Explain SAC-RAG.", QueryType.GENERAL),
    ],
)
def test_robust_query_classification(analyzer, query, expected_type):
    result = analyzer.analyze(query)

    assert result.query_type == expected_type


@pytest.mark.parametrize(
    "query",
    [
        "",
        " ",
        "   ",
        "\t",
        "\n",
    ],
)
def test_whitespace_queries_are_rejected(analyzer, query):
    with pytest.raises(ValueError):
        analyzer.analyze(query)


@pytest.mark.parametrize(
    "query",
    [
        None,
        123,
        45.6,
        [],
        {},
    ],
)
def test_non_string_queries_are_rejected(analyzer, query):
    with pytest.raises(TypeError):
        analyzer.analyze(query)


def test_original_query_is_trimmed(analyzer):
    result = analyzer.analyze("   What is FAISS?   ")

    assert result.query == "What is FAISS?"
    assert result.query_type == QueryType.DEFINITION


def test_code_request_with_history_word_is_still_code(analyzer):
    result = analyzer.analyze(
        "When writing Python, how do I implement binary search?"
    )

    assert result.query_type == QueryType.CODE


def test_programming_language_alone_is_not_code(analyzer):
    result = analyzer.analyze("Tell me about Python.")

    assert result.query_type == QueryType.GENERAL


def test_question_about_language_history_is_fact(analyzer):
    result = analyzer.analyze("When was Python created?")

    assert result.query_type == QueryType.FACT