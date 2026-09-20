from app.query.query_understanding import QueryType as BhagyaQueryType
from app.rag.prompt_engine import QueryType as PromptQueryType
from app.services.rag_service import RAGService


def test_all_query_types_map_correctly():
    for bhagya_type in BhagyaQueryType:
        mapped_type = RAGService._map_query_type(bhagya_type)
        assert mapped_type == PromptQueryType[bhagya_type.name]