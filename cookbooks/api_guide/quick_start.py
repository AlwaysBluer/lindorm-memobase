import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lindormmemobase import LindormMemobase, LindormMemobaseError, ConfigurationError
from lindormmemobase.models.blob import ChatBlob, OpenAICompatibleMessage
from lindormmemobase import Config

async def quick_start():
    """LindormMemobase 快速开始演示"""

    config_path = "config.yaml"
    config = Config.load_config(config_path)
    memobase = LindormMemobase(config)

    # 使用ChatBlob格式（包含messages列表）
    user_id = "zhangxiaoming_engineer_123"
    conversation_blobs = [
        ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user", content="你好！我是张小明，今年25岁，在北京工作，是一名软件工程师。"),
                OpenAICompatibleMessage(role="assistant", content="你好张小明！很高兴认识你。你在北京做软件开发多久了？"),
                OpenAICompatibleMessage(role="user",
                                        content="已经3年了。我主要做AI相关的项目，最近有点焦虑，工作压力比较大。我希望能找到一个AI助手来帮助我管理情绪和工作。")
            ],
        ),
        ChatBlob(
            messages=[
                OpenAICompatibleMessage(role="user",
                                        content="我比较喜欢幽默轻松的对话风格，不要太正式。我希望AI助手能记住我们之前的对话，并且能给我一些建设性的建议。"),
                OpenAICompatibleMessage(role="assistant",
                                        content="明白了！我会用轻松友好的方式和你聊天。你希望多久互动一次呢？"),
                OpenAICompatibleMessage(role="user",
                                        content="每天聊一聊就好，主要聊工作、技术学习，还有心理健康方面的话题。")
            ],
        )
    ]

    extraction_result = await memobase.extract_memories(
        user_id=user_id,
        blobs=conversation_blobs
    )

    profiles = await memobase.get_user_profiles(user_id)
    print(f"🔍 找到 {len(profiles)} 个用户档案:")

    for profile in profiles:
        print(f"\n📋 主题: {profile.topic}")
        for subtopic, entry in profile.subtopics.items():
            print(f"   └── {subtopic}: {entry.content[:100]}...")

    events = await memobase.search_events(user_id, "AI项目 工作压力", limit=3)
    print(f"🔍 找到 {len(events)} 个相关事件:")

    for event in events:
        similarity = event.get('similarity', 0)
        content = event['content'][:100] + "..." if len(event['content']) > 100 else event['content']
        print(f"   📅 相似度 {similarity:.2f}: {content}")

    print("\nStep 6: 获取对话上下文...")
    try:
        new_conversation = [
            OpenAICompatibleMessage(role="user", content="今天工作又很累，有什么建议吗？")
        ]

        context = await memobase.get_conversation_context(
            user_id=user_id,
            conversation=new_conversation,
            max_token_size=1000
        )

        print("📝 生成的上下文:")
        print(f"   {context[:200]}..." if len(context) > 200 else context)

    except LindormMemobaseError as e:
        print(f"❌ 上下文生成失败: {e}")


if __name__ == "__main__":
    asyncio.run(quick_start())