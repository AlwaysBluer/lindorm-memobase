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

================================================================================
SUBTOPIC FIELD REFERENCE (子主题字段说明)
================================================================================

SubTopic(
    name: str,                    # [必填] 子主题名称，如 "学习时间"、"编程能力"
    description: Optional[str],   # [可选] 提取阶段：告诉 LLM 这个字段是干什么的
    update_description: Optional[str],  # [可选] 合并阶段：告诉 LLM 如何处理新旧数据冲突
    validate_value: Optional[bool],     # [可选] 是否强制验证，True 则强制走 merge 验证
)

================================================================================
FIELD USAGE GUIDE (字段使用指南)
================================================================================

1. name (必填)
   - 子主题的唯一标识符
   - 示例: "学习时间", "编程能力", "常买品类"

2. description (推荐填写)
   - 用途：提取阶段，帮助 LLM 理解该字段的含义，从对话中准确抽取信息
   - 示例: "用户喜欢在什么时间段学习"
   - 不填写：LLM 使用默认理解，可能不够精准

3. update_description (高级配置)
   - 用途：合并阶段，当旧值和新值冲突时，告诉 LLM 如何处理
   - 常见策略:
     - "只保留最新值" - 每次更新覆盖旧的
     - "保留所有历史值，用逗号分隔" - 累积式记录
     - "保留最详细的描述" - 选内容更丰富的
   - 不填写：使用默认 merge 策略（智能合并新旧内容）

4. validate_value (可选)
   - 用途：控制是否强制走 merge 验证逻辑
   - True:  必须验证，即使全局关闭验证也会验证
   - False/None: 跟随全局 PROFILE_VALIDATE_MODE 配置
   - 场景: 关键字段（如用户身份）设为 True，次要字段跟随全局

================================================================================
COMMON PATTERNS (常见配置模式)
================================================================================

PATTERN 1: 简单子主题 (只填 name)
    {"name": "学习科目"}  # 适合通用场景，使用默认行为

PATTERN 2: 需要准确理解 (加 description)
    {
        "name": "学习时间",
        "description": "用户喜欢在什么时间段学习，如早上、晚上、周末等"
    }

PATTERN 3: 覆盖式更新 (加 update_description)
    {
        "name": "最后活跃时间",
        "description": "用户最后一次活跃的时间",
        "update_description": "只保留最新的时间，丢弃旧的记录"  # 覆盖式
    }

PATTERN 4: 累积式更新 (不同的 update_description)
    {
        "name": "学习科目",
        "description": "用户学习过的所有科目",
        "update_description": "保留所有提到过的科目，用逗号连接，去重"  # 累积式
    }

PATTERN 5: 强制验证 (加 validate_value)
    {
        "name": "用户身份",
        "description": "用户的职业或身份标识",
        "validate_value": True  # 关键信息，强制验证
    }

PATTERN 6: 完整配置 (全部字段)
    {
        "name": "编程能力",
        "description": "用户的编程技能水平和掌握的语言",
        "update_description": "保留最新和最详细的描述，合并相关技能",
        "validate_value": True
    }

