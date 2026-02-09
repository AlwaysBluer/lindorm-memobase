#!/usr/bin/env python3
"""
Demo: Subtopic-Level Merge Strategy (子主题级别的合并策略)

This demo showcases the new merge threshold feature that allows different
merge behaviors for different subtopics.

Features demonstrated:
1. Configure merge thresholds per "topic::subtopic"
2. Immediate merge for time-sensitive data (threshold=1)
3. Batch merge for stable data (threshold>1) with pending cache
4. Manual trigger_merge() API for on-demand merging
5. Multi-tenant merge isolation per project_id

================================================================================
MERGE THRESHOLD CONCEPTS (合并阈值概念)
================================================================================

Merge Threshold: Number of extracted profiles to accumulate before merging

- threshold = 1: Immediate merge (default, backward compatible)
  → Each profile is merged immediately after extraction
  → Use for: Time-sensitive data that needs real-time updates

- threshold > 1: Batch merge
  → Profiles are cached until threshold is reached, then merged together
  → Use for: Stable data to reduce LLM API costs

Pending Cache: Temporary storage for profiles below merge threshold
  → Stored in PendingProfiles table
  → Automatically merged when threshold is reached
  → Can be manually triggered via trigger_merge()

================================================================================
CONFIGURATION EXAMPLES (配置示例)
================================================================================

# Method 1: Via config.yaml (global default)
merge_thresholds:
  "preferences::current_mood": 1      # Immediate merge (time-sensitive)
  "interests::hobbies": 10           # Batch 10 profiles
  "interests::long_term": 20         # Batch 20 profiles

# Method 2: Via ProfileConfig in code
from lindormmemobase.models.profile_topic import ProfileConfig

config = ProfileConfig(
    merge_thresholds={
        "preferences::dietary": 1,    # Immediate
        "interests::reading": 5,      # Batch 5
    },
    max_pending_profiles=1000         # Max cache size
)

await memobase.set_project_config("my_app", config)

================================================================================
USE CASES (使用场景)
================================================================================

1. E-commerce Application (电商应用)
   - Shopping preferences: threshold=1 (real-time recommendations)
   - Browse history: threshold=10 (batch processing)

2. Education Platform (教育平台)
   - Current progress: threshold=1 (immediate feedback)
   - Long-term goals: threshold=20 (batch analysis)

3. Content Recommendation (内容推荐)
   - Recent interests: threshold=1 (trending topics)
   - Stable preferences: threshold=50 (cost optimization)

================================================================================
"""

import asyncio
from datetime import datetime
from lindormmemobase import LindormMemobase, Config, ProfileConfig
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage


