#!/usr/bin/env python3
"""
LindormImageStore - Image storage and multimodal retrieval interface.
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Literal

import yaml

from lindormmemobase.config import Config
from lindormmemobase.models.response import ImageData, ImageResult, ImageInput, PagedResult, ResetResult
from lindormmemobase.utils.errors import ConfigurationError, ValidationError
from lindormmemobase.utils.image_utils import (
    ensure_bytes,
    infer_content_type_from_url,
    infer_content_type_from_bytes,
    build_data_url,
)
from lindormmemobase.multimodal import get_multimodal_embedding, generate_image_caption
from lindormmemobase.core.storage.images import get_lindorm_image_storage


SearchMode = Literal["caption", "embedding", "hybrid"]


class LindormImageStore:
    """
    Main interface for image storage and multimodal search.
    """

    def __init__(self, config: Optional[Config] = None):
        try:
            self.config = config if config is not None else Config.load_config()
            self._init_storage_sync()
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}") from e

    def _init_storage_sync(self):
        from .core.storage.manager import StorageManager
        if not StorageManager.is_initialized():
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(StorageManager.initialize(self.config))
                else:
                    loop.run_until_complete(StorageManager.initialize(self.config))
            except RuntimeError:
                asyncio.run(StorageManager.initialize(self.config))

    async def initialize_storage(self):
        from .core.storage.manager import StorageManager
        if not StorageManager.is_initialized():
            await StorageManager.initialize(self.config)

    @classmethod
    def from_yaml_file(cls, config_file_path: Union[str, Path]) -> "LindormImageStore":
        try:
            config_path = Path(config_file_path)
            if not config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")
            config = Config.from_yaml_file(config_path)
            return cls(config)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration from file: {e}") from e

    @classmethod
    def from_config(cls, **kwargs) -> "LindormImageStore":
        try:
            from dataclasses import fields

            valid_fields = {f.name for f in fields(Config)}
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
            config = Config(**filtered_kwargs)
            return cls(config)
        except Exception as e:
            raise ConfigurationError(f"Failed to create configuration from parameters: {e}") from e

    async def add_image(
        self,
        project_id: str,
        user_id: str,
        image_url: Optional[str] = None,
        image_data: Optional[Union[bytes, bytearray, memoryview]] = None,
        caption: Optional[str] = None,
        auto_generate_caption: bool = True,
        generate_embedding: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        file_size: Optional[int] = None,
        image_id: Optional[str] = None,
    ) -> ImageResult:
        if not project_id:
            raise ValidationError("project_id is required")
        if not user_id:
            raise ValidationError("user_id is required")
        if not image_url and image_data is None:
            raise ValidationError("image_url or image_data is required")

        image_bytes = None
        if image_data is not None:
            image_bytes = ensure_bytes(image_data)

        storage_type = self.config.image_storage_type
        if storage_type == "url" and not image_url:
            raise ValidationError("image_url is required when image_storage_type is 'url'")
        if storage_type == "binary" and image_bytes is None:
            raise ValidationError("image_data is required when image_storage_type is 'binary'")

        if content_type is None:
            content_type = infer_content_type_from_url(image_url) if image_url else None
            if content_type is None and image_bytes is not None:
                content_type = infer_content_type_from_bytes(image_bytes)

        if file_size is None and image_bytes is not None:
            file_size = len(image_bytes)

        image_ref = image_url
        if image_ref is None and image_bytes is not None:
            image_ref = build_data_url(image_bytes, content_type)

        if caption is None and auto_generate_caption and image_ref:
            caption = await generate_image_caption(image_ref, config=self.config)

        feature_vector = None
        if generate_embedding:
            if image_ref:
                feature_vector = await get_multimodal_embedding(
                    "image",
                    image_ref,
                    model=self.config.multimodal_embedding_model,
                    config=self.config,
                )
            elif caption:
                feature_vector = await get_multimodal_embedding(
                    "text",
                    caption,
                    model=self.config.multimodal_embedding_model,
                    config=self.config,
                )
            else:
                raise ValidationError("Cannot generate embedding without image or caption")

        if storage_type == "url":
            image_bytes_to_store = None
        elif storage_type == "binary":
            image_bytes_to_store = image_bytes
        else:
            image_bytes_to_store = image_bytes

        storage = get_lindorm_image_storage(self.config)
        result_image_id = await storage.store_image(
            project_id=project_id,
            user_id=user_id,
            image_id=image_id or str(uuid.uuid4()),
            caption=caption,
            image_url=image_url,
            image_data=image_bytes_to_store,
            feature_vector=feature_vector,
            content_type=content_type,
            file_size=file_size,
            metadata=metadata,
        )
        return ImageResult(image_id=result_image_id, caption=caption)

    async def batch_add_images(
        self,
        project_id: str,
        user_id: str,
        images: List[ImageInput],
        auto_generate_caption: bool = True,
        generate_embedding: bool = True,
        max_concurrency: int = 5,
    ) -> List[ImageResult]:
        """
        Batch add multiple images with concurrent processing.
        
        Args:
            project_id: Project identifier
            user_id: User identifier
            images: List of ImageInput objects
            auto_generate_caption: Whether to auto-generate captions
            generate_embedding: Whether to generate embeddings
            max_concurrency: Maximum concurrent operations (default: 5)
            
        Returns:
            List of ImageResult for each image
        """
        if not project_id:
            raise ValidationError("project_id is required")
        if not user_id:
            raise ValidationError("user_id is required")
        if not images:
            return []

        semaphore = asyncio.Semaphore(max_concurrency)

        async def process_single_image(img: ImageInput) -> ImageResult:
            async with semaphore:
                try:
                    return await self.add_image(
                        project_id=project_id,
                        user_id=user_id,
                        image_url=img.image_url,
                        image_data=img.image_data,
                        caption=img.caption,
                        auto_generate_caption=auto_generate_caption,
                        generate_embedding=generate_embedding,
                        metadata=img.metadata,
                    )
                except Exception as e:
                    return ImageResult(
                        image_id="",
                        caption=None,
                        success=False,
                        error=str(e),
                    )

        tasks = [process_single_image(img) for img in images]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def get_image(
        self,
        project_id: str,
        user_id: str,
        image_id: str,
        include_data: bool = False,
    ) -> Optional[ImageData]:
        storage = get_lindorm_image_storage(self.config)
        row = await storage.get_image(project_id, user_id, image_id, include_data=include_data)
        if row is None:
            return None
        return ImageData(**row)

    async def update_image(
        self,
        project_id: str,
        user_id: str,
        image_id: str,
        caption: Optional[str] = None,
        auto_generate_caption: bool = False,
        regenerate_embedding: bool = False,
        image_url: Optional[str] = None,
        image_data: Optional[Union[bytes, bytearray, memoryview]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> ImageResult:
        if not project_id:
            raise ValidationError("project_id is required")
        if not user_id:
            raise ValidationError("user_id is required")
        if not image_id:
            raise ValidationError("image_id is required")

        image_bytes = None
        if image_data is not None:
            image_bytes = ensure_bytes(image_data)

        if content_type is None:
            content_type = infer_content_type_from_url(image_url) if image_url else None
            if content_type is None and image_bytes is not None:
                content_type = infer_content_type_from_bytes(image_bytes)

        if file_size is None and image_bytes is not None:
            file_size = len(image_bytes)

        storage = get_lindorm_image_storage(self.config)

        image_ref = image_url
        existing_row = None
        if image_ref is None and image_bytes is not None:
            image_ref = build_data_url(image_bytes, content_type)

        if (auto_generate_caption and caption is None) or regenerate_embedding:
            if image_ref is None:
                existing_row = await storage.get_image(project_id, user_id, image_id, include_data=True)
                if existing_row:
                    stored_data = existing_row.get("image_data")
                    stored_url = existing_row.get("image_url")
                    if stored_data:
                        image_ref = build_data_url(
                            stored_data,
                            existing_row.get("content_type") or content_type,
                        )
                    else:
                        image_ref = stored_url

        if caption is None and auto_generate_caption and image_ref:
            caption = await generate_image_caption(image_ref, config=self.config)

        feature_vector = None
        if regenerate_embedding:
            if image_ref:
                feature_vector = await get_multimodal_embedding(
                    "image",
                    image_ref,
                    model=self.config.multimodal_embedding_model,
                    config=self.config,
                )
            elif caption:
                feature_vector = await get_multimodal_embedding(
                    "text",
                    caption,
                    model=self.config.multimodal_embedding_model,
                    config=self.config,
                )
            else:
                raise ValidationError("Cannot regenerate embedding without image or caption")

        result_image_id = await storage.update_image(
            project_id=project_id,
            user_id=user_id,
            image_id=image_id,
            caption=caption,
            image_url=image_url,
            image_data=image_bytes,
            feature_vector=feature_vector,
            content_type=content_type,
            file_size=file_size,
            metadata=metadata,
        )
        return ImageResult(image_id=result_image_id, caption=caption)

    async def delete_image(self, project_id: str, user_id: str, image_id: str) -> bool:
        storage = get_lindorm_image_storage(self.config)
        await storage.delete_image(project_id, user_id, image_id)
        return True

    async def list_images(
        self,
        project_id: str,
        user_id: Optional[str],
        page: int = 1,
        page_size: int = 20,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
    ) -> PagedResult[ImageData]:
        storage = get_lindorm_image_storage(self.config)
        rows, total = await storage.list_images(project_id, user_id, page, page_size, time_from, time_to)
        items = [ImageData(**row) for row in rows]
        return PagedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total,
        )

    async def search_by_text(
        self,
        project_id: str,
        query: str,
        user_id: Optional[str] = None,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        search_mode: SearchMode = "hybrid",
    ) -> List[ImageData]:
        storage = get_lindorm_image_storage(self.config)
        top_k = top_k or self.config.image_search_default_top_k
        min_score = min_score if min_score is not None else self.config.image_search_min_score

        if search_mode == "caption":
            results = await storage.search_by_caption(project_id, query, user_id, size=top_k)
            return [ImageData(**row) for row in results]

        query_vector = await get_multimodal_embedding(
            "text",
            query,
            model=self.config.multimodal_embedding_model,
            config=self.config,
        )

        if search_mode == "hybrid":
            results = await storage.hybrid_search(
                project_id,
                query,
                query_vector,
                user_id=user_id,
                size=top_k,
                min_score=min_score,
            )
            return [ImageData(**row) for row in results]

        results = await storage.search_by_embedding(
            project_id,
            query_vector,
            user_id=user_id,
            size=top_k,
            min_score=min_score,
        )
        return [ImageData(**row) for row in results]

    async def search_by_image(
        self,
        project_id: str,
        image_url: Optional[str] = None,
        image_data: Optional[Union[bytes, bytearray, memoryview]] = None,
        user_id: Optional[str] = None,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[ImageData]:
        if not image_url and image_data is None:
            raise ValidationError("image_url or image_data is required")

        image_bytes = None
        if image_data is not None:
            image_bytes = ensure_bytes(image_data)

        content_type = infer_content_type_from_url(image_url) if image_url else None
        if content_type is None and image_bytes is not None:
            content_type = infer_content_type_from_bytes(image_bytes)

        image_ref = image_url
        if image_ref is None and image_bytes is not None:
            image_ref = build_data_url(image_bytes, content_type)

        query_vector = await get_multimodal_embedding(
            "image",
            image_ref,
            model=self.config.multimodal_embedding_model,
            config=self.config,
        )

        storage = get_lindorm_image_storage(self.config)
        top_k = top_k or self.config.image_search_default_top_k
        min_score = min_score if min_score is not None else self.config.image_search_min_score
        results = await storage.search_by_embedding(
            project_id,
            query_vector,
            user_id=user_id,
            size=top_k,
            min_score=min_score,
        )
        return [ImageData(**row) for row in results]

    async def reset(self, project_id: str, user_id: Optional[str] = None) -> ResetResult:
        storage = get_lindorm_image_storage(self.config)
        deleted_count = await storage.reset(project_id, user_id)
        return ResetResult(deleted_count=deleted_count)
