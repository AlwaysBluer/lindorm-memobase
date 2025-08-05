#!/usr/bin/env python3
"""
LindormMemobase Full Pipeline Demo
完整数据处理流程演示
"""

import asyncio
from config import Config
from api import LindormMemobase
from models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from models.profile_topic import ProfileConfig

async def quick_start():
    """完整流程演示"""
    
    print("🚀 LindormMemobase 完整流程演示")
    print("=" * 40)
    
    # Step 1: 加载配置
    print("Step 1: 加载配置...")
    config = Config.load_config()
    print(f"✅ 配置加载完成: {config.language}, {config.best_llm_model}")
    
    # Step 2: 初始化
    print("\nStep 2: 初始化LindormMemobase...")
    memobase = LindormMemobase(config=config)
    profile_config = ProfileConfig(language="zh")
    print("✅ 初始化完成")
    
    # Step 3: 准备测试数据
    print("\nStep 3: 准备用户对话数据...")
    conversation_blobs = [
        ChatBlob(
            type=BlobType.chat,
            messages=[
                OpenAICompatibleMessage(role="user", content="你好！我是张小明，今年25岁，在北京工作，是一名软件工程师。"),
                OpenAICompatibleMessage(role="assistant", content="你好张小明！很高兴认识你。你在北京做软件开发多久了？"),
                OpenAICompatibleMessage(role="user", content="已经3年了。我主要做AI相关的项目，最近有点焦虑，工作压力比较大。我希望能找到一个AI助手来帮助我管理情绪和工作。")
            ]
        ),
        ChatBlob(
            type=BlobType.chat,
            messages=[
                OpenAICompatibleMessage(role="user", content="我比较喜欢幽默轻松的对话风格，不要太正式。我希望AI助手能记住我们之前的对话，并且能给我一些建设性的建议。"),
                OpenAICompatibleMessage(role="assistant", content="明白了！我会用轻松友好的方式和你聊天。你希望多久互动一次呢？"),
                OpenAICompatibleMessage(role="user", content="每天聊一聊就好，主要聊工作、技术学习，还有心理健康方面的话题。")
            ]
        )
    ]
    print(f"✅ 创建了 {len(conversation_blobs)} 个对话记录")
    
    # Step 4: 执行完整数据处理
    print("\nStep 4: 执行完整数据处理...")
    print("🔄 正在调用 Qwen 模型进行数据提取和分析...")
    
    user_id = "zhangxiaoming_engineer_123"
    
    try:
        result = await memobase.process_user_blobs(
            user_id=user_id,
            blobs=conversation_blobs,
            profile_config=profile_config
        )
        
        if result.ok():
            data = result.data()
            print("🎉 数据处理成功!")
            print(f"   事件ID: {data.event_id}")
            print(f"   新增档案: {len(data.add_profiles)} 个")
            print(f"   更新档案: {len(data.update_profiles)} 个")
            print(f"   删除档案: {len(data.delete_profiles)} 个")
            
            # 显示提取的档案信息
            if data.add_profiles:
                print("\n📋 新增的用户档案:")
                for profile_id in data.add_profiles:
                    print(f"   - Profile ID: {profile_id}")
            
            if data.update_profiles:
                print("\n🔄 更新的用户档案:")
                for profile_id in data.update_profiles:
                    print(f"   - Profile ID: {profile_id}")
                    
        else:
            print(f"❌ 处理失败: {result.msg()}")
            
    except Exception as e:
        print(f"⚠️  处理出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 40)
    print("🎉 完整流程演示结束!")
    print(f"✨ 使用了你的配置: {config.best_llm_model} + 中文处理 + 自定义档案")

if __name__ == "__main__":
    asyncio.run(quick_start())