================================================================================
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

    # ========== Part 9: Advanced Field Usage Examples ==========
    print("=" * 80)
    print("Part 9: Advanced SubTopic Field Usage Examples")
    print("=" * 80)
    print()
    print("Real-world examples demonstrating when to use each field:")
    print()

    print("┌─ EXAMPLE 1: Override-style updates (覆盖式更新)")
    print("│  Scenario: User's last login time - only keep the latest")
    print("│")
    last_login_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[{
            "topic": "活跃状态",
            "description": "用户在平台的活跃情况",
            "sub_topics": [
                {
                    "name": "最后登录时间",
                    "description": "用户最后一次登录平台的时间",
                    "update_description": "只保留最新提到的登录时间，覆盖旧的记录"
                },
                {
                    "name": "活跃时段",
                    "description": "用户经常在什么时间段活跃",
                    "update_description": "保留所有提到的时段，合并为完整的时间偏好描述"
                }
            ]
        }]
    )
    print("│  Config:")
    print("│    SubTopic(")
    print("│        name='最后登录时间',")
    print("│        description='用户最后一次登录平台的时间',")
    print("│        update_description='只保留最新提到的登录时间，覆盖旧的记录'")
    print("│    )")
    print("│")
    print("│  Behavior:")
    print("│    Day 1: '我昨天登录了' → '昨天'")
    print("│    Day 2: '我刚才登录了' → '刚才' (旧的 '昨天' 被覆盖)")
    print("│")
    print("└─────────────────────────────────────────────────────────────")
    print()

    print("┌─ EXAMPLE 2: Accumulative updates (累积式更新)")
    print("│  Scenario: User's learned skills - collect all mentioned skills")
    print("│")
    skills_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[{
            "topic": "技能清单",
            "description": "用户掌握的所有技能",
            "sub_topics": [
                {
                    "name": "编程语言",
                    "description": "用户会使用的编程语言",
                    "update_description": "保留所有提到过的编程语言，用顿号连接，去重，按提及时间排序"
                },
                {
                    "name": "框架工具",
                    "description": "用户使用过的开发框架和工具",
                    "update_description": "累积式添加，用逗号分隔，去除重复项"
                }
            ]
        }]
    )
    print("│  Config:")
    print("│    SubTopic(")
    print("│        name='编程语言',")
    print("│        description='用户会使用的编程语言',")
    print("│        update_description='保留所有提到过的编程语言，用顿号连接，去重'")
    print("│    )")
    print("│")
    print("│  Behavior:")
    print("│    Day 1: '我会Python' → 'Python'")
    print("│    Day 2: '我还学了JavaScript' → 'Python、JavaScript'")
    print("│    Day 3: 'Python是我的主力语言' → 'Python、JavaScript' (去重)")
    print("│")
    print("└─────────────────────────────────────────────────────────────")
    print()

    print("┌─ EXAMPLE 3: Smart merge (智能合并)")
    print("│  Scenario: User's bio description - merge intelligently")
    print("│")
    bio_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[{
            "topic": "个人简介",
            "description": "用户的基本个人信息",
            "sub_topics": [
                {
                    "name": "自我介绍",
                    "description": "用户对自己的描述和介绍",
                    "update_description": "智能合并新旧描述，保留关键信息，避免重复，保持叙述连贯"
                }
            ]
        }]
    )
    print("│  Config:")
    print("│    SubTopic(")
    print("│        name='自我介绍',")
    print("│        description='用户对自己的描述和介绍',")
    print("│        update_description='智能合并新旧描述，保留关键信息，避免重复'")
    print("│    )")
    print("│")
    print("│  Behavior:")
    print("│    Day 1: '我是一名程序员' → '我是一名程序员'")
    print("│    Day 2: '我住在北京，喜欢编程' → '我是一名程序员，住在北京，喜欢编程'")
    print("│")
    print("└─────────────────────────────────────────────────────────────")
    print()

    print("┌─ EXAMPLE 4: Critical data with validation (关键数据强制验证)")
    print("│  Scenario: User identity - must be accurate")
    print("│")
    identity_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[{
            "topic": "身份信息",
            "description": "用户的核心身份标识",
            "sub_topics": [
                {
                    "name": "职业",
                    "description": "用户的职业或工作身份",
                    "validate_value": True  # 关键信息，强制验证
                },
                {
                    "name": "行业",
                    "description": "用户所在的行业领域",
                    "validate_value": True  # 强制验证
                },
                {
                    "name": "兴趣爱好",  # 次要信息，不强制验证
                    "description": "用户的业余爱好"
                }
            ]
        }]
    )
    print("│  Config:")
    print("│    SubTopic(")
    print("│        name='职业',")
    print("│        description='用户的职业或工作身份',")
    print("│        validate_value=True  # 强制验证，确保准确性")
    print("│    )")
    print("│")
    print("│  Behavior:")
    print("│    - 即使全局关闭验证，职业和行业也会走 merge 验证")
    print("│    - 兴趣爱好跟随全局配置，可能跳过验证")
    print("│")
    print("└─────────────────────────────────────────────────────────────")
    print()

    print("┌─ EXAMPLE 5: Minimal config (最简配置)")
    print("│  Scenario: Quick setup for non-critical fields")
    print("│")
    minimal_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[{
            "topic": "基础信息",
            "sub_topics": [
                {"name": "昵称"},           # 只有 name，使用默认行为
                {"name": "所在地"},
                {"name": "个人简介"}
            ]
        }]
    )
    print("│  Config:")
    print("│    SubTopic(name='昵称')  # 最简配置")
    print("│")
    print("│  Behavior:")
    print("│    - 使用默认的 description (从 name 推断)")
    print("│    - 使用默认的 merge 策略")
    print("│    - 跟随全局验证配置")
    print("│")
    print("└─────────────────────────────────────────────────────────────")
    print()

    print("┌─ EXAMPLE 6: Complete config (完整配置示例)")
    print("│  Scenario: E-commerce user's shipping preference")
    print("│")
    shipping_config = ProfileConfig(
        language="zh",
        overwrite_user_profiles=[{
            "topic": "收货偏好",
            "description": "用户的收货地址和配送偏好",
            "sub_topics": [
                {
                    "name": "默认收货地址",
                    "description": "用户最常用的收货地址，包括省市区详细地址",
                    "update_description": "只保留最新的完整地址，如果新信息更详细则更新",
                    "validate_value": True  # 地址信息很重要
                },
                {
                    "name": "配送时间偏好",
                    "description": "用户希望收货的时间段，如工作日、周末、具体时段",
                    "update_description": "保留最新的时间偏好，如果用户说'只要工作日'则覆盖之前的'周末配送'"
                },
                {
                    "name": "收货人备注",
                    "description": "配送时的特殊要求，如'放快递柜'、'送货上门'等",
                    "update_description": "合并所有备注，用分号分隔不同要求"
                }
            ]
        }]
    )
    print("│  Config (all fields populated):")
    print("│    SubTopic(")
    print("│        name='默认收货地址',")
    print("│        description='用户最常用的收货地址，包括省市区详细地址',")
    print("│        update_description='只保留最新的完整地址，如果新信息更详细则更新',")
    print("│        validate_value=True")
    print("│    )")
    print("│")
    print("└─────────────────────────────────────────────────────────────")
    print()

    print("✅ Advanced examples completed!")
    print("   Key takeaways:")
    print("   - Simple fields: only name needed")
    print("   - Need accuracy: add description")
    print("   - Special merge behavior: add update_description")
    print("   - Critical data: set validate_value=True")
    print()

    # ========== Summary ==========
    print("=" * 80)
    print("Summary: Complete API Reference")
    print("=" * 80)
    print()

    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ 1. SUBTOPIC FIELD CHEATSHEET                                     │")
    print("└─────────────────────────────────────────────────────────────────┘")
    print()
    print("  Field               Required? Purpose                           When to Use")
    print("  ─────────────────── ───────── ─────────────────────────────── ────────────────────────")
    print("  name                YES       Subtopic identifier              Always")
    print("  description         NO        Help LLM understand the field    Need accurate extraction")
    print("  update_description  NO        Control merge behavior           Special merge strategy needed")
    print("  validate_value      NO        Force validation on/off          Critical/less-critical data")
    print()

    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ 2. CRUD OPERATIONS                                               │")
    print("└─────────────────────────────────────────────────────────────────┘")
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

    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ 3. CONFIGURATION PRIORITY (highest to lowest)                    │")
    print("└─────────────────────────────────────────────────────────────────┘")
    print()
    print("  1️⃣  Explicit profile_config parameter")
    print("      result = await memobase.extract_memories(")
    print("          user_id='user123',")
    print("          blobs=[blob],")
    print("          profile_config=custom_config  # Explicit wins")
    print("      )")
    print()
    print("  2️⃣  Database config (ProjectProfileConfigs table)")
    print("      result = await memobase.extract_memories(")
    print("          user_id='user123',")
    print("          blobs=[blob],")
    print("          project_id='education_app'  # Auto-load from DB")
    print("      )")
    print()
    print("  3️⃣  config.yaml fallback")
    print("      result = await memobase.extract_memories(")
    print("          user_id='user123',")
    print("          blobs=[blob]")
    print("          # No project_id = use config.yaml")
    print("      )")
    print()

    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ 4. QUICK CONFIG TEMPLATES                                        │")
    print("└─────────────────────────────────────────────────────────────────┘")
    print()
    print("  # Minimal (simple fields)")
    print("  SubTopic(name='field_name')")
    print()
    print("  # With description (need accuracy)")
    print('  SubTopic(name="学习时间", description="用户喜欢在什么时间段学习")')
    print()
    print("  # Override-style (keep latest)")
    print('  SubTopic(name="最后登录", update_description="只保留最新的时间")')
    print()
    print("  # Accumulative (collect all)")
    print('  SubTopic(name="学习科目", update_description="保留所有科目，用顿号连接")')
    print()
    print("  # Critical data (force validate)")
    print('  SubTopic(name="用户身份", validate_value=True)')
    print()

    print("Demo completed successfully!")
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
