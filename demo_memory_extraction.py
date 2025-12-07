#!/usr/bin/env python3
"""
LindormMemobase Memory Extraction Demo
测试记忆的提取、合并和更新效果的完整示例

这个示例演示：
1. 初始记忆提取 - 从初次对话中提取用户信息
2. 记忆更新 - 用户提供新信息，更新现有档案
3. 记忆合并 - 来自不同对话的相关信息合并到同一主题
4. 档案查询 - 验证提取和更新的效果
"""

import asyncio
from datetime import datetime
from lindormmemobase import LindormMemobase, Config
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage


async def demo_memory_extraction():
    """完整的记忆提取、合并、更新演示"""
    
    print("=" * 80)
    print("LindormMemobase 记忆提取演示")
    print("=" * 80)
    print()
    
    # 初始化 Memobase
    print("📌 步骤 1: 初始化系统")
    config = Config.from_yaml_file("config.yaml")

    memobase = LindormMemobase(config)
    user_id = f"demo_user_{int(datetime.now().timestamp())}"
    project_id = "memory_extraction_demo"
    print(f"✓ 用户ID: {user_id}")
    print(f"✓ 项目ID: {project_id}")
    print()
    
    # ========== 第一部分：初始记忆提取 ==========
    print("=" * 80)
    print("第一部分：初始记忆提取")
    print("=" * 80)
    print()
    
    # 第一次对话：基本个人信息（新增 personal_info）
    print("💬 对话 1: 基本个人信息 - 测试新增档案")
    conversation_1 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user", 
                content="你好！我叫张伟，今年32岁，是一名软件工程师。"
            ),
            OpenAICompatibleMessage(
                role="assistant", 
                content="你好张伟！很高兴认识你。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )
    
    print("  提取记忆中...")
    result_1 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[conversation_1],
        project_id=project_id
    )
    print(f"  ✓ 事件ID: {result_1.event_id}")
    print(f"  ✓ 新增档案: {len(result_1.add_profiles)} 个")
    print(f"  ✓ 更新档案: {len(result_1.update_profiles)} 个")
    print()
    
    # 查看提取的档案
    print("📋 本轮提取后的用户档案:")
    profiles_1 = await memobase.get_user_profiles(user_id, project_id=project_id)
    print(f"   当前共有 {len(profiles_1)} 个主题")
    for profile in profiles_1:
        print(f"\n  【主题: {profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"    - {subtopic}: {entry.content}")
    print()
    
    # 第二次对话：技术技能（新增 skills）
    print("💬 对话 2: 技术技能 - 测试新增另一个档案")
    conversation_2 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user", 
                content="我在公司主要做后端开发，熟悉Python和Go语言。"
            ),
            OpenAICompatibleMessage(
                role="assistant", 
                content="这两种语言都很强大！你有用过什么框架吗？"
            ),
            OpenAICompatibleMessage(
                role="user", 
                content="Python主要用Django和FastAPI，Go用的是Gin框架。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )
    
    print("  提取记忆中...")
    result_2 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[conversation_2],
        project_id=project_id
    )
    print(f"  ✓ 事件ID: {result_2.event_id}")
    print(f"  ✓ 新增档案: {len(result_2.add_profiles)} 个")
    print(f"  ✓ 更新档案: {len(result_2.update_profiles)} 个")
    print()
    
    # 查看更新后的档案
    print("📋 本轮提取后的用户档案:")
    profiles_2 = await memobase.get_user_profiles(user_id, project_id=project_id)
    print(f"   当前共有 {len(profiles_2)} 个主题")
    for profile in profiles_2:
        print(f"\n  【主题: {profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"    - {subtopic}: {entry.content}")
    print()
    
    # ========== 第二部分：记忆更新测试 ==========
    print("=" * 80)
    print("第二部分：记忆更新测试")
    print("=" * 80)
    print()
    
    # 第三次对话：更新技术技能（更新 skills）
    print("💬 对话 3: 技术栈更新 - 测试更新现有档案")
    conversation_3 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user", 
                content="最近我开始学习Rust了，觉得它的内存安全特性很棒。"
            ),
            OpenAICompatibleMessage(
                role="assistant", 
                content="Rust确实很有前景！你打算用它做什么项目吗？"
            ),
            OpenAICompatibleMessage(
                role="user", 
                content="想用Rust重写一些性能关键的服务，还在学习阶段。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )
    
    print("  提取记忆中...")
    result_3 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[conversation_3],
        project_id=project_id
    )
    print(f"  ✓ 事件ID: {result_3.event_id}")
    print(f"  ✓ 新增档案: {len(result_3.add_profiles)} 个")
    print(f"  ✓ 更新档案: {len(result_3.update_profiles)} 个")
    print(f"  ✓ 删除档案: {len(result_3.delete_profiles)} 个")
    print()
    
    # 验证更新效果
    print("📋 本轮提取后的用户档案 (验证技术技能更新):")
    profiles_3 = await memobase.get_user_profiles(user_id, project_id=project_id)
    print(f"   当前共有 {len(profiles_3)} 个主题")
    for profile in profiles_3:
        print(f"\n  【主题: {profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"    - {subtopic}: {entry.content}")
    print()
    
    # ========== 第三部分：记忆合并测试 ==========
    print("=" * 80)
    print("第三部分：记忆合并测试")
    print("=" * 80)
    print()
    
    # 第四次对话：新增兴趣爱好（新增 hobbies）
    print("💬 对话 4: 兴趣爱好 - 测试新增第三个档案")
    conversation_4 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user", 
                content="我平时喜欢健身，每周去健身房3-4次，主要做力量训练。"
            ),
            OpenAICompatibleMessage(
                role="assistant", 
                content="保持运动是很好的习惯！"
            ),
            OpenAICompatibleMessage(
                role="user", 
                content="是的，已经坚持了2年了。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )
    
    print("  提取记忆中...")
    result_4 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[conversation_4],
        project_id=project_id
    )
    print(f"  ✓ 事件ID: {result_4.event_id}")
    print(f"  ✓ 新增档案: {len(result_4.add_profiles)} 个")
    print(f"  ✓ 更新档案: {len(result_4.update_profiles)} 个")
    print()
    
    # 查看本轮更新后的档案
    print("📋 本轮提取后的用户档案:")
    profiles_4 = await memobase.get_user_profiles(user_id, project_id=project_id)
    print(f"   当前共有 {len(profiles_4)} 个主题")
    for profile in profiles_4:
        print(f"\n  【主题: {profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"    - {subtopic}: {entry.content}")
    print()
    
    # ========== 第四部分：复杂场景测试 ==========
    print("=" * 80)
    print("第四部分：复杂场景 - 多主题混合对话")
    print("=" * 80)
    print()
    
    # 第五次对话：更新兴趣爱好（更新 hobbies）并测试删除
    print("💬 对话 5: 兴趣变化 - 测试更新档案")
    conversation_5 = ChatBlob(
        messages=[
            OpenAICompatibleMessage(
                role="user", 
                content="最近我改练瑜伽了，觉得对身体柔韧性更好。力量训练暂时停了。"
            ),
            OpenAICompatibleMessage(
                role="assistant", 
                content="瑜伽也是很好的运动方式！"
            ),
            OpenAICompatibleMessage(
                role="user", 
                content="是的，每周上3次瑜伽课，感觉压力小了很多。"
            ),
        ],
        type=BlobType.chat,
        created_at=datetime.now()
    )
    
    print("  提取记忆中...")
    result_5 = await memobase.extract_memories(
        user_id=user_id,
        blobs=[conversation_5],
        project_id=project_id
    )
    print(f"  ✓ 事件ID: {result_5.event_id}")
    print(f"  ✓ 新增档案: {len(result_5.add_profiles)} 个")
    print(f"  ✓ 更新档案: {len(result_5.update_profiles)} 个")
    print()
    
    # 查看本轮更新后的档案
    print("📋 本轮提取后的用户档案:")
    profiles_5 = await memobase.get_user_profiles(user_id, project_id=project_id)
    print(f"   当前共有 {len(profiles_5)} 个主题")
    for profile in profiles_5:
        print(f"\n  【主题: {profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"    - {subtopic}: {entry.content}")
    print()
    
    # ========== 第五部分：最终档案汇总 ==========
    print("=" * 80)
    print("第五部分：最终用户档案汇总")
    print("=" * 80)
    print()
    
    # 获取完整档案
    print("📊 完整用户档案:")
    final_profiles = await memobase.get_user_profiles(user_id, project_id=project_id)
    print(f"总共 {len(final_profiles)} 个主题\n")
    
    for i, profile in enumerate(final_profiles, 1):
        print(f"{i}. 【{profile.topic}】")
        for subtopic, entry in profile.subtopics.items():
            print(f"   • {subtopic}:")
            print(f"     {entry.content}")
        print()
    
    # ========== 第六部分：事件查询测试 ==========
    print("=" * 80)
    print("第六部分：事件查询和搜索")
    print("=" * 80)
    print()
    
    # 获取所有事件
    print("📅 查询最近的事件记录:")
    events = await memobase.get_events(user_id, time_range_in_days=7, limit=10)
    print(f"共 {len(events)} 条事件记录\n")
    
    for i, event in enumerate(events, 1):
        content_preview = event['content'][:100] if len(event['content']) > 100 else event['content']
        print(f"{i}. {content_preview}")
        print(f"   创建时间: {event['created_at']}")
    print()
    
    # 语义搜索测试
    print("🔍 语义搜索测试:")
    search_queries = [
        "技术技能和编程语言",
        "运动和健身习惯",
        "旅行计划"
    ]
    
    for query in search_queries:
        print(f"\n  查询: \"{query}\"")
        search_results = await memobase.search_events(
            user_id=user_id,
            query=query,
            limit=3,
            similarity_threshold=0.1
        )
        
        if search_results:
            print(f"  找到 {len(search_results)} 条相关记录:")
            for result in search_results:
                similarity = result.get('similarity', 0)
                content_preview = result['content'][:80] if len(result['content']) > 80 else result['content']
                print(f"    - (相似度: {similarity:.3f}) {content_preview}")
        else:
            print("  未找到相关记录")
    print()
    
    # ========== 第七部分：上下文生成测试 ==========
    print("=" * 80)
    print("第七部分：对话上下文生成")
    print("=" * 80)
    print()
    
    # 模拟新对话，生成相关上下文
    test_conversations = [
        {
            "query": "我想换个健身计划",
            "topics": ["health", "fitness", "exercise"]
        },
        {
            "query": "推荐一些AI相关的学习资源",
            "topics": ["work", "skills", "technology"]
        },
        {
            "query": "周末有什么好的活动建议",
            "topics": ["hobbies", "interests", "lifestyle"]
        }
    ]
    
    for test_conv in test_conversations:
        print(f"💭 新对话: \"{test_conv['query']}\"")
        
        conversation = [
            OpenAICompatibleMessage(role="user", content=test_conv['query'])
        ]
        
        context = await memobase.get_conversation_context(
            user_id=user_id,
            conversation=conversation,
            max_token_size=1500,
            prefer_topics=test_conv.get('topics'),
            time_range_in_days=7
        )
        
        print(f"  生成的上下文长度: {len(context)} 字符")
        print(f"  上下文预览:")
        context_preview = context[:300] if len(context) > 300 else context
        print(f"  {context_preview}...")
        print()
    
    # ========== 总结 ==========
    print("=" * 80)
    print("演示总结")
    print("=" * 80)
    print()
    print("✅ 完成的测试:")
    print("  1. ✓ 初始记忆提取 - 从零开始建立用户档案")
    print("  2. ✓ 记忆更新 - 更新已有信息（职业变更）")
    print("  3. ✓ 记忆合并 - 同主题信息的累积和补充")
    print("  4. ✓ 多主题处理 - 一次对话涉及多个主题")
    print("  5. ✓ 档案查询 - 按主题和子主题查看")
    print("  6. ✓ 事件搜索 - 语义相似度搜索")
    print("  7. ✓ 上下文生成 - 为新对话生成相关背景")
    print()
    print(f"📈 统计数据:")
    print(f"  - 用户ID: {user_id}")
    print(f"  - 总对话轮次: 5")
    print(f"  - 最终档案主题数: {len(final_profiles)}")
    print(f"  - 事件记录数: {len(events)}")
    print()
    print("✨ 演示完成！")
    print("=" * 80)


if __name__ == "__main__":
    # 运行演示
    try:
        asyncio.run(demo_memory_extraction())
    except KeyboardInterrupt:
        print("\n\n⚠️  演示被用户中断")
    except Exception as e:
        print(f"\n\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
