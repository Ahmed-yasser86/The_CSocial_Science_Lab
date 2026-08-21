import importlib


def test_ingestion_embeddings_imports_cleanly():
    module = importlib.import_module("Ingestion_Pipline.infra.embeddings")
    assert hasattr(module, "build_embeddings")
