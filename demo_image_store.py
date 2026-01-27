#!/usr/bin/env python3
"""
Demo for LindormImageStore - Image storage and multimodal retrieval.

This demo showcases:
1. Adding images (URL only)
2. Auto-generating captions with Vision-Language models
3. Generating multimodal embeddings
4. Three search modes: caption, embedding, hybrid
5. Searching by image (image-to-image retrieval)
6. Batch operations
7. Listing and pagination

Prerequisites:
-------------
1. Copy .env.example to .env and fill in your credentials
2. Ensure you have:
   - Lindorm database (table + search) access
   - Multimodal embedding service (LindormAI or Dashscope)
   - Optional: Vision-Language model for caption generation

Configuration:
-------------
In your .env file, set:
- MEMOBASE_LINDORM_*: Lindorm database credentials
- MEMOBASE_MULTIMODAL_EMBEDDING_PROVIDER: lindormai or dashscope
- MEMOBASE_MULTIMODAL_EMBEDDING_BASE_URL: Embedding service endpoint
- MEMOBASE_VL_MODEL_PROVIDER: lindormai or dashscope (for caption generation)
- image_storage_type: url (in config.yaml)

Example .env for multimodal features:
-----------------------------------------
# Multimodal Embedding (required)
MEMOBASE_MULTIMODAL_EMBEDDING_PROVIDER=lindormai
MEMOBASE_MULTIMODAL_EMBEDDING_BASE_URL=http://your-lindorm-ai-url:9002/dashscope/compatible-mode/v1

# Vision-Language Model (optional, for auto-caption)
MEMOBASE_VL_MODEL_PROVIDER=lindormai
MEMOBASE_VL_MODEL_BASE_URL=http://your-lindorm-ai-url:9002/dashscope/compatible-mode/v1

Usage:
------
python demo_image_store.py
"""

import asyncio
from datetime import datetime
from typing import Optional

from lindormmemobase.image_store import LindormImageStore
from lindormmemobase.models.enums import SearchMode, ImageStorageType
from lindormmemobase.utils.errors import LindormMemobaseError


# Demo configuration
PROJECT_ID = "demo_project"
USER_ID = "demo_user"


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def demo_add_image_from_url(store: LindormImageStore) -> Optional[str]:
    """Demo: Add image from URL."""
    print_section("1. Add Image from URL")

    image_url = "https://img.alicdn.com/imgextra/i3/O1CN01rdstgY1uiZWt8gqSL_!!6000000006071-0-tps-1970-356.jpg"
    print(f"Adding image from URL: {image_url}")

    try:
        result = await store.add_image(
            project_id=PROJECT_ID,
            user_id=USER_ID,
            image_url=image_url,
            caption="Fresh fruits image",
            auto_generate_caption=True,  # Will override the caption above
            generate_embedding=True,
            metadata={"source": "demo_url", "added_at": datetime.utcnow().isoformat()},
        )
        print(f"✅ Added: image_id={result.image_id}")
        print(f"   Caption: {result.caption}")
        return result.image_id
    except LindormMemobaseError as e:
        print(f"❌ Error: {e}")
        return None


async def demo_get_image(store: LindormImageStore, image_id: str) -> None:
    """Demo: Retrieve image metadata."""
    print_section("2. Get Image Metadata")

    try:
        image = await store.get_image(
            project_id=PROJECT_ID,
            user_id=USER_ID,
            image_id=image_id,
        )
        if image:
            print(f"✅ Found image: {image.image_id}")
            print(f"   Caption: {image.caption}")
            print(f"   Content-Type: {image.content_type}")
            print(f"   File Size: {image.file_size} bytes")
            print(f"   Created At: {image.created_at}")
            print(f"   Metadata: {image.metadata}")
        else:
            print("❌ Image not found")
    except LindormMemobaseError as e:
        print(f"❌ Error: {e}")


