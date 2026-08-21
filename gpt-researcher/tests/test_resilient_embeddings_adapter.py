from gpt_researcher.memory.resilient_embeddings import ResilientEmbeddingsAdapter


class DummyEmbeddings:
    def __init__(self):
        self.calls = 0

    def embed_query(self, text):
        self.calls += 1
        return [0.1, 0.2, 0.3]

    def embed_documents(self, texts):
        self.calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_resilient_embeddings_adapter_returns_embeddings():
    adapter = ResilientEmbeddingsAdapter(DummyEmbeddings())

    doc_embeddings = adapter.embed_documents(["hello"])
    assert doc_embeddings == [[0.1, 0.2, 0.3]]

    query_embedding = adapter.embed_query("hello")
    assert query_embedding == [0.1, 0.2, 0.3]
