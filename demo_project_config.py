#!/usr/bin/env python3
"""
Demo: Project-Specific Profile Configuration (按 projectId 动态配置 topic/subtopic)

This demo showcases how to configure different topic/subtopic extraction rules
for different projects using the SDK API.

Features demonstrated:
1. Setup project configs using SDK API (set_project_config)
2. Automatic config loading by project_id during extract_memories()
3. Three-tier priority: explicit profile_config > DB config > config.yaml fallback
4. CRUD operations: read, update, delete project configs
5. Cache management for performance
"""

import asyncio
from datetime import datetime
from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig


async def demo_project_specific_config():
    """Demonstrate project-specific profile configuration."""

    print("=" * 80)
    print("Project-Specific Profile Configuration Demo")
    print("按项目动态配置 Topic/Subtopic 演示")
    print("=" * 80)
    print()

    # Initialize Memobase
    print("📌 Step 1: Initialize LindormMemobase")
    config = Config.from_yaml_file("config.yaml")
    memobase = LindormMemobase(config)

    user_id = f"demo_user_{int(datetime.now().timestamp())}"
    print(f"✓ User ID: {user_id}")
    print()

    # ========== Part 0: Setup Project Configs via SDK API ==========
    print("=" * 80)
    print("Part 0: Setup Project Configs via SDK API")
    print("=" * 80)
    print()
    print("Creating project-specific configurations using set_project_config()...")
    print()

    # Setup Education App config
    print("📝 Setting up config for 'education_app'...")
    education_config = ProfileConfig(
        language="zh",
        profile_strict_mode=True,
        overwrite_user_profiles=[
            {
                "topic": "学习偏好",
                "description": "用户的学习习惯和偏好",
                "sub_topics": [
                    {"name": "学习时间", "description": "喜欢在什么时间学习"},
                    {"name": "学习风格", "description": "视觉/听觉/动手等学习偏好"},
                    {"name": "学习科目", "description": "擅长或感兴趣的科目"}
                ]
            },
            {
                "topic": "学习进度",
                "description": "各科目的学习进展",
                "sub_topics": [
                    {"name": "数学水平", "description": "数学的掌握程度"},
                    {"name": "英语水平", "description": "英语的掌握程度"},
                    {"name": "编程能力", "description": "编程技能的进展"}
                ]
            }
        ]
    )

    try:
        await memobase.set_project_config("education_app", education_config)
        print("  ✓ Config saved for 'education_app'")
    except Exception as e:
        print(f"  ⚠️  Skipped: {e}")
        print("  (In production with valid DB connection, this would save to database)")
    print()

    # Setup E-commerce App config
    print("📝 Setting up config for 'ecommerce_app'...")
    ecommerce_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[
            {
                "topic": "购物偏好",
                "description": "用户的购物习惯",
                "sub_topics": [
                    {"name": "常买品类", "description": "经常购买的商品类别"},
                    {"name": "价格敏感度", "description": "对价格的关注程度"},
                    {"name": "购物频率", "description": "购物频次习惯"}
                ]
            },
            {
                "topic": "收货地址",
                "description": "常用收货地址信息",
                "sub_topics": [
                    {"name": "家庭地址", "description": "家庭住址"},
                    {"name": "公司地址", "description": "公司地址"}
                ]
            }
        ]
    )

    try:
        await memobase.set_project_config("ecommerce_app", ecommerce_config)
        print("  ✓ Config saved for 'ecommerce_app'")
    except Exception as e:
        print(f"  ⚠️  Skipped: {e}")
    print()

    print("✅ Project configs setup complete!")
    print("  Now extract_memories() will automatically use these configs.")
    print()

    # ========== Part 1: Education App with custom DB config ==========
    print("=" * 80)
    print("Part 1: Education App - Custom Learning Profile Config")
    print("=" * 80)
    print()
    print("Scenario: User is using an education app (project_id='education_app')")
    print("Expected: Extract learning-related profiles (学习偏好, 学习进度)")
    print()

    education_conversation = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="我每天晚上8点以后学习，喜欢看视频教程。最近在学Python和机器学习。"
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="很好的学习习惯！晚上学习确实效率高。"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="是的，我数学基础不错，但英语还需要加强。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    print("💬 Extracting memories with project_id='education_app'...")
    result_education = await memobase.extract_memories(
        user_id=user_id,
        blobs=[education_conversation],
        project_id="education_app"
        # Config automatically loaded from DB
    )

    print(f"✓ Extraction completed")
    print(f"  - Event ID: {result_education.event_id}")
    print(f"  - Profiles added: {len(result_education.add_profiles)}")
    print(f"  - Profiles updated: {len(result_education.update_profiles)}")
    print()

    print("📋 Extracted profiles for education_app:")
    profiles_education = await memobase.get_user_profiles(
        user_id=user_id,
        project_id="education_app"
    )
    if profiles_education:
        for profile in profiles_education:
            print(f"  【{profile.topic}】")
            for subtopic, entry in profile.subtopics.items():
                print(f"    - {subtopic}: {entry.content}")
    else:
        print("  (No profiles - DB config may not be set up)")
    print()

    # ========== Part 2: E-commerce App with different config ==========
    print("=" * 80)
    print("Part 2: E-commerce App - Shopping Profile Config")
    print("=" * 80)
    print()
    print("Scenario: User is using an e-commerce app (project_id='ecommerce_app')")
    print("Expected: Extract shopping-related profiles (购物偏好, 收货地址)")
    print()

    ecommerce_conversation = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="我要买一本Python编程书，送到我的公司地址。"
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="好的，请提供您的收货地址。"
            ),
            OpenAICompatibleMessage(
                role="user",
                content="上海市浦东新区张江高科技园区XXX号。我经常买技术类书籍。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    print("💬 Extracting memories with project_id='ecommerce_app'...")
    result_ecommerce = await memobase.extract_memories(
        user_id=user_id,
        blobs=[ecommerce_conversation],
        project_id="ecommerce_app"
    )

    print(f"✓ Extraction completed")
    print(f"  - Event ID: {result_ecommerce.event_id}")
    print(f"  - Profiles added: {len(result_ecommerce.add_profiles)}")
    print(f"  - Profiles updated: {len(result_ecommerce.update_profiles)}")
    print()

    print("📋 Extracted profiles for ecommerce_app:")
    profiles_ecommerce = await memobase.get_user_profiles(
        user_id=user_id,
        project_id="ecommerce_app"
    )
    if profiles_ecommerce:
        for profile in profiles_ecommerce:
            print(f"  【{profile.topic}】")
            for subtopic, entry in profile.subtopics.items():
                print(f"    - {subtopic}: {entry.content}")
    else:
        print("  (No profiles - DB config may not be set up)")
    print()

    # ========== Part 3: Fallback to config.yaml ==========
    print("=" * 80)
    print("Part 3: Fallback to config.yaml (No DB Config)")
    print("=" * 80)
    print()
    print("Scenario: Using a project without DB config (project_id='unknown_app')")
    print("Expected: Falls back to config.yaml default configuration")
    print()

    unknown_conversation = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="我叫张三，是一名软件工程师，住在北京。"
            ),
            OpenAICompatibleMessage(
                role="assistant",
                content="你好张三！很高兴认识你。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    print("💬 Extracting memories with project_id='unknown_app' (no DB config)...")
    result_unknown = await memobase.extract_memories(
        user_id=user_id,
        blobs=[unknown_conversation],
        project_id="unknown_app"
        # Falls back to config.yaml
    )

    print(f"✓ Extraction completed (used config.yaml fallback)")
    print(f"  - Event ID: {result_unknown.event_id}")
    print(f"  - Profiles added: {len(result_unknown.add_profiles)}")
    print()

    # ========== Part 4: Explicit profile_config (highest priority) ==========
    print("=" * 80)
    print("Part 4: Explicit ProfileConfig (Highest Priority)")
    print("=" * 80)
    print()
    print("Scenario: Passing explicit profile_config parameter")
    print("Expected: Uses provided config, ignores DB and config.yaml")
    print()

    custom_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[
            {
                "topic": "临时主题",
                "description": "这是一个临时主题",
                "sub_topics": [
                    {"name": "临时子主题1"},
                    {"name": "临时子主题2"}
                ]
            }
        ]
    )

    print("💬 Extracting memories with explicit profile_config...")
    result_custom = await memobase.extract_memories(
        user_id=user_id,
        blobs=[unknown_conversation],
        profile_config=custom_config,  # Explicit config - highest priority
        project_id="education_app"  # Even though DB has config, explicit wins
    )

    print(f"✓ Extraction completed (used explicit profile_config)")
    print(f"  - Event ID: {result_custom.event_id}")
    print(f"  - Profiles added: {len(result_custom.add_profiles)}")
    print()

    # ========== Part 5: Read project config ==========
    print("=" * 80)
    print("Part 5: Read Project Config")
    print("=" * 80)
    print()
    print("Scenario: Reading back the config stored in DB")
    print()

    print("📖 Reading config for 'education_app'...")
    try:
        saved_config = await memobase.get_project_config("education_app")
        if saved_config:
            print("✓ Retrieved config from DB:")
            print(f"  - Language: {saved_config.language}")
            print(f"  - Strict mode: {saved_config.profile_strict_mode}")
            if saved_config.overwrite_user_profiles:
                print(f"  - Topics:")
                for topic in saved_config.overwrite_user_profiles:
                    print(f"    • {topic['topic']}")
                    if 'sub_topics' in topic:
                        for st in topic['sub_topics']:
                            print(f"      - {st.get('name', st)}")
        else:
            print("ℹ️  No config found (may have been deleted or DB not available)")
    except Exception as e:
        print(f"⚠️  Skipped: {e}")
    print()

    # ========== Part 6: Update project config ==========
    print("=" * 80)
    print("Part 6: Update Project Config")
    print("=" * 80)
    print()
    print("Scenario: Modifying an existing project's config")
    print()

    print("📝 Updating config for 'education_app' (adding new topics)...")
    updated_education_config = ProfileConfig(
        language="zh",
        profile_strict_mode=True,
        overwrite_user_profiles=[
            {
                "topic": "学习偏好",
                "sub_topics": [
                    {"name": "学习时间"},
                    {"name": "学习风格"},
                    {"name": "学习科目"},
                    {"name": "学习设备"}  # New subtopic
                ]
            },
            {
                "topic": "学习进度",
                "sub_topics": [
                    {"name": "数学水平"},
                    {"name": "英语水平"},
                    {"name": "编程能力"}
                ]
            },
            {
                "topic": "学习计划",  # New topic
                "sub_topics": [
                    {"name": "短期目标"},
                    {"name": "长期目标"}
                ]
            }
        ]
    )

    try:
        await memobase.set_project_config("education_app", updated_education_config)
        print("✓ Config updated for 'education_app'")
        print("  (New topic '学习计划' and subtopic '学习设备' added)")
    except Exception as e:
        print(f"⚠️  Skipped: {e}")
    print()

    # ========== Part 7: Delete project config ==========
    print("=" * 80)
    print("Part 7: Delete Project Config")
    print("=" * 80)
    print()
    print("Scenario: Removing a project's config (will fallback to config.yaml)")
    print()

    print("🗑️  Deleting config for 'ecommerce_app'...")
    try:
        deleted = await memobase.delete_project_config("ecommerce_app")
        if deleted:
            print("✓ Config deleted for 'ecommerce_app'")
            print("  Future calls will fall back to config.yaml")
        else:
            print("ℹ️  No config found to delete")
    except Exception as e:
        print(f"⚠️  Skipped: {e}")
    print()

    # ========== Part 8: Cache management ==========
    print("=" * 80)
    print("Part 8: Cache Management")
    print("=" * 80)
    print()
    print("Scenario: Manually invalidating cache after updating DB config")
    print()

    print("💡 Invalidate cache for a specific project:")
    print("  await memobase.invalidate_project_config_cache('education_app')")
    await memobase.invalidate_project_config_cache("education_app")
    print("  ✓ Cache invalidated for 'education_app'")
    print()

    print("💡 Invalidate all cache:")
    print("  await memobase.invalidate_project_config_cache()  # No parameter")
    await memobase.invalidate_project_config_cache()
    print("  ✓ All cache invalidated")
    print()

    # ========== Summary ==========
    print("=" * 80)
    print("Summary: Complete API Usage")
    print("=" * 80)
    print()
    print("CRUD Operations:")
    print()
    print("  CREATE / UPDATE:")
    print("    await memobase.set_project_config(project_id, profile_config)")
    print()
    print("  READ:")
    print("    config = await memobase.get_project_config(project_id)")
    print()
    print("  DELETE:")
    print("    deleted = await memobase.delete_project_config(project_id)")
    print()
    print("  CACHE INVALIDATION:")
    print("    await memobase.invalidate_project_config_cache(project_id)")
    print("    await memobase.invalidate_project_config_cache()  # All")
    print()
    print("Usage in extract_memories():")
    print()
    print("  # Automatic config loading by project_id")
    print("  result = await memobase.extract_memories(")
    print("      user_id='user123',")
    print("      blobs=[chat_blob],")
    print("      project_id='education_app'  # Loads DB config automatically")
    print("  )")
    print()
    print("Configuration Priority (highest to lowest):")
    print()
    print("  1️⃣  Explicit profile_config parameter")
    print("  2️⃣  Database config (ProjectProfileConfigs table)")
    print("  3️⃣  config.yaml fallback")
    print()
    print("Demo completed successfully! 🎉")
    print("=" * 80)


