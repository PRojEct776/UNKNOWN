from app.rag.config import settings


def test_project_paths_exist():
    assert settings.BASE_DIR.exists()
    assert settings.PAPERS_DIR.exists()
    assert settings.JSON_DIR.exists()
    assert settings.CHUNK_DIR.exists()
    assert settings.VECTOR_DIR.exists()
    assert settings.LOG_DIR.exists()


def test_rag_configuration():
    assert settings.CHUNK_SIZE == 500
    assert settings.CHUNK_OVERLAP == 100
    assert settings.TOP_K_RESULTS == 5


def test_supported_extensions():
    assert ".pdf" in settings.SUPPORTED_EXTENSIONS
    assert ".docx" in settings.SUPPORTED_EXTENSIONS
    assert ".txt" in settings.SUPPORTED_EXTENSIONS


def test_embedding_model():
    assert settings.EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"


def test_default_encoding():
    assert settings.DEFAULT_ENCODING == "utf-8"