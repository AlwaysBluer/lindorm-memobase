"""Unit tests for UserProfiles search query modes."""

import pytest
from unittest.mock import patch, MagicMock

from lindormmemobase.core.storage.user_profiles import LindormTableStorage


@pytest.mark.unit
@pytest.mark.asyncio
class TestUserProfilesSearchModes:
    """Validate generated Lindorm Search queries for profile search methods."""

    async def test_vector_search_profiles_uses_pure_vector_prefilter(self, mock_config):
        """Vector search should not include full-text match or filter_rrf fusion settings."""
        with patch("lindormmemobase.core.storage.user_profiles.OpenSearch") as mock_os:
            mock_client = MagicMock()
            mock_client.search.return_value = {"hits": {"hits": []}}
            mock_os.return_value = mock_client

            storage = LindormTableStorage(mock_config)

            await storage.vector_search_profiles(
                user_id="user_1",
                query="travel plan",
                query_vector=[0.1] * mock_config.embedding_dim,
                size=5,
                min_score=0.4,
                project_id="project_a",
                topics=["travel"],
                subtopics=["destination"],
            )

            call_kwargs = mock_client.search.call_args.kwargs
            body = call_kwargs["body"]

            assert call_kwargs["routing"] == "user_1"
            assert body["ext"]["lvector"]["filter_type"] == "pre_filter"
            assert "hybrid_search_type" not in body["ext"]["lvector"]

            knn_filter = body["query"]["knn"]["embedding"]["filter"]["bool"]["filter"]
            assert {"term": {"user_id": "user_1"}} in knn_filter
            assert {"term": {"project_id": "project_a"}} in knn_filter
            assert {"terms": {"topic": ["travel"]}} in knn_filter
            assert {"terms": {"subtopic": ["destination"]}} in knn_filter

    async def test_hybrid_search_profiles_uses_filter_rrf_structure(self, mock_config):
        """Hybrid search should use match + scalar filters with filter_rrf settings."""
        with patch("lindormmemobase.core.storage.user_profiles.OpenSearch") as mock_os:
            mock_client = MagicMock()
            mock_client.search.return_value = {"hits": {"hits": []}}
            mock_os.return_value = mock_client

            storage = LindormTableStorage(mock_config)

            await storage.hybrid_search_profiles(
                user_id="user_2",
                query="favorite restaurant",
                query_vector=[0.2] * mock_config.embedding_dim,
                size=8,
                min_score=0.3,
                project_id="project_b",
                topics=["food"],
            )

            body = mock_client.search.call_args.kwargs["body"]

            lvector = body["ext"]["lvector"]
            assert lvector["hybrid_search_type"] == "filter_rrf"
            assert lvector["filter_type"] == "efficient_filter"
            assert lvector["rrf_knn_weight_factor"] == "0.5"
            assert lvector["rrf_rank_constant"] == "60"

            must_blocks = body["query"]["knn"]["embedding"]["filter"]["bool"]["must"]
            assert len(must_blocks) == 2
            assert must_blocks[0] == {
                "bool": {"must": [{"match": {"content": {"query": "favorite restaurant"}}}]}
            }

            scalar_filters = must_blocks[1]["bool"]["filter"]
            assert {"term": {"user_id": "user_2"}} in scalar_filters
            assert {"term": {"project_id": "project_b"}} in scalar_filters
            assert {"terms": {"topic": ["food"]}} in scalar_filters
