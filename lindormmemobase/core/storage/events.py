import uuid
from datetime import datetime
from opensearchpy import OpenSearch
from typing import Optional, Dict, List, Any
from ...utils.promise import Promise, CODE
from ...config import Config

# Global storage instance cache
_lindorm_search_storage = None

def get_lindorm_search_storage(config: Config) -> 'LindormSearchStorage':
    """Get or create a global LindormSearchStorage instance."""
    global _lindorm_search_storage
    if _lindorm_search_storage is None and config is None:
        raise Exception("requre configurations to set lindorm connection")
    elif _lindorm_search_storage is None:
        _lindorm_search_storage = LindormSearchStorage(config)
    return _lindorm_search_storage

# class OpenSearchEventStorage:
# Lindorm is compatible with Opensearch .
class LindormSearchStorage:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenSearch(
            hosts=[{
                'host': config.opensearch_host,
                'port': config.opensearch_port
            }],
            http_auth=(config.opensearch_username, config.opensearch_password) if config.opensearch_username else None,
            use_ssl=config.opensearch_use_ssl,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )
        self._ensure_indices()
    
    def _ensure_indices(self):
        events_setting_mapping = {
            "settings": {
                "index.knn": True,
                "knn_routing": True,
            },
            "mappings": {
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
        
        if not self.client.indices.exists(index=self.config.opensearch_events_index):
            self.client.indices.create(index=self.config.opensearch_events_index, body=events_setting_mapping)
        
        # 创建event_gists索引
        gists_setting_mapping = {
            "settings": {
                "index.knn": True,
                "knn_routing": True,
            },
            "mappings": {
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
        
        if not self.client.indices.exists(index=self.config.opensearch_event_gists_index):
            self.client.indices.create(index=self.config.opensearch_event_gists_index, body=gists_setting_mapping)

    async def store_event_with_embedding(
        self, 
        user_id: str, 
        event_data: Dict[str, Any], 
        embedding: Optional[List[float]] = None
    ) -> Promise[str]:
        try:
            event_id = str(uuid.uuid4())
            doc = {
                "user_id": user_id,
                "event_data": event_data,
                "embedding": embedding,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self.client.index(
                index=self.config.opensearch_events_index,
                id=event_id,
                body=doc,
                routing=user_id
            )
            
            return Promise.resolve(event_id)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to store event: {str(e)}")

    async def store_event_gist_with_embedding(
        self,
        user_id: str,
        event_id: str,
        gist_data: Dict[str, Any],
        embedding: Optional[List[float]] = None
    ) -> Promise[str]:
        try:
            gist_id = str(uuid.uuid4())
            doc = {
                "user_id": user_id,
                "event_id": event_id,
                "gist_data": gist_data,
                "embedding": embedding,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self.client.index(
                index=self.config.opensearch_event_gists_index,
                id=gist_id,
                body=doc,
                routing=user_id,
            )
            
            return Promise.resolve(gist_id)
        except Exception as e:
            return Promise.reject("OPENSEARCH_ERROR", f"Failed to store event gist: {str(e)}")

    async def hybrid_search_events(
        self,
        user_id: str,
        query: str,
        query_vector: List[float],
        size: int = 10,
    ) -> Promise[List[Dict[str, Any]]]:
        try:
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
                                            }]
                                        }
                                    }]
                                }
                            }
                        }
                    }
                }
            }
            
            response = self.client.search(
                index=self.config.opensearch_events_index,
                body=query,
                routing=user_id  # Add routing for Lindorm Search
            )
            
            results = []
            for hit in response['hits']['hits']:
                results.append({
                    'id': hit['_source']['id'],
                    'event_data': hit['_source']['event_data'],
                    'score': hit['_score'],
                    'created_at': hit['_source']['created_at']
                })
            
            return Promise.resolve(results)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to search events: {str(e)}")
        
    async def hybrid_search_gist_events(
        self,
        user_id: str,
        query: str,
        query_vector: List[float],
        size: int = 10,
    ) -> Promise[List[Dict[str, Any]]]:
        try:
            search_query = {
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
                                                        "gist_data": {
                                                            "query": query
                                                        }
                                                    }
                                                },
                                                {
                                                    "term": {
                                                        "_routing": user_id,
                                                    }
                                                }
                                            ]
                                        }
                                    }]
                                }
                            }
                        }
                    }
                }
            }
            
            response = self.client.search(
                index=self.config.opensearch_event_gists_index,
                body=search_query,
                routing=user_id  # Add routing for Lindorm Search
            )
            
            results = []
            for hit in response['hits']['hits']:
                results.append({
                    'id': hit['_id'],
                    'event_id': hit['_source']['event_id'],
                    'gist_data': hit['_source']['gist_data'],
                    'score': hit['_score'],
                    'created_at': hit['_source']['created_at']
                })
            
            return Promise.resolve(results)
        except Exception as e:
            return Promise.reject(CODE.SERVER_PROCESS_ERROR, f"Failed to search gist events: {str(e)}")


async def store_event_with_embedding(
    user_id: str, 
    event_data: Dict[str, Any], 
    embedding: Optional[List[float]] = None,
    config: Config = None
) -> Promise[str]:
    if config is None:
        return Promise.reject("CONFIG_ERROR", "Config parameter is required")
    storage = LindormSearchStorage(config)
    return await storage.store_event_with_embedding(user_id, event_data, embedding)

async def store_event_gist_with_embedding(
    user_id: str,
    event_id: str,
    gist_data: Dict[str, Any],
    embedding: Optional[List[float]] = None,
    config: Config = None
) -> Promise[str]:
    if config is None:
        return Promise.reject("CONFIG_ERROR", "Config parameter is required")
    storage = LindormSearchStorage(config)
    return await storage.store_event_gist_with_embedding(user_id, event_id, gist_data, embedding)