async def demo_search_by_text(store: LindormImageStore) -> None:
    """Demo: Three different search modes."""
    print_section("3. Search by Text (Three Modes)")

    queries = [
        "fruits",  # Should match the URL image
        "sunset",  # No match expected
    ]

    for mode in [SearchMode.CAPTION, SearchMode.EMBEDDING, SearchMode.HYBRID]:
        print(f"\n--- Search Mode: {mode.value} ---")
        for query in queries:
            print(f"\nQuery: '{query}'")
            try:
                results = await store.search_by_text(
                    project_id=PROJECT_ID,
                    query=query,
                    user_id=USER_ID,
                    search_mode=mode,
                    top_k=3,
                )
                print(f"   Found {len(results)} results")
                for r in results[:2]:
                    print(f"   - {r.image_id}: similarity={r.similarity:.3f}, caption={r.caption[:30] if r.caption else 'None'}...")
            except LindormMemobaseError as e:
                print(f"   ❌ Error: {e}")


async def demo_search_by_image(store: LindormImageStore, image_id: str) -> None:
    """Demo: Image-to-image search using vector similarity."""
    print_section("4. Search by Image (Image-to-Image)")

    try:
        image = await store.get_image(PROJECT_ID, USER_ID, image_id)
        if not image or not image.image_url:
            print("❌ Image URL not available for search")
            return

        print("Searching for similar images using URL...")

        results = await store.search_by_image(
            project_id=PROJECT_ID,
            image_url=image.image_url,
            user_id=USER_ID,
            top_k=3,
        )

        print(f"✅ Found {len(results)} similar images")
        for r in results[:3]:
            print(f"   - {r.image_id}: similarity={r.similarity:.3f}, caption={r.caption[:30] if r.caption else 'None'}...")
    except LindormMemobaseError as e:
        print(f"❌ Error: {e}")


async def demo_batch_add_images(store: LindormImageStore) -> None:
    """Demo: Batch add multiple images with concurrency control."""
    print_section("5. Batch Add Images")

    from lindormmemobase.models.response import ImageInput

    # Create test inputs
    test_inputs = [
        ImageInput(
            image_url="https://img.alicdn.com/imgextra/i3/O1CN01rdstgY1uiZWt8gqSL_!!6000000006071-0-tps-1970-356.jpg",
            metadata={"category": "fruit"},
        ),
    ]

    print(f"Adding {len(test_inputs)} images (max_concurrency=2)...")

    try:
        results = await store.batch_add_images(
            project_id=PROJECT_ID,
            user_id=USER_ID,
            images=test_inputs,
            auto_generate_caption=True,
            generate_embedding=True,
            max_concurrency=2,
        )

        for i, result in enumerate(results):
            status = "✅" if result.success else "❌"
            print(f"{status} [{i+1}] image_id={result.image_id}, success={result.success}")
            if not result.success:
                print(f"      Error: {result.error}")
            elif result.image_id:
                print(f"      Caption: {result.caption[:40] if result.caption else 'None'}...")
    except LindormMemobaseError as e:
        print(f"❌ Batch error: {e}")


async def demo_list_images(store: LindormImageStore) -> None:
    """Demo: List images with pagination."""
    print_section("6. List Images with Pagination")

    page = 1
    page_size = 5

    try:
        result = await store.list_images(
            project_id=PROJECT_ID,
            user_id=USER_ID,
            page=page,
            page_size=page_size,
        )

        print(f"Page {result.page}/{(result.total + page_size - 1) // page_size}")
        print(f"Total: {result.total} images")
        print(f"Showing {len(result.items)} results:")
        print(f"Has more: {result.has_more}")

        for img in result.items:
            caption_preview = (img.caption[:30] + "...") if img.caption and len(img.caption) > 30 else (img.caption or "No caption")
            print(f"  - {img.image_id}: {caption_preview}")
    except LindormMemobaseError as e:
        print(f"❌ Error: {e}")


