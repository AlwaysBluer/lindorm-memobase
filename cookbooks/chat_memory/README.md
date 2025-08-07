# Memory-Enhanced Chatbot

一个基于 lindormmemobase 的智能聊天机器人，具有记忆学习和上下文增强能力。

## 功能特性

🧠 **智能记忆系统**
- 自动从对话中提取和存储用户记忆
- 基于向量相似度的记忆搜索
- 个性化用户画像管理

🎯 **上下文增强**
- 根据历史对话智能检索相关记忆
- 为AI回答提供个性化上下文
- 动态调整记忆权重和相关性

⚡ **性能优化**
- 智能缓存系统（90%性能提升）
- 分层记忆管理架构
- 实时事件搜索与缓存用户画像结合

## 文件说明

- `memory_chatbot.py` - 主要的聊天机器人应用
- `smart_memory_manager.py` - 智能记忆管理器（性能优化组件）
- `config.yaml` - 配置文件模板
- `LAYERED_CACHE_OPTIMIZATION.md` - 缓存优化技术文档

## 快速开始

### 1. 环境配置

确保您已经安装并配置了 lindormmemobase：

```bash
# 安装依赖
pip install lindormmemobase

# 配置环境变量
export MEMOBASE_LLM_API_KEY=your-openai-api-key-here
export MEMOBASE_EMBEDDING_API_KEY=your-embedding-api-key-here

# 数据库配置（可选）
export MEMOBASE_MYSQL_HOST=localhost
export MEMOBASE_MYSQL_USERNAME=username
export MEMOBASE_MYSQL_PASSWORD=password
export MEMOBASE_MYSQL_DATABASE=memobase

# Lindorm Search配置
export MEMOBASE_LINDORM_SEARCH_HOST=localhost
export MEMOBASE_LINDORM_SEARCH_PORT=9200
export MEMOBASE_LINDORM_SEARCH_USERNAME=username  
export MEMOBASE_LINDORM_SEARCH_PASSWORD=password
```

### 2. 运行聊天机器人

#### Web界面 (推荐)

```bash
# 安装Web界面依赖
pip install -r cookbooks/chat_memory/requirements-web.txt

# 启动Web服务器
python cookbooks/chat_memory/web_server.py

# 打开浏览器访问
# http://localhost:8000
```

#### 命令行界面

```bash
# 基本运行
python cookbooks/chat_memory/memory_chatbot.py

# 指定用户ID
python cookbooks/chat_memory/memory_chatbot.py --user_id alice

# 使用自定义配置
python cookbooks/chat_memory/memory_chatbot.py --config cookbooks/chat_memory/config.yaml

# 禁用记忆增强
python cookbooks/chat_memory/memory_chatbot.py --no-memory

# 禁用自动记忆提取
python cookbooks/chat_memory/memory_chatbot.py --no-auto-extract
```

### 3. Web界面功能

Web界面提供了现代化的聊天体验，包含以下功能：

- **实时流式对话** - 响应逐字显示，无需等待
- **记忆上下文指示** - 显示是否使用了记忆上下文
- **连接状态监控** - 实时显示连接状态
- **记忆提取通知** - 显示后台记忆处理状态
- **统计信息** - 点击"📊 Stats"查看会话统计
- **记忆浏览** - 点击"📚 Memories"查看存储的记忆
- **响应式设计** - 支持桌面和移动设备

### 4. 命令行界面命令 

在命令行聊天过程中，您可以使用以下命令：

- `/memories` - 查看当前存储的记忆
- `/search [查询]` - 搜索记忆内容
- `/toggle` - 切换记忆增强功能
- `/fast` - 切换快速上下文模式（缓存vs实时）
- `/stats` - 显示会话统计信息
- `/status` - 显示记忆处理状态
- `/cache` - 显示缓存性能统计
- `/help` - 显示帮助信息
- `/quit` - 退出聊天机器人

## 架构特性

### 智能缓存系统

本聊天机器人采用三层缓存架构：

1. **Profile Cache Layer** - 缓存用户画像（慢更新，快访问）
2. **Event Search Layer** - 实时事件搜索（保证准确性）
3. **Session Memory Layer** - 会话历史管理


## 工作原理

### 记忆提取流程

1. **对话收集**：收集用户的对话内容
2. **批量处理**：每10轮对话后自动提取记忆
3. **结构化存储**：将记忆按主题和子主题组织
4. **向量化索引**：为记忆内容创建向量索引以支持相似度搜索
5. **后台处理**：使用异步队列进行非阻塞记忆提取

### 上下文增强流程

1. **缓存检索**：快速从缓存中获取相关用户画像
2. **实时搜索**：搜索最新的相关事件
3. **上下文构建**：组合画像、事件和会话历史
4. **响应生成**：使用增强的上下文生成个性化回答
5. **智能更新**：后台定期更新画像缓存

## 高级配置

### 数据库后端

聊天机器人支持持久化存储：

- **MySQL**: 存储用户画像和结构化记忆
- **Lindorm Search**: 存储事件和支持向量搜索（替代OpenSearch）

