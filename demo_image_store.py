#!/usr/bin/env python3
"""
Demo for LindormImageStore image storage and multimodal retrieval.

Usage:
  1) Ensure config.yaml or env vars include:
     - lindorm_table_* / lindorm_search_* settings
     - multimodal_embedding_provider, multimodal_embedding_model
     - (optional) vl_model_provider / vl_model for caption
  2) Run:
     python demo_image_store.py

Notes:
  - This script does not download images; it uses a URL string.
  - Replace IMAGE_URL with your OSS/S3 URL.
"""

import asyncio
from datetime import datetime

from lindormmemobase.image_store import LindormImageStore


PROJECT_ID = "demo_project"
USER_ID = "demo_user"
IMAGE_URL = "https://example.com/your-image.jpg"


async def main() -> None:
    store = LindormImageStore.from_yaml_file("config.yaml")
    await store.initialize_storage()

    print("Adding image...")
    image_id = await store.add_image(
        project_id=PROJECT_ID,
        user_id=USER_ID,
        image_url=IMAGE_URL,
        caption=None,
        auto_generate_caption=True,
        generate_embedding=True,
        metadata={"source": "demo", "ingested_at": datetime.utcnow().isoformat()},
    )
    print(f"Added image_id: {image_id}")

    print("Get image (without data)...")
    image = await store.get_image(PROJECT_ID, USER_ID, image_id, include_data=False)
    print(image)

    print("Search by text...")
    results = await store.search_by_text(
        project_id=PROJECT_ID,
        query="person outdoors",
        user_id=USER_ID,
        search_mode="embedding",
    )
    print(f"Search results: {len(results)}")
    for item in results[:3]:
        print(item.image_id, item.similarity, item.caption)

    print("List images...")
    images = await store.list_images(PROJECT_ID, USER_ID, page=1, page_size=5)
    print(f"List images: {len(images)}")

    # Optional: delete
    # await store.delete_image(PROJECT_ID, USER_ID, image_id)


if __name__ == "__main__":
    asyncio.run(main())
