import uuid
from datetime import datetime, timezone, timedelta
from opensearchpy import OpenSearch
from typing import Optional, Dict, List, Any
from ...utils.errors import SearchStorageError
from ...config import Config, TRACE_LOG

# Backward compatibility - delegate to StorageManager
def get_lindorm_search_storage(config: Config) -> 'LindormSearchStorage':
    """Get or create a global LindormSearchStorage instance - delegates to StorageManager."""
    from .manager import StorageManager
    return StorageManager.get_search_storage(config)


# class OpenSearchEventStorage:
# Lindorm is compatible with Opensearch .
class LindormSearchStorage:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenSearch(
            hosts=[{
                'host': config.lindorm_search_host,
                'port': config.lindorm_search_port
            }],
            http_auth=(
                config.lindorm_search_username,
                config.lindorm_search_password) if config.lindorm_search_username else None,
            use_ssl=config.lindorm_search_use_ssl,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )
        # Don't call _ensure methods in __init__ anymore
        # Indices are created explicitly via initialize_indices()
    
    def initialize_indices(self):
        """Create event and event gist indices. Called during StorageManager initialization."""
        self._ensure_event_indices()
        self._ensure_event_gist_indices()

    def _ensure_event_indices(self):
        events_setting_mapping = {
            "settings": {
                "index.knn": True,
                "knn_routing": True,
            },
            "mappings": {
                "_source": {
                    "excludes": ["embedding"]
                },
                "properties": {
                    "user_id": {"type": "keyword"},
                    "event_data": {"type": "object"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self.config.embedding_dim,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lvector",
                            "parameters": {
                                "m": 24,
                                "ef_construction": 200
                            }
                        }
                    },
                    "created_at": {"type": "date"}
                }
            }
        }

        if not self.client.indices.exists(index=self.config.lindorm_search_events_index):
            self.client.indices.create(index=self.config.lindorm_search_events_index, body=events_setting_mapping)

    def _ensure_event_gist_indices(self):
        gists_setting_mapping = {
            "settings": {
                "index.knn": True,
                "knn_routing": True,
            },
            "mappings": {
                "_source": {
                    "excludes": ["embedding"]
                },
                "properties": {
                    "user_id": {"type": "keyword"},
                    "event_id": {"type": "keyword"},
                    "gist_data": {"type": "object"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self.config.embedding_dim,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lvector",
                            "parameters": {
                                "m": 24,
                                "ef_construction": 200
                            }
                        }
                    },
                    "created_at": {"type": "date"}
                }
            }
        }

        if not self.client.indices.exists(index=self.config.lindorm_search_event_gists_index):
            self.client.indices.create(index=self.config.lindorm_search_event_gists_index, body=gists_setting_mapping)

    async def store_event_with_embedding(
            self,
            user_id: str,
            event_id: str,
            event_data: Dict[str, Any],
            embedding: Optional[List[float]] = None
    ) -> str:
        try:
            doc = {
                "user_id": user_id,
                "event_data": event_data,
                "embedding": embedding,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            response = self.client.index(
                index=self.config.lindorm_search_events_index,
                id=event_id,
                body=doc,
                routing=user_id
            )

            return event_id
        except Exception as e:
            raise SearchStorageError(f"Failed to store event: {str(e)}") from e

    async def store_event_gist_with_embedding(
            self,
            user_id: str,
            event_id: str,
            gist_data: Dict[str, Any],
            embedding: Optional[List[float]] = None
    ) -> str:
        try:
            gist_id = str(uuid.uuid4())
            doc = {
                "user_id": user_id,
                "event_id": event_id,
                "gist_data": gist_data,
                "embedding": embedding,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            response = self.client.index(
                index=self.config.lindorm_search_event_gists_index,
                id=gist_id,
                body=doc,
                routing=user_id,
            )

            return gist_id
        except Exception as e:
            raise SearchStorageError(f"Failed to store event gist: {str(e)}") from e

    async def update_event_with_embedding(
            self,
            user_id: str,
            event_id: str,
            event_data: Dict[str, Any],
            embedding: Optional[List[float]] = None
    ) -> str:
        try:
            doc = {
                "event_data": event_data,
                "embedding": embedding,
            }

            response = self.client.update(
                index=self.config.lindorm_search_events_index,
                id=event_id,
                body={"doc": doc},
                routing=user_id
            )

            return event_id
        except Exception as e:
            raise SearchStorageError(f"Failed to update event: {str(e)}") from e

    async def update_event_gist_with_embedding(
            self,
            user_id: str,
            gist_id: str,
            gist_data: Dict[str, Any],
            embedding: Optional[List[float]] = None
    ) -> str:
        try:
            doc = {
                "gist_data": gist_data,
                "embedding": embedding,
            }

            response = self.client.update(
                index=self.config.lindorm_search_event_gists_index,
                id=gist_id,
                body={"doc": doc},
                routing=user_id
            )

            return gist_id
        except Exception as e:
            raise SearchStorageError(f"Failed to update event gist: {str(e)}") from e

    async def delete_event(
            self,
            user_id: str,
            event_id: str
    ) -> str:
        try:
            response = self.client.delete(
                index=self.config.lindorm_search_events_index,
                id=event_id,
                routing=user_id
            )

            return event_id
        except Exception as e:
            raise SearchStorageError(f"Failed to delete event: {str(e)}") from e

    async def delete_event_gist(
            self,
            user_id: str,
            gist_id: str
    ) -> str:
        try:
            response = self.client.delete(
                index=self.config.lindorm_search_event_gists_index,
                id=gist_id,
                routing=user_id
            )

            return gist_id
        except Exception as e:
            raise SearchStorageError(f"Failed to delete event gist: {str(e)}") from e

    async def delete_event_gists_by_event_id(
            self,
            user_id: str,
            event_id: str
    ) -> int:
        """Delete all gists associated with an event_id"""
        try:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"_routing": user_id}},
                            {"term": {"event_id": event_id}},
                            {"term": {"user_id": user_id}}
                        ]
                    }
                }
            }

            response = self.client.delete_by_query(
                index=self.config.lindorm_search_event_gists_index,
                body=query,
                routing=user_id
            )

            deleted_count = response.get('deleted', 0)
            return deleted_count
        except Exception as e:
            raise SearchStorageError(f"Failed to delete event gists: {str(e)}") from e

    async def hybrid_search_events(
            self,
            user_id: str,
            query: str,
            query_vector: List[float],
            size: int = 10,
            min_score: float = 0.6,
            time_range_in_days: int = 21,
    ) -> List[Dict[str, Any]]:
        try:
            time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
            query = {
                "size": size,
                "sort": [{"_score": {"order": "desc"}}],  # Add sort field for Lindorm
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_vector,
                            "filter": {
                                "bool": {
                                    "must": [{
                                        "bool": {
                                            "must": [
                                                {
                                                    "match": {
                                                        "event_data": {
                                                            "query": query
                                                        }
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "_routing": user_id,
                                                    }
                                                },
                                                {
                                                    "range": {
                                                        "created_at": {
                                                            "gt": time_cutoff.isoformat()
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    }]
                                }
                            },
                            "topk": size,
                        }
                    }
                },
                "ext": {
                    "lvector": {
                        "min_score": str(min_score),
                        "hybrid_search_type": "filter_rrf",
                        "rrf_knn_weight_factor": "0.5"
                    }
                }
            }

            response = self.client.search(
                index=self.config.lindorm_search_events_index,
                body=query,
                routing=user_id  # Add routing for Lindorm Search
            )

            results = []
            for hit in response['hits']['hits']:
                results.append({
                    'id': hit['_source']['id'],
                    'event_data': hit['_source']['event_data'],
                    'similarity': hit['_score'],
                    'created_at': hit['_source']['created_at']
                })

            return results
        except Exception as e:
            raise SearchStorageError(f"Failed to search events: {str(e)}") from e

    async def hybrid_search_gist_events(
            self,
            user_id: str,
            query: str,
            query_vector: List[float],
            size: int = 10,
            min_score: float = 0.6,
            time_range_in_days: int = 21
    ) -> List[Dict[str, Any]]:
        try:
            time_cutoff = datetime.now(timezone.utc) - timedelta(days=time_range_in_days)
            search_query = {
                "size": size,
                "_source": {
                    "exclude": ["embedding"]
                },
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_vector,
                            "filter": {
                                "bool": {
                                    "must": [{
                                        "bool": {
                                            "must": [
                                                {
                                                    "match": {
                                                        "gist_data.content": {
                                                            "query": query
                                                        }
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "_routing": user_id,
                                                    }
                                                },
                                                {
                                                    "range": {
                                                        "created_at": {
                                                            "gt": time_cutoff.isoformat()
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    }]
                                }
                            },
                            "k": size,
                        }
                    }
                },
                "ext": {
                    "lvector": {
                        "min_score": str(min_score),
                        "hybrid_search_type": "filter_rrf",
                        "rrf_knn_weight_factor": "0.5"
                    }
                }
            }

            response = self.client.search(
                index=self.config.lindorm_search_event_gists_index,
                body=search_query,
                routing=user_id  # Add routing for Lindorm Search
            )
            if not response or 'hits' not in response or 'hits' not in response['hits']:
                TRACE_LOG.error(user_id, f"Invalid search response structure: {response}")
                return []

            gists = []
            for hit in response['hits']['hits']:
                if '_source' not in hit:
                    TRACE_LOG.error(user_id, f"Missing _source in search hit: {hit.keys()}")
                    continue
                source = hit['_source']
                # Check if required fields exist in source
                if 'gist_data' not in source or 'created_at' not in source:
                    TRACE_LOG.error(user_id, f"Missing required fields in _source: {source.keys()}")
                    continue
                similarity = hit.get('_score', 0.0)
                gists.append({
                    "id": hit['_id'],
                    "gist_data": source['gist_data'],
                    "created_at": source['created_at'],
                    "updated_at": source.get('updated_at', source['created_at']),
                    "similarity": similarity
                })

            return gists
        except Exception as e:
            raise SearchStorageError(f"Failed to search gist events: {str(e)}") from e


async def search_user_event_gists_with_embedding(
        user_id: str,
        query: str,
        query_vector: List[float],
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21
) -> List[Dict[str, Any]]:
    storage = get_lindorm_search_storage(config)
    return await storage.hybrid_search_gist_events(user_id, query, query_vector, topk, similarity_threshold, time_range_in_days)


async def search_user_events_with_embedding(
        user_id: str,
        query: str,
        query_vector: List[float],
        config: Config,
        topk: int = 10,
        similarity_threshold: float = 0.2,
        time_range_in_days: int = 21
)-> List[Dict[str, Any]]:
    storage = get_lindorm_search_storage(config)
    return await storage.hybrid_search_events(user_id, query, query_vector, topk,
                                              similarity_threshold, time_range_in_days)


async def store_event_with_embedding(
        user_id: str,
        event_id: str,
        event_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.store_event_with_embedding(user_id, event_id, event_data, embedding)


async def store_event_gist_with_embedding(
        user_id: str,
        event_id: str,
        gist_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.store_event_gist_with_embedding(user_id, event_id, gist_data, embedding)


async def update_event_with_embedding(
        user_id: str,
        event_id: str,
        event_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.update_event_with_embedding(user_id, event_id, event_data, embedding)


async def update_event_gist_with_embedding(
        user_id: str,
        gist_id: str,  # 添加 gist_id 参数
        gist_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.update_event_gist_with_embedding(user_id, gist_id, gist_data, embedding)


async def delete_event(
        user_id: str,
        event_id: str,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.delete_event(user_id, event_id)


async def delete_event_gist(
        user_id: str,
        event_gist_id: str,
        config: Config = None
) -> str:
    storage = get_lindorm_search_storage(config)
    return await storage.delete_event_gist(user_id, event_gist_id)


async def delete_event_gists_by_event_id(
        user_id: str,
        event_id: str,
        config: Config = None
) -> int:
    storage = get_lindorm_search_storage(config)
    return await storage.delete_event_gists_by_event_id(user_id, event_id)
