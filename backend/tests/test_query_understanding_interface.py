from app.query.query_understanding import (
    QueryType,
    QueryUnderstanding,
    QueryUnderstandingResult,
)


def test_query_types_match_unknown_architecture():
    expected = {
        "FACT",
        "DEFINITION",
        "REASONING",
        "COMPARISON",
        "CODE",
        "SUMMARY",
        "GENERAL",
    }

    actual = {query_type.value for query_type in QueryType}

    assert actual == expected


def test_result_structure():
    result = QueryUnderstandingResult(
        query="What is SAC-RAG?",
        query_type=QueryType.DEFINITION,
    )

    assert result.query == "What is SAC-RAG?"
    assert result.query_type == QueryType.DEFINITION


def test_query_understanding_interface_exists():
    analyzer = QueryUnderstanding()

    assert hasattr(analyzer, "analyze")
    assert callable(analyzer.analyze)


def test_definition_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("What is SAC-RAG?")

    assert result.query_type == QueryType.DEFINITION


def test_reasoning_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("Why is hybrid retrieval useful?")

    assert result.query_type == QueryType.REASONING


def test_comparison_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("Compare BM25 vs FAISS.")

    assert result.query_type == QueryType.COMPARISON


def test_summary_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("Summarize the SAC-RAG pipeline.")

    assert result.query_type == QueryType.SUMMARY


def test_fact_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("When was Python created?")

    assert result.query_type == QueryType.FACT


def test_code_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("Write a Java program for binary search.")

    assert result.query_type == QueryType.CODE


def test_general_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("Tell me something about retrieval.")

    assert result.query_type == QueryType.GENERAL


def test_python_history_is_not_code():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("When was Python created?")

    assert result.query_type == QueryType.FACT


def test_java_history_is_not_code():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("When was Java created?")

    assert result.query_type == QueryType.FACT


def test_javascript_history_is_not_code():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("When was JavaScript created?")

    assert result.query_type == QueryType.FACT


def test_rust_history_is_not_code():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("When was Rust created?")

    assert result.query_type == QueryType.FACT


def test_cpp_code_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("Implement quicksort using C++.")

    assert result.query_type == QueryType.CODE


def test_csharp_code_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("How do I implement a stack in C#?")

    assert result.query_type == QueryType.CODE


def test_java_code_query():
    analyzer = QueryUnderstanding()

    result = analyzer.analyze("Create a Java program for binary search.")

    assert result.query_type == QueryType.CODE


def test_empty_query_rejected():
    analyzer = QueryUnderstanding()

    try:
        analyzer.analyze("   ")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_non_string_query_rejected():
    analyzer = QueryUnderstanding()

    try:
        analyzer.analyze(None)
        assert False, "Expected TypeError"
    except TypeError:
        pass