async def demo_buffer_with_project_config():
    """Demo showing how buffer processing also uses project-specific configs."""

    print("=" * 80)
    print("Bonus: Buffer Processing with Project Configs")
    print("=" * 80)
    print()

    config = Config.from_yaml_file("config.yaml")
    memobase = LindormMemobase(config)

    user_id = f"buffer_user_{int(datetime.now().timestamp())}"
    project_id = "education_app"

    print(f"User ID: {user_id}")
    print(f"Project ID: {project_id}")
    print()

    # Setup config first
    print("📝 Setting up config for buffer demo...")
    education_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[
            {
                "topic": "学习偏好",
                "sub_topics": [{"name": "学习时间"}, {"name": "学习风格"}]
            }
        ]
    )
    try:
        await memobase.set_project_config(project_id, education_config)
        print("✓ Config saved")
    except Exception as e:
        print(f"⚠️  Skipped: {e}")
    print()

    # Add blobs to buffer
    print("📦 Adding blobs to buffer...")
    blob1 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="我每天晚上学习Python，喜欢看视频教程。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    blob_id1 = await memobase.add_blob_to_buffer(
        user_id=user_id,
        blob=blob1,
        project_id=project_id
    )
    print(f"✓ Added blob: {blob_id1}")
    print()

    # Process buffer (uses project-specific config automatically)
    print("⚙️  Processing buffer...")
    print("  (Will automatically load project config from DB)")
    print()

    try:
        result = await memobase.process_buffer(
            user_id=user_id,
            blob_type=BlobType.chat,
            project_id=project_id
        )

        if result:
            print("✓ Buffer processed successfully")
            print(f"  - Event ID: {result.event_id}")
            print(f"  - Profiles added: {len(result.add_profiles)}")
        else:
            print("ℹ️  No blobs to process")
    except Exception as e:
        print(f"ℹ️  Processing result: {e}")
    print()

    print("Key Point: process_buffer() also uses project-specific configs!")
    print("=" * 80)


if __name__ == "__main__":
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "     Project-Specific Profile Configuration Demo".center(78)     + "║")
    print("║" + "     按项目动态配置 Topic/Subtopic 演示".center(78)                + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    try:
        asyncio.run(demo_project_specific_config())
        print()
        asyncio.run(demo_buffer_with_project_config())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
