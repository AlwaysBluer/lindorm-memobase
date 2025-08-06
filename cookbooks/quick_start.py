import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lindormmemobase import LindormMemobase, LindormMemobaseError, ConfigurationError
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig

async def quick_start():
    """LindormMemobase 快速开始演示"""
    
    print("🚀 LindormMemobase 快速开始演示")
    print("=" * 40)
    
    # Step 1: 初始化LindormMemobase（会自动从环境变量加载配置）
    print("Step 1: 初始化LindormMemobase...")
    try:
        # 使用默认配置（会从环境变量和config.yaml加载）
        memobase = LindormMemobase()
        print(f"✅ LindormMemobase 初始化成功")
        print(f"   语言: {memobase.config.language}")
        print(f"   模型: {memobase.config.best_llm_model}")
    except ConfigurationError as e:
        print(f"❌ 配置错误: {e}")
        print("请检查环境变量设置:")
        print("- MEMOBASE_LLM_API_KEY")
        print("- MEMOBASE_MYSQL_HOST, MEMOBASE_MYSQL_USER, MEMOBASE_MYSQL_PASSWORD")
        print("- MEMOBASE_OPENSEARCH_HOST")
        return
    
    # 初始化Profile配置
    profile_config = ProfileConfig(language="zh")
    print("✅ Profile配置初始化完成")
    
    # Step 2: 准备测试数据
    print("\nStep 2: 准备用户对话数据...")
    
    # 使用ChatBlob格式（包含messages列表）
    user_id = "zhangxiaoming_engineer_123"
    timestamp = int(datetime.now().timestamp())
    
    conversation_blobs = [
        ChatBlob(
            id=f"chat_{user_id}_{timestamp}_1",
            messages=[
                OpenAICompatibleMessage(role="user", content="你好！我是张小明，今年25岁，在北京工作，是一名软件工程师。"),
                OpenAICompatibleMessage(role="assistant", content="你好张小明！很高兴认识你。你在北京做软件开发多久了？"),
                OpenAICompatibleMessage(role="user", content="已经3年了。我主要做AI相关的项目，最近有点焦虑，工作压力比较大。我希望能找到一个AI助手来帮助我管理情绪和工作。")
            ],
            type=BlobType.chat,
            timestamp=timestamp
        ),
        ChatBlob(
            id=f"chat_{user_id}_{timestamp}_2",
            messages=[
                OpenAICompatibleMessage(role="user", content="我比较喜欢幽默轻松的对话风格，不要太正式。我希望AI助手能记住我们之前的对话，并且能给我一些建设性的建议。"),
                OpenAICompatibleMessage(role="assistant", content="明白了！我会用轻松友好的方式和你聊天。你希望多久互动一次呢？"),
                OpenAICompatibleMessage(role="user", content="每天聊一聊就好，主要聊工作、技术学习，还有心理健康方面的话题。")
            ],
            type=BlobType.chat,
            timestamp=timestamp + 1
        )
    ]
    
    print(f"✅ 创建了 {len(conversation_blobs)} 个对话记录")
    
    # Step 3: 内存提取
    print("\nStep 3: 执行内存提取...")
    print("🔄 正在调用LLM进行内存提取和分析...")
    
    try:
        # 使用新的API（直接返回数据，不需要检查Promise）
        extraction_result = await memobase.extract_memories(
            user_id=user_id,
            blobs=conversation_blobs,
            profile_config=profile_config
        )
        
        print("🎉 内存提取成功!")
        print(f"   提取结果: {type(extraction_result)}")
        
        # 显示提取结果的详细信息
        if hasattr(extraction_result, 'merge_add_result'):
            merge_result = extraction_result.merge_add_result
            added = len(merge_result.get('add', []))
            updated = len(merge_result.get('update', []))
            deleted = len(merge_result.get('delete', []))
            print(f"   新增档案: {added} 个")
            print(f"   更新档案: {updated} 个")
            print(f"   删除档案: {deleted} 个")
        else:
            print(f"   提取完成，结果格式: {extraction_result}")
            
    except LindormMemobaseError as e:
        print(f"❌ 内存提取失败: {e}")
    except Exception as e:
        print(f"⚠️  处理出错: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 4: 检索用户档案
    print("\nStep 4: 检索用户档案...")
    try:
        profiles = await memobase.get_user_profiles(user_id)
        print(f"🔍 找到 {len(profiles)} 个用户档案:")
        
        for profile in profiles:
            print(f"\n📋 主题: {profile.topic}")
            for subtopic, entry in profile.subtopics.items():
                print(f"   └── {subtopic}: {entry.content[:100]}...")
                
    except LindormMemobaseError as e:
        print(f"❌ 档案检索失败: {e}")
    
    # Step 5: 搜索相关事件
    print("\nStep 5: 搜索相关事件...")
    try:
        events = await memobase.search_events(user_id, "AI项目 工作压力", limit=3)
        print(f"🔍 找到 {len(events)} 个相关事件:")
        
        for event in events:
            similarity = event.get('similarity', 0)
            content = event['content'][:100] + "..." if len(event['content']) > 100 else event['content']
            print(f"   📅 相似度 {similarity:.2f}: {content}")
            
    except LindormMemobaseError as e:
        print(f"❌ 事件搜索失败: {e}")
    
    # Step 6: 获取对话上下文
    print("\nStep 6: 获取对话上下文...")
    try:
        # 模拟新的对话
        new_conversation = [
            OpenAICompatibleMessage(role="user", content="今天工作又很累，有什么建议吗？")
        ]
        
        context = await memobase.get_conversation_context(
            user_id=user_id,
            conversation=new_conversation,
            profile_config=profile_config,
            max_token_size=1000
        )
        
        print("📝 生成的上下文:")
        print(f"   {context[:200]}..." if len(context) > 200 else context)
        
    except LindormMemobaseError as e:
        print(f"❌ 上下文生成失败: {e}")

# def check_environment():
#     """检查必要的环境变量是否设置"""
#     required_env_vars = [
#         'MEMOBASE_LLM_API_KEY',
#         'MEMOBASE_MYSQL_HOST',
#         'MEMOBASE_MYSQL_USER', 
#         'MEMOBASE_MYSQL_PASSWORD',
#         'MEMOBASE_OPENSEARCH_HOST'
#     ]
    
#     missing_vars = []
#     for var in required_env_vars:
#         if not os.getenv(var):
#             missing_vars.append(var)
    
#     if missing_vars:
#         print("❌ 缺少必要的环境变量:")
#         for var in missing_vars:
#             print(f"   - {var}")
#         print("\n请在运行前设置这些环境变量。")
#         return False
    
#     print("✅ 环境变量检查通过")
#     return True


if __name__ == "__main__":
    asyncio.run(quick_start())