配置示例（在 config.yaml 文件中）：

```yaml
# LLM配置
llm_api_key: your-openai-api-key
best_llm_model: gpt-4
embedding_api_key: your-embedding-api-key
embedding_model: text-embedding-3-small

# MySQL配置
mysql_host: localhost
mysql_username: username
mysql_password: password
mysql_database: memobase

# Lindorm Search配置
lindorm_search_host: localhost
lindorm_search_port: 9200
lindorm_search_username: username
lindorm_search_password: password
lindorm_search_use_ssl: false

# 记忆系统配置
enable_event_embedding: true
embedding_dim: 1536
```

### 记忆系统调优

在代码中调整记忆系统参数：

```python
chatbot.max_context_tokens = 4000        # 记忆上下文最大token数
chatbot.conversation_batch_size = 10     # 每N轮对话提取一次记忆
chatbot.use_fast_context = True          # 启用快速缓存模式
```

### 缓存系统配置

```python
# 在SmartMemoryManager中调整缓存参数
memory_manager = SmartMemoryManager(user_id, memobase, max_cache_size=100)
memory_manager.profile_update_interval = 600  # 缓存更新间隔（秒）
```

## 示例会话

```
🤖 Memory Chatbot initialized for user: demo_user
📚 Memory enhancement: ON
🧠 Auto memory extraction: ON
📦 Batch size: 10 messages
⚡ Fast context mode: ON
============================================================

👤 You: Hello! I'm John, and I love playing tennis on weekends.

🤖 Bot: Hello John! It's great to meet you. I see you enjoy playing tennis on weekends - 
that's a wonderful way to stay active and have fun! I'll remember this about you. 
Do you play at a particular court or club?

👤 You: Yes, I usually play at the Central Park courts with my friend Mike.

🤖 Bot: That sounds lovely! Central Park has beautiful tennis courts. Playing with 
Mike regularly must be a great way to maintain both your friendship and your tennis skills. 
I'll remember that you and Mike are tennis partners at Central Park.

👤 You: /cache

📊 Memory Cache Performance:
--------------------------------------------------
   Cache Hit Rate: 85.2%
   Cache Hits: 23
   Cache Misses: 4
   Cached Profiles: 12
   Profile Refreshes: 2
   Average Response Time: 0.456s
   Last Profile Update: 14:25:30

💡 Performance Tips:
   - Fast mode enabled - excellent response time

👤 You: /memories

📚 Your Current Memories:
--------------------------------------------------

🏷️  Topic: sports
   └── tennis: Enjoys playing tennis on weekends at Central Park courts with friend Mike

🏷️  Topic: personal_info
   └── name: User's name is John
   └── social: Has a friend named Mike who plays tennis with them
```

## 故障排除

### 常见问题

1. **API密钥错误**
   - 确保设置了正确的 `MEMOBASE_LLM_API_KEY`
   - 检查API密钥是否有效且有足够余额

2. **记忆功能不工作**
   - 检查是否正确配置了数据库连接
   - 确保具有数据库写入权限

3. **搜索功能不可用**
   - 确保设置了 `MEMOBASE_EMBEDDING_API_KEY`
   - 检查 Lindorm Search 配置是否正确

4. **缓存性能问题**
   - 使用 `/cache` 命令查看缓存统计
   - 考虑调整 `profile_update_interval` 参数

### 日志调试

启用详细日志以排查问题：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

或通过环境变量：

```bash
export MEMOBASE_DEBUG=true
export MEMOBASE_LOG_LEVEL=DEBUG
```

## 扩展开发

### 自定义记忆主题

修改 `ProfileConfig` 以添加自定义记忆主题：

```python
from lindormmemobase.models.profile_topic import ProfileConfig, UserProfileTopic, SubTopic

custom_config = ProfileConfig()
custom_config.topics.append(
    UserProfileTopic(
        name="hobbies",
        subtopics=[
            SubTopic(name="outdoor_activities"),
            SubTopic(name="indoor_activities"),
            SubTopic(name="creative_pursuits")
        ]
    )
)

chatbot = MemoryChatbot("user_id", config)
chatbot.profile_config = custom_config
```

### 自定义缓存策略

继承 `SmartMemoryManager` 类并重写缓存逻辑：

```python
class CustomMemoryManager(SmartMemoryManager):
    def calculate_keyword_relevance(self, message_keywords, cached_profile):
        # 实现自定义相关性算法
        return super().calculate_keyword_relevance(message_keywords, cached_profile)
```

### 自定义响应生成

继承 `MemoryChatbot` 类并重写 `generate_response` 方法：

```python
class CustomChatbot(MemoryChatbot):
    async def generate_response(self, user_message: str, context: str = "") -> str:
        # 实现自定义响应逻辑
        return await super().generate_response(user_message, context)
```

## 技术文档

- [缓存优化技术详解](./LAYERED_CACHE_OPTIMIZATION.md) - 详细的性能优化实现说明

## 许可证

此示例遵循 lindormmemobase 包的许可证条款。