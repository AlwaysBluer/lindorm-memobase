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

💬 **交互式聊天**
- 实时对话界面
- 丰富的命令系统
- 会话统计和记忆管理

## 文件说明

- `memory_chatbot.py` - 主要的聊天机器人应用
- `chatbot_config.yaml` - 配置文件模板
- `chatbot.env` - 环境变量模板

## 快速开始

### 1. 环境配置

复制环境变量模板并填入您的API密钥：

```bash
cp cookbooks/chatbot.env .env
# 编辑 .env 文件，至少设置：
# MEMOBASE_LLM_API_KEY=your-openai-api-key-here
```

### 2. 运行聊天机器人

```bash
# 基本运行
python cookbooks/memory_chatbot.py

# 指定用户ID
python cookbooks/memory_chatbot.py --user_id alice

# 使用自定义配置
python cookbooks/memory_chatbot.py --config cookbooks/chatbot_config.yaml

# 禁用记忆增强
python cookbooks/memory_chatbot.py --no-memory

# 禁用自动记忆提取
python cookbooks/memory_chatbot.py --no-auto-extract
```

### 3. 聊天机器人命令

在聊天过程中，您可以使用以下命令：

- `/memories` - 查看当前存储的记忆
- `/search [查询]` - 搜索记忆内容
- `/toggle` - 切换记忆增强功能
- `/stats` - 显示会话统计信息
- `/help` - 显示帮助信息
- `/quit` - 退出聊天机器人

## 工作原理

### 记忆提取流程

1. **对话收集**：收集用户的对话内容
2. **批量处理**：每5轮对话后自动提取记忆
3. **结构化存储**：将记忆按主题和子主题组织
4. **向量化索引**：为记忆内容创建向量索引以支持相似度搜索

### 上下文增强流程

1. **记忆检索**：基于当前对话内容搜索相关记忆
2. **上下文构建**：组合用户画像和历史事件
3. **响应生成**：使用增强的上下文生成个性化回答
4. **持续学习**：从新对话中继续学习和更新记忆

## 高级配置

### 数据库后端

聊天机器人支持持久化存储：

- **MySQL**: 存储用户画像和结构化记忆
- **OpenSearch**: 存储事件和支持向量搜索

配置示例（在 .env 文件中）：

```bash
# MySQL配置
MYSQL_USERNAME=your-username
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=chatbot_memories

# OpenSearch配置
OPENSEARCH_ENDPOINT=https://your-opensearch:9200
OPENSEARCH_USERNAME=your-username
OPENSEARCH_PASSWORD=your-password
```

### 记忆系统调优

在 `chatbot_config.yaml` 中调整记忆系统参数：

```yaml
chatbot:
  max_context_tokens: 4000        # 记忆上下文最大token数
  conversation_batch_size: 5      # 每N轮对话提取一次记忆
  memory_search_threshold: 0.2    # 记忆搜索相似度阈值
  max_memory_age_days: 90        # 记忆保留天数
```

## 示例会话

```
🤖 Memory Chatbot initialized for user: demo_user
📚 Memory enhancement: ON
🧠 Auto memory extraction: ON

👤 You: Hello! I'm John, and I love playing tennis on weekends.

🤖 Bot: Hello John! It's great to meet you. I see you enjoy playing tennis on weekends - 
that's a wonderful way to stay active and have fun! I'll remember this about you. 
Do you play at a particular court or club?

👤 You: Yes, I usually play at the Central Park courts with my friend Mike.

🤖 Bot: That sounds lovely! Central Park has beautiful tennis courts. Playing with 
Mike regularly must be a great way to maintain both your friendship and your tennis skills. 
I'll remember that you and Mike are tennis partners at Central Park.

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
   - 确保在 `.env` 文件中设置了正确的 `MEMOBASE_LLM_API_KEY`
   - 检查API密钥是否有效且有足够余额

2. **记忆功能不工作**
   - 检查是否正确配置了数据库连接
   - 确保具有数据库写入权限

3. **搜索功能不可用**
   - 确保设置了 `MEMOBASE_EMBEDDING_API_KEY`
   - 检查 OpenSearch 配置是否正确

### 日志调试

启用详细日志以排查问题：

```bash
# 在配置文件中设置
debug: true
log_level: "DEBUG"
trace_log_enabled: true

# 或通过环境变量
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

### 自定义响应生成

继承 `MemoryChatbot` 类并重写 `generate_response` 方法：

```python
class CustomChatbot(MemoryChatbot):
    async def generate_response(self, user_message: str, context: str = "") -> str:
        # 实现自定义响应逻辑
        return await super().generate_response(user_message, context)
```

## 许可证

此示例遵循 lindormmemobase 包的许可证条款。