async def demo_update_image(store: LindormImageStore, image_id: str) -> None:
    """Demo: Update image caption and regenerate embedding."""
    print_section("7. Update Image")

    new_caption = "Updated: A small red pixel for testing"
    print(f"Updating image {image_id}...")

    try:
        result = await store.update_image(
            project_id=PROJECT_ID,
            user_id=USER_ID,
            image_id=image_id,
            caption=new_caption,
        )
        print(f"✅ Updated: {result.image_id}")

        # Verify the update
        image = await store.get_image(PROJECT_ID, USER_ID, image_id)
        print(f"   New caption: {image.caption}")
    except LindormMemobaseError as e:
        print(f"❌ Error: {e}")


async def demo_reset(store: LindormImageStore) -> None:
    """Demo: Reset (delete all images for a user/project)."""
    print_section("8. Reset Demo Data")

    print("⚠️  This will delete all demo images.")
    print("    Comment out this function call if you want to keep the data.")

    # Uncomment to actually delete:
    # try:
    #     result = await store.reset(project_id=PROJECT_ID, user_id=USER_ID)
    #     print(f"✅ Deleted {result.deleted_count} images")
    # except LindormMemobaseError as e:
    #     print(f"❌ Error: {e}")

    print("(Skipped - reset is commented out)")


async def check_prerequisites(store: LindormImageStore) -> bool:
    """Check if required configuration is present."""
    print_section("Checking Prerequisites")

    all_good = True

    # Check Lindorm connection
    if not store.config.lindorm_table_host:
        print("❌ MEMOBASE_LINDORM_TABLE_HOST not set")
        all_good = False
    else:
        print(f"✅ Lindorm Table: {store.config.lindorm_table_host}:{store.config.lindorm_table_port}")

    if not store.config.lindorm_search_host:
        print("❌ MEMOBASE_LINDORM_SEARCH_HOST not set")
        all_good = False
    else:
        print(f"✅ Lindorm Search: {store.config.lindorm_search_host}:{store.config.lindorm_search_port}")

    # Check multimodal embedding config
    if not (store.config.multimodal_embedding_base_url or store.config.embedding_base_url or store.config.llm_base_url):
        print("❌ Multimodal embedding base URL not set")
        print("   Set MEMOBASE_MULTIMODAL_EMBEDDING_BASE_URL or use LLM_BASE_URL")
        all_good = False
    else:
        print(f"✅ Multimodal Embedding: {store.config.multimodal_embedding_provider}")

    # Check VL model config (optional, for auto-caption)
    if not (store.config.vl_model_base_url or store.config.llm_base_url):
        print("⚠️  VL model base URL not set (auto-caption will be disabled)")
        print("   Set MEMOBASE_VL_MODEL_BASE_URL or use LLM_BASE_URL for auto-caption")

    # Check storage type
    print(f"✅ Storage Type: {store.config.image_storage_type}")
    # Note: image_storage_type='url' stores external URLs directly, no OSS needed

    return all_good


async def main() -> None:
    """Main demo function."""
    print("\n" + "=" * 60)
    print("  LindormImageStore Demo")
    print("=" * 60)

    # Initialize store
    store = LindormImageStore.from_yaml_file("config.yaml")

    # Check prerequisites
    if not await check_prerequisites(store):
        print("\n❌ Prerequisites not met. Please configure your environment.")
        print("   Copy .env.example to .env and fill in your credentials.")
        return

    # Initialize storage (create tables/indices if needed)
    print("\nInitializing storage (this may take a moment on first run)...")
    try:
        await store.initialize_storage()
        print("✅ Storage initialized")
    except LindormMemobaseError as e:
        print(f"❌ Storage initialization failed: {e}")
        return

    # Run demos
    url_image_id = await demo_add_image_from_url(store)
    reference_image_id = url_image_id

    if reference_image_id:
        await demo_get_image(store, reference_image_id)
        await demo_search_by_text(store)
        await demo_search_by_image(store, reference_image_id)
        await demo_update_image(store, reference_image_id)

    await demo_batch_add_images(store)
    await demo_list_images(store)
    await demo_reset(store)

    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
