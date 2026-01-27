import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from opensearchpy import OpenSearch

from lindormmemobase.utils.errors import StorageError, SearchStorageError
from lindormmemobase.utils.tools import validate_and_format_embedding
from lindormmemobase.config import Config, LOG
from .base import LindormStorageBase


DEFAULT_PROJECT_ID = "default"


def get_lindorm_image_storage(config: Config) -> "LindormImageStorage":
    """Get LindormImageStorage instance via StorageManager (lazy import to avoid circular dependency)."""
    from .manager import StorageManager
    return StorageManager.get_image_storage(config)


class LindormImageStorage(LindormStorageBase):
    def __init__(self, config: Config):
        super().__init__(config)
        self.image_index_name = f"{self.config.lindorm_table_database}.ImageStore.srh_idx"
        self.client = OpenSearch(
            hosts=[{
                "host": config.lindorm_search_host,
                "port": config.lindorm_search_port,
            }],
            http_auth=(
                config.lindorm_search_username,
                config.lindorm_search_password,
            ) if config.lindorm_search_username else None,
            use_ssl=config.lindorm_search_use_ssl,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
            maxsize=config.lindorm_search_pool_size,
        )

    def _get_pool_name(self) -> str:
        return "memobase_image_pool"

    def _get_pool_config(self) -> dict:
        return {
            "host": self.config.lindorm_table_host,
            "port": self.config.lindorm_table_port,
            "user": self.config.lindorm_table_username,
            "password": self.config.lindorm_table_password,
            "database": self.config.lindorm_table_database,
            "pool_size": self.config.lindorm_table_pool_size,
        }

    def initialize_tables_and_indices(self):
        self._create_table()
        self._create_search_index()

    def _create_table(self):
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES LIKE 'ImageStore'")
            if cursor.fetchone():
                LOG.info("ImageStore table already exists, skipping creation")
                return

            cursor.execute(
                """
                CREATE TABLE ImageStore (
                    project_id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    image_id VARCHAR NOT NULL,
                    caption VARCHAR,
                    image_url VARCHAR NOT NULL,
                    feature_vector VARCHAR,
                    content_type VARCHAR,
                    file_size BIGINT,
                    metadata JSON,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    PRIMARY KEY(project_id, user_id, image_id)
                )
                """
            )

            try:
                cursor.execute("CREATE INDEX idx_created_at ON ImageStore (created_at)")
            except Exception:
                pass

            try:
                cursor.execute("CREATE INDEX idx_updated_at ON ImageStore (updated_at)")
            except Exception:
                pass

            conn.commit()
            LOG.info("ImageStore table created")
        finally:
            cursor.close()
            conn.close()

    def _create_search_index(self):
        pool = self._get_pool()
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            LOG.info("ImageStore: Checking if search index exists...")
            cursor.execute("SHOW INDEX FROM ImageStore")
            index_exists = False
            for row in cursor.fetchall():
                if len(row) >= 3 and row[2] == "srh_idx":
                    index_exists = True
                    break
            if index_exists:
                LOG.info("ImageStore search index already exists, skipping creation")
                return

            LOG.info("ImageStore: Creating search index (this may take several minutes on first run)...")
            def _create_index_with_caption_mapping(mapping: str):
                cursor.execute(
                    f"""
                    CREATE INDEX srh_idx USING SEARCH ON ImageStore(
                        project_id,
                        user_id,
                        image_id,
                        image_url,
                        content_type,
                        file_size,
                        created_at,
                        updated_at,
                        caption(mapping='{mapping}'),
                        feature_vector(mapping='{{
                            "type": "knn_vector",
                            "dimension": {self.config.multimodal_embedding_dim},
                            "data_type": "float",
                            "method": {{
                                "engine": "lvector",
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "parameters": {{
                                    "m": 24,
                                    "ef_construction": 500
                                }}
                            }}
                        }}'),
                        metadata
                    ) PARTITION BY hash(project_id) WITH (
                        SOURCE_SETTINGS='{{
                            "excludes": ["feature_vector"]
                        }}',
                        INDEX_SETTINGS='{{
                            "index": {{
                                "knn": true,
                                "knn_routing": true,
                                "knn.vector_empty_value_to_keep": true
                            }}
                        }}'
                    )
                    """
                )

            try:
                _create_index_with_caption_mapping(
                    '{"type": "text", "analyzer": "ik_smart"}'
                )
            except Exception as e:
                LOG.warning(f"ImageStore search index create failed with analyzer: {e}. Retrying without analyzer.")
                _create_index_with_caption_mapping('{"type": "text"}')

            conn.commit()
            LOG.info("ImageStore search index created")
        finally:
            cursor.close()
            conn.close()

    async def store_image(
        self,
        project_id: str,
        user_id: str,
        image_id: Optional[str],
        caption: Optional[str],
        image_url: str,
        feature_vector: Optional[List[float]],
        content_type: Optional[str],
        file_size: Optional[int],
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        def _store_image_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            actual_image_id = image_id or str(uuid.uuid4())

            try:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc)
                metadata_json = json.dumps(metadata) if metadata is not None else None
                feature_vector_str = validate_and_format_embedding(
                    feature_vector,
                    self.config.multimodal_embedding_dim,
                    user_id,
                    project_id=actual_project_id,
                )

                cursor.execute(
                    """
                    INSERT INTO ImageStore
                    (project_id, user_id, image_id, caption, image_url, feature_vector,
                     content_type, file_size, metadata, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(actual_project_id),
                        str(user_id),
                        str(actual_image_id),
                        caption,
                        image_url,
                        feature_vector_str,
                        content_type,
                        file_size,
                        metadata_json,
                        now,
                        now,
                    ),
                )
                conn.commit()
                return actual_image_id
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to store image: {e}") from e
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(_store_image_sync, "Failed to store image")

    async def update_image(
        self,
        project_id: str,
        user_id: str,
        image_id: str,
        caption: Optional[str] = None,
        image_url: Optional[str] = None,
        feature_vector: Optional[List[float]] = None,
        content_type: Optional[str] = None,
        file_size: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        def _update_image_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            actual_project_id = project_id or DEFAULT_PROJECT_ID

            try:
                cursor = conn.cursor()
                fields = []
                params = []

                if caption is not None:
                    fields.append("caption = %s")
                    params.append(caption)
                if image_url is not None:
                    fields.append("image_url = %s")
                    params.append(image_url)
                if feature_vector is not None:
                    feature_vector_str = validate_and_format_embedding(
                        feature_vector,
                        self.config.multimodal_embedding_dim,
                        user_id,
                        project_id=actual_project_id,
                    )
                    fields.append("feature_vector = %s")
                    params.append(feature_vector_str)
                if content_type is not None:
                    fields.append("content_type = %s")
                    params.append(content_type)
                if file_size is not None:
                    fields.append("file_size = %s")
                    params.append(file_size)
                if metadata is not None:
                    metadata_json = json.dumps(metadata)
                    fields.append("metadata = %s")
                    params.append(metadata_json)

                if not fields:
                    return image_id

                fields.append("updated_at = %s")
                params.append(datetime.now(timezone.utc))
                params.extend([str(actual_project_id), str(user_id), str(image_id)])

                query = f"UPDATE ImageStore SET {', '.join(fields)} WHERE project_id = %s AND user_id = %s AND image_id = %s"
                cursor.execute(query, tuple(params))
                conn.commit()
                return image_id
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to update image: {e}") from e
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(_update_image_sync, "Failed to update image")

    async def delete_image(self, project_id: str, user_id: str, image_id: str) -> str:
        def _delete_image_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM ImageStore WHERE project_id = %s AND user_id = %s AND image_id = %s",
                    (str(actual_project_id), str(user_id), str(image_id)),
                )
                conn.commit()
                return image_id
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to delete image: {e}") from e
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(_delete_image_sync, "Failed to delete image")

    async def get_image(
        self,
        project_id: str,
        user_id: str,
        image_id: str,
    ) -> Optional[Dict[str, Any]]:
        def _get_image_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            try:
                cursor = conn.cursor(dictionary=True)
                columns = (
                    "project_id, user_id, image_id, caption, image_url, content_type, file_size, metadata, created_at, updated_at"
                )
                cursor.execute(
                    f"SELECT {columns} FROM ImageStore WHERE project_id = %s AND user_id = %s AND image_id = %s",
                    (str(actual_project_id), str(user_id), str(image_id)),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                if row.get("metadata") and isinstance(row["metadata"], str):
                    row["metadata"] = json.loads(row["metadata"])
                return row
            except Exception as e:
                raise StorageError(f"Failed to get image: {e}") from e
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(_get_image_sync, "Failed to get image")

    async def list_images(
        self,
        project_id: str,
        user_id: Optional[str],
        page: int,
        page_size: int,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List images with pagination, returns (items, total_count)."""
        def _list_images_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            actual_project_id = project_id or DEFAULT_PROJECT_ID
            try:
                cursor = conn.cursor(dictionary=True)
                where_clauses = ["project_id = %s"]
                params: List[Any] = [str(actual_project_id)]

                if user_id:
                    where_clauses.append("user_id = %s")
                    params.append(str(user_id))
                if time_from:
                    where_clauses.append("created_at >= %s")
                    params.append(time_from)
                if time_to:
                    where_clauses.append("created_at <= %s")
                    params.append(time_to)

                where_clause = ' AND '.join(where_clauses)
                
                # Get total count
                count_query = f"SELECT COUNT(*) as cnt FROM ImageStore WHERE {where_clause}"
                cursor.execute(count_query, tuple(params))
                count_row = cursor.fetchone()
                total = count_row['cnt'] if count_row else 0

                # Get paginated items
                offset = max(page - 1, 0) * page_size
                query = (
                    "SELECT project_id, user_id, image_id, caption, image_url, content_type, file_size, metadata, created_at, updated_at "
                    f"FROM ImageStore WHERE {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s"
                )
                params.extend([page_size, offset])
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                for row in rows:
                    if row.get("metadata") and isinstance(row["metadata"], str):
                        row["metadata"] = json.loads(row["metadata"])
                return rows, total
            except Exception as e:
                raise StorageError(f"Failed to list images: {e}") from e
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(_list_images_sync, "Failed to list images")

    async def reset(self, project_id: Optional[str], user_id: Optional[str] = None) -> int:
        def _reset_sync():
            pool = self._get_pool()
            conn = pool.get_connection()
            try:
                cursor = conn.cursor()
                if user_id and project_id:
                    cursor.execute(
                        "DELETE FROM ImageStore WHERE project_id = %s AND user_id = %s",
                        (str(project_id), str(user_id)),
                    )
                elif user_id:
                    cursor.execute(
                        "DELETE FROM ImageStore WHERE user_id = %s",
                        (str(user_id),),
                    )
                elif project_id:
                    cursor.execute(
                        "DELETE FROM ImageStore WHERE project_id = %s",
                        (str(project_id),),
                    )
                else:
                    cursor.execute("TRUNCATE TABLE ImageStore")
                deleted = cursor.rowcount
                conn.commit()
                return deleted
            except Exception as e:
                conn.rollback()
                raise StorageError(f"Failed to reset images: {e}") from e
            finally:
                cursor.close()
                conn.close()

        return await self._execute_sync_operation(_reset_sync, "Failed to reset images")

    async def search_by_embedding(
        self,
        project_id: str,
        query_vector: List[float],
        user_id: Optional[str] = None,
        size: int = 10,
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        try:
            filter_conditions = [
                {"term": {"project_id": project_id}},
            ]
            if user_id:
                filter_conditions.append({"term": {"user_id": user_id}})

            search_query = {
                "size": size,
                "_source": {
                    "exclude": ["feature_vector", "_searchindex_id"],
                },
                "query": {
                    "knn": {
                        "feature_vector": {
                            "vector": query_vector,
                            "filter": {
                                "bool": {
                                    "must": filter_conditions,
                                }
                            },
                            "k": size,
                        }
                    }
                },
                "ext": {
                    "lvector": {
                        "min_score": str(min_score),
                    }
                },
            }

            response = self.client.search(
                index=self.image_index_name,
                body=search_query,
                routing=project_id,
            )

            results = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                results.append({
                    "image_id": source.get("image_id"),
                    "project_id": source.get("project_id"),
                    "user_id": source.get("user_id"),
                    "caption": source.get("caption"),
                    "image_url": source.get("image_url"),
                    "content_type": source.get("content_type"),
                    "file_size": source.get("file_size"),
                    "metadata": source.get("metadata"),
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at"),
                    "similarity": hit.get("_score"),
                })
            return results
        except Exception as e:
            raise SearchStorageError(f"Failed to search images: {e}") from e

    async def search_by_caption(
        self,
        project_id: str,
        query: str,
        user_id: Optional[str] = None,
        size: int = 10,
    ) -> List[Dict[str, Any]]:
        try:
            must_conditions = [
                {"term": {"project_id": project_id}},
                {"match": {"caption": {"query": query}}},
            ]
            if user_id:
                must_conditions.append({"term": {"user_id": user_id}})

            search_query = {
                "size": size,
                "_source": {
                    "exclude": ["feature_vector", "_searchindex_id"],
                },
                "query": {
                    "bool": {
                        "must": must_conditions,
                    }
                },
            }

            response = self.client.search(
                index=self.image_index_name,
                body=search_query,
                routing=project_id,
            )

            results = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                results.append({
                    "image_id": source.get("image_id"),
                    "project_id": source.get("project_id"),
                    "user_id": source.get("user_id"),
                    "caption": source.get("caption"),
                    "image_url": source.get("image_url"),
                    "content_type": source.get("content_type"),
                    "file_size": source.get("file_size"),
                    "metadata": source.get("metadata"),
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at"),
                    "similarity": hit.get("_score"),
                })
            return results
        except Exception as e:
            raise SearchStorageError(f"Failed to search images by caption: {e}") from e

    async def hybrid_search(
        self,
        project_id: str,
        query: str,
        query_vector: List[float],
        user_id: Optional[str] = None,
        size: int = 10,
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector similarity and text matching using RRF fusion.

        This method uses Lindorm's native RRF (Reciprocal Rank Fusion) to combine:
        - KNN vector search on feature_vector
        - BM25 text search on caption (when query is provided)

        According to Lindorm documentation, the filter conditions must be separated into:
        1. RRF full-text query conditions (first bool.must) - participates in RRF fusion
        2. Pre-filter conditions (second bool.filter) - applied before vector search

        When query is empty/None, performs pure vector search with pre-filter only.
        """
        try:
            # Pre-filter conditions: project/user isolation (always applied)
            pre_filter_conditions = [
                {"term": {"project_id": project_id}},
            ]
            if user_id:
                pre_filter_conditions.append({"term": {"user_id": user_id}})

            # Build the bool.must array for the filter
            # Must contain two separate bool clauses per Lindorm documentation
            bool_must_clauses = []

            # First bool clause: RRF full-text query (participates in RRF fusion)
            # Only include caption match if query is provided
            if query:
                rrf_query_conditions = [{"match": {"caption": {"query": query}}}]
                bool_must_clauses.append({
                    "bool": {
                        "must": rrf_query_conditions
                    }
                })

            # Second bool clause: pre-filter conditions (applied before vector search)
            bool_must_clauses.append({
                "bool": {
                    "filter": pre_filter_conditions
                }
            })

            # Hybrid search query with RRF fusion
            search_query = {
                "size": size,
                "_source": {
                    "exclude": ["feature_vector", "_searchindex_id"],
                },
                "query": {
                    "knn": {
                        "feature_vector": {
                            "vector": query_vector,
                            "filter": {
                                "bool": {
                                    "must": bool_must_clauses
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
                        "filter_type": "pre_filter",
                        "rrf_knn_weight_factor": "0.5",
                        "rrf_rank_constant": "60",
                        "client_refactor": "true",
                    }
                },
            }

            response = self.client.search(
                index=self.image_index_name,
                body=search_query,
                routing=project_id,
            )

            results = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                results.append({
                    "image_id": source.get("image_id"),
                    "project_id": source.get("project_id"),
                    "user_id": source.get("user_id"),
                    "caption": source.get("caption"),
                    "image_url": source.get("image_url"),
                    "content_type": source.get("content_type"),
                    "file_size": source.get("file_size"),
                    "metadata": source.get("metadata"),
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at"),
                    "similarity": hit.get("_score"),
                })
            return results
        except Exception as e:
            raise SearchStorageError(f"Failed to hybrid search images: {e}") from e
