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

🌐 **现代化Web界面**
- 实时流式响应
- WebSocket双向通信
- 上下文可视化界面
- 响应式设计，支持移动设备

## 文件说明

- `memory_chatbot.py` - 主要的聊天机器人应用（命令行界面）
- `web_server.py` - Web界面服务器（FastAPI + WebSocket）
- `smart_memory_manager.py` - 智能记忆管理器（性能优化组件）
- `start_web.sh` - 便捷启动脚本
- `config.yaml` - 配置文件模板
- `requirements-web.txt` - Web界面依赖文件
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

#### **核心聊天功能**
- **实时流式对话** - 响应逐字显示，无需等待完整回复
- **记忆上下文指示** - 显示是否使用了记忆上下文增强
- **连接状态监控** - 实时显示WebSocket连接状态
- **记忆提取通知** - 显示后台记忆处理状态

#### **工具栏功能**
- **📚 Memories** - 查看用户存储的所有记忆和画像
- **🧠 Context** - 实时查看当前context buffer内容和缓存统计
- **📊 Stats** - 查看详细的会话统计和性能指标

#### **界面特性**
- **响应式设计** - 支持桌面和移动设备
- **优雅动画** - 打字指示器、连接状态动画
- **模态窗口** - 美观的信息展示弹窗
- **实时反馈** - 即时显示处理状态和错误信息

#### **性能优化**
- **启动预加载** - 服务器启动时预加载context缓存
- **资源共享** - 多个会话共享预加载的memory manager
- **智能清理** - 连接断开时自动清理资源

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

### 5. 快速启动脚本

为了方便使用，提供了启动脚本：

```bash
# 直接运行启动脚本（推荐）
./start_web.sh

# 脚本会自动：
# - 检查并安装依赖
# - 验证配置文件
# - 启动Web服务器
```

## 架构特性

### 智能缓存系统

本聊天机器人采用三层缓存架构：

1. **Profile Cache Layer** - 缓存用户画像（慢更新，快访问）
2. **Event Search Layer** - 实时事件搜索（保证准确性）
3. **Session Memory Layer** - 会话历史管理

### 流式响应系统

- **后端流式处理** - 基于OpenAI API的原生流式支持
- **WebSocket实时通信** - 低延迟的双向通信
- **渐进式显示** - 逐字符实时显示AI响应
- **优雅降级** - 流式失败时自动切换到普通模式

### Context预加载机制

- **启动时预加载** - 服务器启动时自动准备context缓存
- **Memory Manager共享** - 多个会话共享预加载的缓存实例
- **智能查找** - 自动匹配用户的预加载缓存
- **资源优化** - 避免重复创建memory manager


## 工作原理

### 记忆提取流程

1. **对话收集**：收集用户的对话内容
2. **批量处理**：每2轮对话后自动提取记忆（可配置）
3. **结构化存储**：将记忆按主题和子主题组织
4. **向量化索引**：为记忆内容创建向量索引以支持相似度搜索
5. **后台处理**：使用异步队列进行非阻塞记忆提取

### 上下文增强流程

1. **预加载准备**：服务器启动时预先准备context缓存
2. **缓存检索**：快速从缓存中获取相关用户画像
3. **实时搜索**：搜索最新的相关事件
4. **上下文构建**：组合画像、事件和会话历史
5. **流式响应**：使用增强的上下文生成个性化回答
6. **智能更新**：后台定期更新画像缓存

### Web服务架构

1. **FastAPI后端** - 高性能异步Web框架
2. **WebSocket通信** - 实时双向数据传输
3. **资源管理** - 智能的chatbot实例生命周期管理
4. **异常处理** - 全面的错误处理和资源清理

## 高级配置

### 数据库后端

聊天机器人支持持久化存储：

- **Lindorm 宽表**: 存储用户画像和结构化记忆
- **Lindorm Search**: 存储事件和支持向量搜索（替代OpenSearch）


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