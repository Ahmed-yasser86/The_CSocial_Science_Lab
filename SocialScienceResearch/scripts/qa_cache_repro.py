import sys, os
sys.path.insert(0, r"C:\Users\DELL\graph-rag-agent\SocialScienceResearch")
os.chdir(r"C:\Users\DELL\graph-rag-agent\SocialScienceResearch")

from SocialScienceResearch.services.recommendation_graph_service import RecommendationGraphService


class FakeRecommendations:
    def __init__(self):
        self._edges = []

    def list_recommendation_edges_graph(self, run_ids=None):
        return list(self._edges)


class FakeRepo:
    def __init__(self):
        self.recommendations = FakeRecommendations()


svc = RecommendationGraphService.__new__(RecommendationGraphService)
svc.__init__(FakeRepo())

g1 = svc.build_graph(run_id="r1")
print("BEFORE: run-scoped edges =", g1.number_of_edges())

svc._repos.recommendations._edges.append(
    {"source_video_id": "a", "recommended_video_id": "b", "position": 1, "collection_run_id": "r1"}
)

g2 = svc.build_graph(run_id="r1")
print("AFTER scrape: run-scoped edges =", g2.number_of_edges(), "(BUG if 0: stale forever)")

g3 = svc.build_graph()
print("WHOLE before add:", g3.number_of_edges())
svc._repos.recommendations._edges.append(
    {"source_video_id": "c", "recommended_video_id": "d", "position": 2, "collection_run_id": "r2"}
)
g4 = svc.build_graph()
print("WHOLE after add:", g4.number_of_edges(), "(BUG if 0: stale until 300s TTL)")