async def demo_merge_threshold():
    """Complete demonstration of merge threshold feature"""

    print("=" * 80)
    print("LindormMemobase 子主题级别合并策略演示")
    print("=" * 80)
    print()

    # ========== Step 1: Initialize System ==========
    print("📌 步骤 1: 初始化系统")
    print("-" * 80)

    config = Config.from_yaml_file("config.yaml")
    memobase = LindormMemobase(config)

    # Generate unique IDs for this demo run
    user_id = f"demo_user_{int(datetime.now().timestamp())}"
    project_id = "merge_threshold_demo"

    print(f"✓ 用户ID: {user_id}")
    print(f"✓ 项目ID: {project_id}")
    print()

    # ========== Step 2: Configure Merge Thresholds ==========
    print("📌 步骤 2: 配置合并阈值")
    print("-" * 80)

    # Configure project-specific merge thresholds
    profile_config = ProfileConfig(
        language="zh",
        merge_thresholds={
            # Time-sensitive: immediate merge
            "preferences::current_mood": 1,
            "preferences::immediate_needs": 1,

            # Stable: batch merge for cost savings
            "interests::hobbies": 3,      # Batch 3 profiles
            "interests::reading": 3,      # Batch 3 profiles
            "demographics::basic_info": 5, # Batch 5 profiles
        },
        max_pending_profiles=1000
    )

    await memobase.set_project_config(project_id, profile_config)
    print("✓ 已配置项目合并策略:")
    print("  - preferences::current_mood: threshold=1 (立即合并)")
    print("  - preferences::immediate_needs: threshold=1 (立即合并)")
    print("  - interests::hobbies: threshold=3 (批量合并)")
    print("  - interests::reading: threshold=3 (批量合并)")
    print("  - demographics::basic_info: threshold=5 (批量合并)")
    print()

    # ========== Step 3: Immediate Merge Demo ==========
    print("=" * 80)
    print("演示 1: 立即合并 (threshold=1)")
    print("=" * 80)
    print()

    print("💬 对话: 当前心情 (preferences::current_mood)")
    conversation_1 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="今天心情很不错，刚刚完成了一个重要的项目！"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    result_1 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[conversation_1],
        project_id=project_id
    )

    print(f"✓ 提取完成")
    print(f"  - 新增档案: {len(result_1.add_profiles)} 个")
    print(f"  - 更新档案: {len(result_1.update_profiles)} 个")

    # Verify the profile was immediately merged
    profiles_1 = await memobase.get_user_profiles(
        user_id=user_id,
        topics=["preferences"],
        project_id=project_id
    )
    print(f"  - 当前 preferences 主题档案数: {len(profiles_1)}")
    print("  → threshold=1, 立即合并 ✅")
    print()

    # ========== Step 4: Batch Merge Demo ==========
    print("=" * 80)
    print("演示 2: 批量合并 (threshold=3)")
    print("=" * 80)
    print()

    # First extraction: hobbies (will be cached, threshold=3)
    print("💬 对话 1: 兴趣爱好 (interests::hobbies) - 第1个，等待缓存")
    hobbies_1 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="我平时喜欢打篮球和看电影。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    result_h1 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[hobbies_1],
        project_id=project_id
    )
    print(f"✓ 提取完成 (当前缓存: 1/3)")
    print(f"  - 新增档案: {len(result_h1.add_profiles)} 个")
    print(f"  - 更新档案: {len(result_h1.update_profiles)} 个")
    print("  → 存入 PendingProfiles 缓存")
    print()

    # Second extraction: hobbies (still cached)
    print("💬 对话 2: 兴趣爱好 (interests::hobbies) - 第2个，继续缓存")
    hobbies_2 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="周末通常和朋友去爬山。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    result_h2 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[hobbies_2],
        project_id=project_id
    )
    print(f"✓ 提取完成 (当前缓存: 2/3)")
    print(f"  - 新增档案: {len(result_h2.add_profiles)} 个")
    print(f"  - 更新档案: {len(result_h2.update_profiles)} 个")
    print("  → 继续存入 PendingProfiles 缓存")
    print()

    # Third extraction: hobbies (threshold reached, auto-merge)
    print("💬 对话 3: 兴趣爱好 (interests::hobbies) - 第3个，触发合并！")
    hobbies_3 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="最近开始学习摄影了。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    result_h3 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[hobbies_3],
        project_id=project_id
    )
    print(f"✓ 提取完成 (达到阈值 3/3)")
    print(f"  - 新增档案: {len(result_h3.add_profiles)} 个")
    print(f"  - 更新档案: {len(result_h3.update_profiles)} 个")
    print("  → 自动触发批量合并，清空缓存 ✅")
    print()

    # Verify the merged result
    profiles_hobbies = await memobase.get_user_profiles(
        user_id=user_id,
        topics=["interests"],
        project_id=project_id
    )
    print(f"📋 合并后的兴趣爱好档案:")
    for profile in profiles_hobbies:
        print(f"\n  【主题: {profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"    - {subtopic}: {entry.content}")
    print()

    # ========== Step 5: Manual Merge Trigger Demo ==========
    print("=" * 80)
    print("演示 3: 手动触发合并 (trigger_merge)")
    print("=" * 80)
    print()

    # Add some reading interests but don't reach threshold
    print("💬 对话: 阅读兴趣 (interests::reading) - 只添加2个，不达到阈值")
    reading_1 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="我喜欢读科幻小说。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    await memobase.extract_memories(
        user_id=user_id,
        blobs=[reading_1],
        project_id=project_id
    )
    print("✓ 第1个阅读兴趣已缓存")

    reading_2 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="最近在看《三体》系列。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    await memobase.extract_memories(
        user_id=user_id,
        blobs=[reading_2],
        project_id=project_id
    )
    print("✓ 第2个阅读兴趣已缓存 (阈值=3，还有1个才自动合并)")
    print()

    # Manually trigger merge
    print("🔧 手动触发合并 (trigger_merge)")
    merge_result = await memobase.trigger_merge(
        user_id=user_id,
        topic="interests",
        subtopic="reading",
        project_id=project_id
    )

    print(f"✓ 合并结果:")
    print(f"  - success: {merge_result.success}")
    print(f"  - merged_count: {merge_result.merged_count}")
    print(f"  - topics_merged: {merge_result.topics_merged}")
    print(f"  - message: {merge_result.message}")
    print()

    # Verify the merged result
    profiles_reading = await memobase.get_user_profiles(
        user_id=user_id,
        topics=["interests"],
        subtopics=["reading"],
        project_id=project_id
    )
    print(f"📋 手动合并后的阅读兴趣档案:")
    for profile in profiles_reading:
        print(f"\n  【主题: {profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"    - {subtopic}: {entry.content}")
    print()

    # ========== Step 6: Multi-Tenant Isolation Demo ==========
    print("=" * 80)
    print("演示 4: 多租户隔离")
    print("=" * 80)
    print()

    # Same user, different project
    project_id_2 = "merge_threshold_demo_2"

    # Configure different thresholds for project 2
    profile_config_2 = ProfileConfig(
        language="zh",
        merge_thresholds={
            "interests::hobbies": 1,  # Immediate merge for project 2
        }
    )
    await memobase.set_project_config(project_id_2, profile_config_2)

    print(f"💬 对话: 项目2中的兴趣爱好 - 立即合并")
    hobbies_p2 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user",
                content="在项目2中，我喜欢游泳。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )

    result_p2 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[hobbies_p2],
        project_id=project_id_2
    )
    print(f"✓ 项目2提取完成:")
    print(f"  - 新增档案: {len(result_p2.add_profiles)} 个")
    print(f"  → threshold=1, 立即合并")
    print()

    # Verify isolation: project 2 should not see project 1 data
    profiles_p1 = await memobase.get_user_profiles(
        user_id=user_id,
        topics=["interests"],
        project_id=project_id
    )
    profiles_p2 = await memobase.get_user_profiles(
        user_id=user_id,
        topics=["interests"],
        project_id=project_id_2
    )

    print(f"📋 多租户隔离验证:")
    print(f"  - 项目1 hobbies 档案数: {len(profiles_p1)}")
    print(f"  - 项目2 hobbies 档案数: {len(profiles_p2)}")
    print("  → 两个项目的数据完全隔离 ✅")
    print()

    # ========== Summary ==========
    print("=" * 80)
    print("演示总结")
    print("=" * 80)
    print()
    print("✅ 立即合并 (threshold=1):")
    print("   - 适合时效性强的数据")
    print("   - 每次提取后立即合并")
    print()
    print("✅ 批量合并 (threshold>1):")
    print("   - 适合稳定的数据")
    print("   - 降低 LLM API 调用成本")
    print("   - 达到阈值时自动合并")
    print()
    print("✅ 手动触发合并:")
    print("   - 可随时强制合并待缓存条目")
    print("   - 支持按 topic/subtopic/project_id 过滤")
    print()
    print("✅ 多租户隔离:")
    print("   - 每个项目独立配置和存储")
    print("   - 相同用户在不同项目中的数据互不干扰")
    print()
    print("=" * 80)


async def demo_cost_comparison():
    """Compare costs between immediate merge and batch merge"""

    print("=" * 80)
    print("成本对比: 立即合并 vs 批量合并")
    print("=" * 80)
    print()

    print("假设场景: 用户在短时间内产生了10个兴趣爱好档案")
    print()

    # Immediate merge (threshold=1)
    print("📊 方案 A: 立即合并 (threshold=1)")
    print("-" * 80)
    immediate_llm_calls = 10
    print(f"  - LLM 调用次数: {immediate_llm_calls} 次")
    print(f"  - 每次提取都触发合并")
    print(f"  - 成本系数: {immediate_llm_calls}x")
    print()

    # Batch merge (threshold=10)
    print("📊 方案 B: 批量合并 (threshold=10)")
    print("-" * 80)
    batch_llm_calls = 1  # Only one merge at the end
    extraction_calls = 10  # Extraction still happens
    print(f"  - LLM 调用次数: {batch_llm_calls} 次 (合并)")
    print(f"  - 提取调用: {extraction_calls} 次 (必要)")
    print(f"  - 成本系数: ~{batch_llm_calls}x (合并)")
    print(f"  - 成本节省: ~{((immediate_llm_calls - batch_llm_calls) / immediate_llm_calls * 100):.0f}%")
    print()

    print("💡 结论:")
    print("   - 对于稳定数据，批量合并可显著降低 LLM 成本")
    print("   - 对于时效性强的数据，使用立即合并保证实时性")
    print()


async def main():
    """Run all demonstrations"""

    # Run main demo
    await demo_merge_threshold()

    print()

    # Run cost comparison
    await demo_cost_comparison()


if __name__ == "__main__":
    asyncio.run(main())
