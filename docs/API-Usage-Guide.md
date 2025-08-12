# LindormMemobase API 使用指南

## 目录
- [简介](#简介)
- [安装与配置](#安装与配置)
- [核心概念](#核心概念)
- [快速开始](#快速开始)
- [API 参考](#api-参考)
  - [初始化](#初始化)
  - [内存提取](#内存提取)
  - [用户档案管理](#用户档案管理)
  - [事件管理](#事件管理)
  - [上下文生成](#上下文生成)
  - [缓冲区管理](#缓冲区管理)
- [高级用法](#高级用法)
- [完整示例](#完整示例)

## 简介

LindormMemobase 是一个轻量级的记忆提取和用户档案管理系统，专为 LLM 应用设计。它提供了以下核心功能：

- **记忆提取**：从对话中自动提取和结构化用户信息
- **用户档案管理**：维护和更新用户的长期记忆档案
- **语义搜索**：基于向量嵌入的相似度搜索
- **上下文生成**：为对话生成相关的历史上下文
- **缓冲区管理**：智能的数据缓冲和批量处理机制

## 安装与配置

### 安装

```bash
pip install lindormmemobase
```

### 配置方式

LindormMemobase 采用分层配置策略，优先级从高到低为：
1. **环境变量**（覆盖所有其他配置）
2. **config.yaml**（项目级配置）
3. **默认值**（内置默认配置）

推荐实践：
- **敏感信息**（API密钥、密码）放在 `.env` 文件或环境变量中
- **项目配置**（模型选择、功能开关）放在 `config.yaml` 中
- 环境变量会自动覆盖 config.yaml 中的同名配置

#### 1. 环境变量配置（.env 文件）

创建 `.env` 文件存储敏感信息和连接配置：

```bash
# API 密钥和认证信息（敏感信息）
MEMOBASE_LLM_API_KEY=your-openai-api-key
MEMOBASE_EMBEDDING_API_KEY=your-embedding-api-key  # 可选，默认使用 LLM_API_KEY

# Lindorm Table (MySQL协议) 连接配置
MEMOBASE_LINDORM_TABLE_HOST=localhost
MEMOBASE_LINDORM_TABLE_PORT=33060
MEMOBASE_LINDORM_TABLE_USERNAME=root
MEMOBASE_LINDORM_TABLE_PASSWORD=your-table-password
MEMOBASE_LINDORM_TABLE_DATABASE=memobase

# Lindorm Search 连接配置
MEMOBASE_LINDORM_SEARCH_HOST=localhost
MEMOBASE_LINDORM_SEARCH_PORT=30070
MEMOBASE_LINDORM_SEARCH_USERNAME=search-username  
MEMOBASE_LINDORM_SEARCH_PASSWORD=search-password  
MEMOBASE_LINDORM_SEARCH_USE_SSL=false

# 自定义 API 端点（可选，用于私有部署）
MEMOBASE_LLM_BASE_URL=https://your-custom-api.com/v1
MEMOBASE_EMBEDDING_BASE_URL=https://your-embedding-api.com/v1
```

#### 2. 项目配置文件（config.yaml）

创建 `config.yaml` 文件定义应用级配置：

```yaml
# 语言和本地化设置
language: zh  # 支持 en（英文）或 zh（中文）
use_timezone: Asia/Shanghai  # 时区设置：UTC, America/New_York, Europe/London, Asia/Tokyo, Asia/Shanghai

# LLM 模型选择
best_llm_model: gpt-4o-mini  # 主要模型
thinking_llm_model: o4-mini   # 思考链模型
summary_llm_model: gpt-3.5-turbo  # 摘要模型（可选）

# 索引名称配置（通常不需要修改）
lindorm_search_events_index: memobase_events
lindorm_search_event_gists_index: memobase_event_gists

# 嵌入配置
enable_event_embedding: true
embedding_provider: openai  # 可选：openai 或 jina
embedding_model: text-embedding-3-small
embedding_dim: 1536
embedding_max_token_size: 8192

# 记忆提取配置
max_profile_subtopics: 15  # 每个主题的最大子主题数
max_chat_blob_buffer_process_token_size: 16384  # 对话缓冲区大小
minimum_chats_token_size_for_event_summary: 256  # 触发事件摘要的最小token数

# 缓冲区管理配置
max_chat_blob_buffer_token_size: 8192  # 缓冲区最大token数，达到此值自动触发处理

# 档案管理设置
profile_strict_mode: false  # 严格模式
profile_validate_mode: true  # 验证模式
event_theme_requirement: "Focus on the user's infos, not its instructions"

# 高级配置（通常不需要修改）
persistent_chat_blobs: false  # 是否持久化对话数据
llm_tab_separator: "::"  # LLM 输出分隔符
max_pre_profile_token_size: 128  # 预处理档案的最大token数
```

#### 3. 完整配置示例

**项目结构：**
```
your-project/
├── .env                    # 敏感信息（加入 .gitignore）
├── .env.example           # 环境变量模板（可提交到代码库）
├── config.yaml            # 项目配置（可提交到代码库）
├── config.yaml.example    # 配置模板
└── main.py               # 应用代码
```

**.env.example**（模板文件，提交到代码库）：
```bash
# 复制此文件为 .env 并填入实际值

# === API 密钥配置 ===
MEMOBASE_LLM_API_KEY=your-openai-api-key-here
# MEMOBASE_EMBEDDING_API_KEY=optional-separate-embedding-key

# === Lindorm Table 连接配置 ===
MEMOBASE_LINDORM_TABLE_HOST=localhost
MEMOBASE_LINDORM_TABLE_PORT=33060
MEMOBASE_LINDORM_TABLE_USERNAME=root
MEMOBASE_LINDORM_TABLE_PASSWORD=your-password-here
MEMOBASE_LINDORM_TABLE_DATABASE=memobase

# === Lindorm Search 连接配置 ===
MEMOBASE_LINDORM_SEARCH_HOST=localhost
MEMOBASE_LINDORM_SEARCH_PORT=30070
# MEMOBASE_LINDORM_SEARCH_USERNAME=optional-if-auth-enabled
# MEMOBASE_LINDORM_SEARCH_PASSWORD=optional-if-auth-enabled
# MEMOBASE_LINDORM_SEARCH_USE_SSL=false

# === 自定义端点（可选） ===
# MEMOBASE_LLM_BASE_URL=https://your-custom-api.com/v1
# MEMOBASE_EMBEDDING_BASE_URL=https://your-embedding-api.com/v1
```

**config.yaml.example**（配置模板）：
```yaml
# === 基础配置 ===
language: zh  # 选择语言：en 或 zh
use_timezone: Asia/Shanghai  # 时区设置

# === 模型配置 ===
# 根据需求和成本选择合适的模型
best_llm_model: gpt-4o-mini  # 可选：gpt-4o, gpt-3.5-turbo
thinking_llm_model: o4-mini  # 思考链模型
embedding_model: text-embedding-3-small  # 可选：text-embedding-3-large

# === 嵌入配置 ===
enable_event_embedding: true
embedding_provider: openai  # 或 jina
embedding_dim: 1536

# === 记忆提取配置 ===
max_profile_subtopics: 15
profile_validate_mode: true

# === 索引名称（通常不需要修改）===
lindorm_search_events_index: memobase_events
lindorm_search_event_gists_index: memobase_event_gists
```

#### 4. 配置加载顺序

```python
from lindormmemobase import LindormMemobase

# 方式1：自动加载（推荐）
# 自动按以下顺序加载：
# 1. 读取 config.yaml（如果存在）
# 2. 读取环境变量（覆盖 config.yaml 中的同名项）
# 3. 使用默认值（未配置的项）
memobase = LindormMemobase()

# 方式2：指定配置文件
memobase = LindormMemobase.from_yaml_file("custom-config.yaml")

# 方式3：代码中覆盖（最高优先级）
memobase = LindormMemobase.from_config(
    language="en",  # 覆盖配置文件中的语言设置
    best_llm_model="gpt-4o"  # 覆盖模型选择
)
```

#### 5. 配置最佳实践

**开发环境：**
- 使用 `.env` 文件管理 API 密钥
- 在 `config.yaml` 中使用较小的模型降低成本
- 启用所有调试和验证选项

**生产环境：**
- 使用环境变量注入敏感信息（不使用 .env 文件）
- 在 `config.yaml` 中配置性能优化参数
- 根据负载调整 token 限制和缓冲区大小

**多环境管理：**
```bash
# 开发环境
cp config.dev.yaml config.yaml
export MEMOBASE_LLM_API_KEY=$DEV_API_KEY

# 测试环境
cp config.test.yaml config.yaml
export MEMOBASE_LLM_API_KEY=$TEST_API_KEY

# 生产环境
cp config.prod.yaml config.yaml
export MEMOBASE_LLM_API_KEY=$PROD_API_KEY
```

**Docker 部署示例：**
```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制配置文件（不包含敏感信息）
COPY config.yaml .
COPY . .

# 运行时通过环境变量注入敏感信息
# docker run -e MEMOBASE_LLM_API_KEY=xxx ...
CMD ["python", "main.py"]
```

## 核心概念

### 1. Blob（数据块）

Blob 是输入数据的基本单位，支持多种类型：

- **ChatBlob**: 对话消息
- **DocBlob**: 文档内容
- **CodeBlob**: 代码片段
- **ImageBlob**: 图像数据
- **TranscriptBlob**: 音频转录

### 2. Profile（用户档案）

用户档案按主题（topic）和子主题（subtopic）组织：

```python
Profile(
    topic="personal_info",
    subtopics={
        "basic": ProfileEntry(content="张小明，25岁，软件工程师"),
        "location": ProfileEntry(content="在北京工作")
    }
)
```

### 3. Event（事件）

事件是带时间戳的用户活动记录，支持语义搜索。

### 4. ProfileConfig（档案配置）

控制记忆提取行为的配置对象。

## API 参考

### 初始化

#### 方法 1：使用默认配置

```python
from lindormmemobase import LindormMemobase

# 自动从环境变量和 config.yaml 加载配置
memobase = LindormMemobase()
```

#### 方法 2：从 YAML 文件加载

```python
# 指定配置文件路径
memobase = LindormMemobase.from_yaml_file("path/to/config.yaml")
```

#### 方法 3：使用参数初始化

```python
# 直接传入配置参数
memobase = LindormMemobase.from_config(
    language="zh",
    llm_api_key="your-api-key",
    best_llm_model="gpt-4o",
    lindorm_table_host="localhost",
    lindorm_table_port=33060
)
```

#### 方法 4：使用 Config 对象

```python
from lindormmemobase import Config

config = Config(
    language="zh",
    llm_api_key="your-api-key",
    lindorm_table_host="localhost"
)
memobase = LindormMemobase(config)
```

### 内存提取

从用户对话中提取结构化信息并更新档案：

```python
async def extract_memories(
    user_id: str,
    blobs: List[Blob],
    profile_config: Optional[ProfileConfig] = None
) -> Dict
```

**参数说明：**
- `user_id`: 用户唯一标识符
- `blobs`: 要处理的数据块列表
- `profile_config`: 档案配置（可选）

**示例：**

```python
from lindormmemobase.models.blob import ChatBlob, OpenAICompatibleMessage

# 创建对话数据
conversation = ChatBlob(
    messages=[
        OpenAICompatibleMessage(
            role="user", 
            content="我喜欢打篮球和游泳"
        ),
        OpenAICompatibleMessage(
            role="assistant", 
            content="很好的运动爱好！"
        )
    ]
)

# 提取记忆
result = await memobase.extract_memories(
    user_id="user123",
    blobs=[conversation]
)
```

### 用户档案管理

#### 获取用户档案

```python
async def get_user_profiles(
    user_id: str,
    topics: Optional[List[str]] = None
) -> List[Profile]
```

**参数说明：**
- `user_id`: 用户标识符
- `topics`: 要筛选的主题列表（可选）

**示例：**

```python
# 获取所有档案
profiles = await memobase.get_user_profiles("user123")

# 只获取特定主题
profiles = await memobase.get_user_profiles(
    "user123", 
    topics=["interests", "preferences"]
)

# 遍历档案
for profile in profiles:
    print(f"主题: {profile.topic}")
    for subtopic, entry in profile.subtopics.items():
        print(f"  {subtopic}: {entry.content}")
```

#### 获取相关档案

根据当前对话内容智能筛选相关档案：

```python
async def get_relevant_profiles(
    user_id: str,
    conversation: List[OpenAICompatibleMessage],
    topics: Optional[List[str]] = None,
    max_profiles: int = 10,
    max_profile_token_size: int = 4000
) -> List[Profile]
```

**示例：**

```python
conversation = [
    OpenAICompatibleMessage(
        role="user", 
        content="我想规划下个月的旅行"
    )
]

relevant_profiles = await memobase.get_relevant_profiles(
    user_id="user123",
    conversation=conversation,
    topics=["travel", "preferences"],
    max_profiles=5
)
```

#### 搜索档案

基于文本查询搜索档案：

```python
async def search_profiles(
    user_id: str,
    query: str,
    topics: Optional[List[str]] = None,
    max_results: int = 10
) -> List[Profile]
```

**示例：**

```python
profiles = await memobase.search_profiles(
    user_id="user123",
    query="最喜欢的餐厅",
    topics=["food", "dining"],
    max_results=5
)
```

### 事件管理

#### 获取最近事件

```python
async def get_events(
    user_id: str,
    time_range_in_days: int = 21,
    limit: int = 100
) -> List[dict]
```

**返回格式：**
```python
{
    "id": "event_id",
    "content": "事件内容",
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
}
```

**示例：**

```python
# 获取最近 30 天的事件
events = await memobase.get_events(
    user_id="user123",
    time_range_in_days=30,
    limit=50
)

for event in events:
    print(f"{event['created_at']}: {event['content']}")
```

#### 搜索事件

使用语义搜索查找相关事件：

```python
async def search_events(
    user_id: str,
    query: str,
    limit: int = 10,
    similarity_threshold: float = 0.2,
    time_range_in_days: int = 21
) -> List[dict]
```

**参数说明：**
- `query`: 搜索查询文本
- `similarity_threshold`: 相似度阈值（0.0-1.0）
- `time_range_in_days`: 搜索时间范围

**示例：**

```python
# 搜索与"项目进度"相关的事件
events = await memobase.search_events(
    user_id="user123",
    query="项目进度会议",
    limit=5,
    similarity_threshold=0.3,
    time_range_in_days=7
)

for event in events:
    similarity = event['similarity']
    print(f"相似度 {similarity:.2f}: {event['content']}")
```

### 上下文生成

为对话生成包含用户档案和相关事件的上下文：

```python
async def get_conversation_context(
    user_id: str,
    conversation: List[OpenAICompatibleMessage],
    profile_config: Optional[ProfileConfig] = None,
    max_token_size: int = 2000,
    prefer_topics: Optional[List[str]] = None,
    time_range_in_days: int = 30,
    event_similarity_threshold: float = 0.2,
    profile_event_ratio: float = 0.6,
    require_event_summary: bool = False,
    customize_context_prompt: Optional[str] = None
) -> str
```

**重要参数：**
- `max_token_size`: 上下文最大 token 数
- `prefer_topics`: 优先选择的主题
- `profile_event_ratio`: 档案与事件内容的比例（0.6 表示 60% 档案，40% 事件）
- `require_event_summary`: 是否包含事件摘要
- `customize_context_prompt`: 自定义上下文生成提示

**示例：**

```python
conversation = [
    OpenAICompatibleMessage(
        role="user", 
        content="今天晚上吃什么好？"
    )
]

context = await memobase.get_conversation_context(
    user_id="user123",
    conversation=conversation,
    prefer_topics=["dietary_preferences", "favorite_foods"],
    max_token_size=1500,
    profile_event_ratio=0.7,  # 70% 档案，30% 事件
    time_range_in_days=14
)

print(f"生成的上下文：\n{context}")
```

### 缓冲区管理

LindormMemobase 提供智能的缓冲区管理功能，能够自动收集和批量处理对话数据，提高记忆提取的效率。

#### 核心概念

- **缓冲区**: 临时存储待处理的对话数据
- **批量处理**: 当缓冲区达到一定容量时自动触发处理
- **状态管理**: 跟踪每个数据块的处理状态（idle、processing、done、failed）
- **智能调度**: 根据token大小和数据量智能决定处理时机

#### 添加数据到缓冲区

```python
async def add_blob_to_buffer(
    user_id: str,
    blob: Blob,
    blob_id: Optional[str] = None
) -> str
```

**参数说明：**
- `user_id`: 用户唯一标识符
- `blob`: 要添加的数据块（ChatBlob、DocBlob等）
- `blob_id`: 可选的自定义ID，默认生成UUID

**示例：**

```python
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage

# 创建聊天数据块
chat_blob = ChatBlob(
    messages=[
        OpenAICompatibleMessage(role="user", content="我喜欢喝咖啡"),
        OpenAICompatibleMessage(role="assistant", content="咖啡是很好的选择！")
    ],
    type=BlobType.chat
)

# 添加到缓冲区
blob_id = await memobase.add_blob_to_buffer("user123", chat_blob)
print(f"已添加到缓冲区: {blob_id}")
```

#### 检测缓冲区状态

```python
async def detect_buffer_full_or_not(
    user_id: str,
    blob_type: BlobType = BlobType.chat
) -> Dict[str, Any]
```

**返回格式：**
```python
{
    "is_full": True,  # 是否需要处理
    "buffer_full_ids": ["blob_id_1", "blob_id_2"],  # 需要处理的数据块ID列表
    "blob_type": "BlobType.chat"  # 数据块类型
}
```

**示例：**

```python
# 检查缓冲区状态
status = await memobase.detect_buffer_full_or_not("user123", BlobType.chat)

print(f"缓冲区已满: {status['is_full']}")
print(f"待处理的数据块数量: {len(status['buffer_full_ids'])}")

if status["is_full"]:
    print("需要处理缓冲区中的数据")
```

#### 处理缓冲区数据

```python
async def process_buffer(
    user_id: str,
    blob_type: BlobType = BlobType.chat,
    profile_config: Optional[ProfileConfig] = None,
    blob_ids: Optional[List[str]] = None
) -> Optional[Any]
```

**参数说明：**
- `user_id`: 用户标识符
- `blob_type`: 处理的数据类型
- `profile_config`: 档案配置（可选）
- `blob_ids`: 指定要处理的数据块ID列表，为None时处理所有未处理的数据

**示例：**

```python
# 处理所有未处理的聊天数据
result = await memobase.process_buffer("user123", BlobType.chat)
if result:
    print("缓冲区处理完成")

# 处理特定的数据块
result = await memobase.process_buffer(
    user_id="user123",
    blob_type=BlobType.chat,
    blob_ids=["blob_id_1", "blob_id_2"],
    profile_config=ProfileConfig(language="zh")
)
```

#### 自动化工作流程示例

```python
async def smart_chat_processing(user_id: str, user_messages: List[str]):
    """智能对话处理流程，集成缓冲区管理"""
    
    for message_content in user_messages:
        # 1. 创建聊天数据块
        chat_blob = ChatBlob(
            messages=[OpenAICompatibleMessage(role="user", content=message_content)],
            type=BlobType.chat
        )
        
        # 2. 添加到缓冲区
        blob_id = await memobase.add_blob_to_buffer(user_id, chat_blob)
        print(f"消息已缓冲: {blob_id}")
        
        # 3. 检查缓冲区状态
        status = await memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
        
        # 4. 自动处理满载的缓冲区
        if status["is_full"]:
            print(f"缓冲区已满，开始处理 {len(status['buffer_full_ids'])} 个数据块...")
            
            result = await memobase.process_buffer(
                user_id=user_id,
                blob_type=BlobType.chat,
                blob_ids=status["buffer_full_ids"]
            )
            
            if result:
                print("✓ 缓冲区处理完成，记忆已提取")
            else:
                print("✗ 缓冲区处理失败")

# 使用示例
messages = [
    "我是李四，在上海工作",
    "我喜欢跑步和看电影", 
    "最近在学习Python编程",
    "周末计划去博物馆"
]

await smart_chat_processing("user456", messages)
```

#### 批量对话处理与缓冲区集成

```python
class BufferedConversationProcessor:
    """带缓冲区的对话处理器"""
    
    def __init__(self, memobase: LindormMemobase):
        self.memobase = memobase
        self.pending_messages = {}  # 用户ID -> 消息列表
    
    async def add_message(self, user_id: str, role: str, content: str):
        """添加单条消息到处理队列"""
        if user_id not in self.pending_messages:
            self.pending_messages[user_id] = []
        
        self.pending_messages[user_id].append(
            OpenAICompatibleMessage(role=role, content=content)
        )
        
        # 每积累5条消息就添加到缓冲区
        if len(self.pending_messages[user_id]) >= 5:
            await self._flush_to_buffer(user_id)
    
    async def _flush_to_buffer(self, user_id: str):
        """将积累的消息添加到缓冲区"""
        if user_id not in self.pending_messages or not self.pending_messages[user_id]:
            return
        
        # 创建聊天数据块
        chat_blob = ChatBlob(
            messages=self.pending_messages[user_id],
            type=BlobType.chat
        )
        
        # 添加到缓冲区
        blob_id = await self.memobase.add_blob_to_buffer(user_id, chat_blob)
        print(f"对话块已添加到缓冲区: {blob_id}")
        
        # 清空待处理消息
        self.pending_messages[user_id] = []
        
        # 检查是否需要处理缓冲区
        await self._check_and_process_buffer(user_id)
    
    async def _check_and_process_buffer(self, user_id: str):
        """检查并处理缓冲区"""
        status = await self.memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
        
        if status["is_full"]:
            print(f"开始处理用户 {user_id} 的缓冲区...")
            result = await self.memobase.process_buffer(
                user_id=user_id,
                blob_type=BlobType.chat,
                blob_ids=status["buffer_full_ids"]
            )
            
            if result:
                print(f"✓ 用户 {user_id} 缓冲区处理完成")
                return True
            else:
                print(f"✗ 用户 {user_id} 缓冲区处理失败")
                return False
        return False
    
    async def force_process_all(self, user_id: str):
        """强制处理用户的所有数据"""
        # 先将待处理消息刷入缓冲区
        await self._flush_to_buffer(user_id)
        
        # 处理所有缓冲区数据
        result = await self.memobase.process_buffer(user_id, BlobType.chat)
        return result is not None

# 使用示例
processor = BufferedConversationProcessor(memobase)

# 模拟实时对话
await processor.add_message("user789", "user", "你好，我是新用户")
await processor.add_message("user789", "assistant", "欢迎！很高兴认识您")
await processor.add_message("user789", "user", "我想了解一下这个系统")
# ... 更多消息

# 强制处理所有待处理数据
await processor.force_process_all("user789")
```

#### 缓冲区配置优化

**config.yaml 配置：**

```yaml
# 缓冲区大小配置
max_chat_blob_buffer_token_size: 8192  # 缓冲区最大token数，建议根据实际使用调整

# 处理限制配置  
max_chat_blob_buffer_process_token_size: 16384  # 单次处理最大token数

# 根据不同场景调整：
# - 低频对话场景：可设置较小的缓冲区大小（如4096）
# - 高频对话场景：可设置较大的缓冲区大小（如16384）
# - 实时响应场景：设置较小的缓冲区确保及时处理
# - 批处理场景：设置较大的缓冲区提高处理效率
```

#### 错误处理与监控

```python
async def robust_buffer_processing(user_id: str, messages: List[str]):
    """带错误处理的缓冲区处理"""
    
    for i, message in enumerate(messages):
        try:
            # 添加消息到缓冲区
            chat_blob = ChatBlob(
                messages=[OpenAICompatibleMessage(role="user", content=message)],
                type=BlobType.chat
            )
            
            blob_id = await memobase.add_blob_to_buffer(user_id, chat_blob)
            print(f"[{i+1}/{len(messages)}] 消息已缓冲: {blob_id}")
            
            # 检查缓冲区状态
            status = await memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
            
            if status["is_full"]:
                print(f"处理缓冲区中的 {len(status['buffer_full_ids'])} 个数据块...")
                
                # 处理缓冲区
                result = await memobase.process_buffer(
                    user_id=user_id,
                    blob_type=BlobType.chat,
                    blob_ids=status["buffer_full_ids"]
                )
                
                if result:
                    print("✓ 缓冲区处理成功")
                else:
                    print("⚠️ 缓冲区处理返回空结果")
                    
        except Exception as e:
            print(f"✗ 处理消息 {i+1} 时出错: {e}")
            # 记录错误但继续处理下一条消息
            continue
    
    # 最终检查是否还有未处理的数据
    try:
        final_status = await memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
        if final_status["buffer_full_ids"]:
            print("处理剩余缓冲区数据...")
            await memobase.process_buffer(user_id, BlobType.chat)
    except Exception as e:
        print(f"最终处理出错: {e}")

# 使用示例
test_messages = [
    "我叫王五，在深圳工作",
    "我是一名数据科学家",
    "喜欢研究机器学习算法", 
    "业余时间喜欢踢足球",
    "最近在关注大语言模型的发展"
]

await robust_buffer_processing("user_wang", test_messages)
```

## 高级用法

### 自定义档案配置

```python
from lindormmemobase.models.profile_topic import ProfileConfig

# 创建自定义档案配置
profile_config = ProfileConfig(
    language="zh",
    overwrite_user_profiles=[
        {
            "topic": "health",
            "subtopics": ["exercise", "diet", "sleep"]
        },
        {
            "topic": "work",
            "subtopics": ["projects", "skills", "goals"]
        }
    ],
    event_tags=[
        {"name": "important", "description": "重要事件"},
        {"name": "milestone", "description": "里程碑"}
    ]
)

# 使用自定义配置提取记忆
result = await memobase.extract_memories(
    user_id="user123",
    blobs=conversation_blobs,
    profile_config=profile_config
)
```

### 批量处理对话

```python
async def process_conversation_history(user_id: str, messages: List[dict]):
    """批量处理历史对话"""
    
    # 将消息分组为对话块
    blobs = []
    batch_size = 10  # 每个块包含10条消息
    
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i+batch_size]
        chat_blob = ChatBlob(
            messages=[
                OpenAICompatibleMessage(
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg.get("timestamp")
                )
                for msg in batch
            ]
        )
        blobs.append(chat_blob)
    
    # 批量提取记忆
    result = await memobase.extract_memories(
        user_id=user_id,
        blobs=blobs
    )
    
    return result
```

### 实时对话集成

```python
class ConversationManager:
    """对话管理器，集成记忆系统"""
    
    def __init__(self, memobase: LindormMemobase):
        self.memobase = memobase
        self.conversation_buffer = []
    
    async def process_message(self, user_id: str, role: str, content: str):
        """处理单条消息"""
        
        # 添加到缓冲区
        message = OpenAICompatibleMessage(role=role, content=content)
        self.conversation_buffer.append(message)
        
        # 每 5 条消息提取一次记忆
        if len(self.conversation_buffer) >= 5:
            blob = ChatBlob(messages=self.conversation_buffer)
            
            # 异步提取记忆
            await self.memobase.extract_memories(
                user_id=user_id,
                blobs=[blob]
            )
            
            # 清空缓冲区
            self.conversation_buffer = []
    
    async def get_context_for_reply(self, user_id: str, current_message: str):
        """为回复生成上下文"""
        
        conversation = [
            OpenAICompatibleMessage(role="user", content=current_message)
        ]
        
        # 获取相关上下文
        context = await self.memobase.get_conversation_context(
            user_id=user_id,
            conversation=conversation,
            max_token_size=1000
        )
        
        return context
```

### 错误处理

```python
from lindormmemobase import LindormMemobaseError, ConfigurationError

async def safe_extract_memories(memobase, user_id, blobs):
    """带错误处理的记忆提取"""
    try:
        result = await memobase.extract_memories(
            user_id=user_id,
            blobs=blobs
        )
        return result
    
    except ConfigurationError as e:
        print(f"配置错误: {e}")
        # 处理配置问题
        return None
    
    except LindormMemobaseError as e:
        print(f"提取失败: {e}")
        # 处理提取错误
        return None
    
    except Exception as e:
        print(f"未知错误: {e}")
        # 处理其他错误
        return None
```

## 完整示例

### 示例 1：聊天机器人集成

```python
import asyncio
from typing import List
from lindormmemobase import LindormMemobase
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage
from lindormmemobase.models.profile_topic import ProfileConfig

class MemoryEnabledChatbot:
    """带记忆功能的聊天机器人"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.memobase = LindormMemobase.from_yaml_file(config_path)
        self.profile_config = ProfileConfig(language="zh")
        self.conversation_history = []
    
    async def initialize_user(self, user_id: str):
        """初始化用户档案"""
        profiles = await self.memobase.get_user_profiles(user_id)
        if not profiles:
            print(f"新用户 {user_id}，开始建立档案")
        else:
            print(f"已加载用户 {user_id} 的 {len(profiles)} 个档案主题")
        return profiles
    
    async def chat(self, user_id: str, user_input: str) -> str:
        """处理用户输入并生成回复"""
        
        # 1. 记录用户输入
        user_message = OpenAICompatibleMessage(
            role="user",
            content=user_input
        )
        self.conversation_history.append(user_message)
        
        # 2. 获取相关上下文
        context = await self.memobase.get_conversation_context(
            user_id=user_id,
            conversation=self.conversation_history[-10:],  # 最近10条消息
            max_token_size=1500,
            prefer_topics=self._infer_topics(user_input),
            time_range_in_days=30
        )
        
        # 3. 生成回复（这里模拟 LLM 调用）
        assistant_reply = await self._generate_reply(context, user_input)
        
        # 4. 记录助手回复
        assistant_message = OpenAICompatibleMessage(
            role="assistant",
            content=assistant_reply
        )
        self.conversation_history.append(assistant_message)
        
        # 5. 异步提取记忆（每2轮对话提取一次）
        if len(self.conversation_history) % 4 == 0:
            await self._extract_memories_async(user_id)
        
        return assistant_reply
    
    def _infer_topics(self, user_input: str) -> List[str]:
        """推断相关主题"""
        topic_keywords = {
            "work": ["工作", "项目", "会议", "任务"],
            "health": ["健康", "运动", "睡眠", "饮食"],
            "interests": ["爱好", "喜欢", "兴趣", "娱乐"],
            "personal_info": ["我是", "我叫", "年龄", "住在"]
        }
        
        relevant_topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in user_input for keyword in keywords):
                relevant_topics.append(topic)
        
        return relevant_topics if relevant_topics else ["general"]
    
    async def _generate_reply(self, context: str, user_input: str) -> str:
        """生成回复（模拟）"""
        # 实际应用中，这里会调用 LLM API
        # 示例：response = await llm.generate(prompt=f"{context}\n用户：{user_input}")
        return f"理解了您的需求。基于您的档案信息，我了解到：{context[:100]}..."
    
    async def _extract_memories_async(self, user_id: str):
        """使用缓冲区异步提取记忆"""
        # 创建对话块并添加到缓冲区
        blob = ChatBlob(
            messages=self.conversation_history[-4:]  # 最近2轮对话
        )
        
        try:
            # 添加到缓冲区
            blob_id = await self.memobase.add_blob_to_buffer(user_id, blob)
            print(f"对话已添加到缓冲区: {blob_id}")
            
            # 检查是否需要处理缓冲区
            status = await self.memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
            
            if status["is_full"]:
                print(f"缓冲区已满，开始处理 {len(status['buffer_full_ids'])} 个数据块...")
                result = await self.memobase.process_buffer(
                    user_id=user_id,
                    blob_type=BlobType.chat,
                    profile_config=self.profile_config,
                    blob_ids=status["buffer_full_ids"]
                )
                
                if result:
                    print("✓ 缓冲区处理完成，记忆已提取")
                else:
                    print("⚠️ 缓冲区处理返回空结果")
                    
        except Exception as e:
            print(f"缓冲区处理失败: {e}")
    
    async def force_extract_all_memories(self, user_id: str):
        """强制处理所有缓冲区数据"""
        try:
            result = await self.memobase.process_buffer(user_id, BlobType.chat)
            if result:
                print("✓ 所有缓冲区数据已处理完成")
                return True
            else:
                print("⚠️ 没有待处理的缓冲区数据")
                return False
        except Exception as e:
            print(f"强制处理缓冲区失败: {e}")
            return False
    
    async def get_user_summary(self, user_id: str) -> str:
        """获取用户档案摘要"""
        profiles = await self.memobase.get_user_profiles(user_id)
        
        summary = []
        for profile in profiles:
            summary.append(f"【{profile.topic}】")
            for subtopic, entry in profile.subtopics.items():
                summary.append(f"  - {subtopic}: {entry.content}")
        
        return "\n".join(summary)

# 使用示例
async def main():
    # 初始化聊天机器人
    chatbot = MemoryEnabledChatbot()
    user_id = "test_user_001"
    
    # 初始化用户
    await chatbot.initialize_user(user_id)
    
    # 模拟对话
    conversations = [
        "你好，我是小明，今年28岁，是一名产品经理",
        "我喜欢看科幻电影和打羽毛球",
        "最近工作压力有点大，经常加班到很晚",
        "周末想去爬山放松一下"
    ]
    
    for user_input in conversations:
        print(f"\n用户: {user_input}")
        reply = await chatbot.chat(user_id, user_input)
        print(f"助手: {reply}")
        await asyncio.sleep(1)  # 模拟对话间隔
    
    # 强制处理所有剩余缓冲区数据
    print("\n=== 处理剩余缓冲区数据 ===")
    await chatbot.force_extract_all_memories(user_id)
    
    # 查看用户档案
    print("\n=== 用户档案摘要 ===")
    summary = await chatbot.get_user_summary(user_id)
    print(summary)
    
    # 搜索相关记忆
    print("\n=== 搜索相关记忆 ===")
    events = await chatbot.memobase.search_events(
        user_id=user_id,
        query="运动爱好",
        limit=3
    )
    for event in events:
        print(f"- {event['content']}")
    
    # 演示缓冲区状态检查
    print("\n=== 缓冲区状态检查 ===")
    status = await chatbot.memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
    print(f"缓冲区已满: {status['is_full']}")
    print(f"待处理数据块数量: {len(status['buffer_full_ids'])}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 2：缓冲区管理专用示例

```python
import asyncio
from typing import List
from lindormmemobase import LindormMemobase
from lindormmemobase.models.blob import ChatBlob, BlobType, OpenAICompatibleMessage

async def buffer_management_demo():
    """完整的缓冲区管理演示"""
    
    # 初始化
    memobase = LindormMemobase()
    user_id = "buffer_demo_user"
    
    print("=== 缓冲区管理演示 ===\n")
    
    # 1. 准备测试对话数据
    conversations = [
        ["user", "我是张三，在北京从事AI研发工作"],
        ["assistant", "您好张三！AI研发是很有前景的领域。"],
        ["user", "我平时喜欢阅读技术书籍和跑步"],
        ["assistant", "阅读和跑步都是很好的习惯！"],
        ["user", "最近在研究大语言模型的应用"],
        ["assistant", "LLM确实是当前的热点技术。"],
        ["user", "我希望能在这个领域有所突破"],
        ["assistant", "相信您一定可以的！"],
        ["user", "周末计划去图书馆学习新技术"],
        ["assistant", "充实的周末安排！"]
    ]
    
    # 2. 批量添加对话到缓冲区
    print("1. 批量添加对话到缓冲区...")
    blob_ids = []
    
    for i in range(0, len(conversations), 2):  # 每2条消息一个对话块
        if i + 1 < len(conversations):
            # 创建对话块
            chat_blob = ChatBlob(
                messages=[
                    OpenAICompatibleMessage(role=conversations[i][0], content=conversations[i][1]),
                    OpenAICompatibleMessage(role=conversations[i+1][0], content=conversations[i+1][1])
                ],
                type=BlobType.chat
            )
            
            # 添加到缓冲区
            blob_id = await memobase.add_blob_to_buffer(user_id, chat_blob)
            blob_ids.append(blob_id)
            print(f"   ✓ 对话块 {len(blob_ids)} 已添加: {blob_id}")
            
            # 每添加一个对话块就检查缓冲区状态
            status = await memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
            print(f"   - 缓冲区状态: {'已满' if status['is_full'] else '未满'} "
                  f"(待处理: {len(status['buffer_full_ids'])} 个)")
            
            if status["is_full"]:
                print(f"   🔄 缓冲区已满，自动处理 {len(status['buffer_full_ids'])} 个数据块...")
                result = await memobase.process_buffer(
                    user_id=user_id,
                    blob_type=BlobType.chat,
                    blob_ids=status["buffer_full_ids"]
                )
                
                if result:
                    print(f"   ✅ 缓冲区处理完成")
                else:
                    print(f"   ⚠️ 缓冲区处理返回空结果")
            
            print()  # 空行分隔
    
    # 3. 处理剩余的缓冲区数据
    print("2. 检查并处理剩余缓冲区数据...")
    final_status = await memobase.detect_buffer_full_or_not(user_id, BlobType.chat)
    
    if final_status["buffer_full_ids"]:
        print(f"   发现 {len(final_status['buffer_full_ids'])} 个未处理的数据块")
        result = await memobase.process_buffer(user_id, BlobType.chat)
        if result:
            print("   ✅ 剩余数据处理完成")
    else:
        print("   ℹ️ 没有剩余的未处理数据")
    
    # 4. 验证处理结果
    print("\n3. 验证处理结果...")
    
    # 获取用户档案
    profiles = await memobase.get_user_profiles(user_id)
    print(f"   生成用户档案: {len(profiles)} 个主题")
    
    for profile in profiles:
        print(f"   📝 主题: {profile.topic}")
        for subtopic, entry in profile.subtopics.items():
            print(f"      └── {subtopic}: {entry.content}")
    
    # 获取事件
    events = await memobase.get_events(user_id, time_range_in_days=7, limit=10)
    print(f"\n   生成事件记录: {len(events)} 条")
    for event in events[:3]:  # 只显示前3条
        print(f"   📅 {event['content']}")
    
    # 5. 演示搜索功能
    print("\n4. 搜索相关记忆...")
    search_results = await memobase.search_events(
        user_id=user_id,
        query="技术学习",
        limit=3,
        similarity_threshold=0.1
    )
    
    print(f"   找到 {len(search_results)} 条相关记录:")
    for result in search_results:
        similarity = result.get('similarity', 0)
        print(f"   🔍 (相似度: {similarity:.2f}) {result['content']}")
    
    print(f"\n✨ 缓冲区管理演示完成！用户 {user_id} 的记忆系统已建立")

# 运行演示
if __name__ == "__main__":
    asyncio.run(buffer_management_demo())
```

### 示例 3：批量数据导入

```python
import asyncio
import json
from datetime import datetime, timedelta
from lindormmemobase import LindormMemobase
from lindormmemobase.models.blob import ChatBlob, OpenAICompatibleMessage

async def import_chat_history(file_path: str, user_id: str):
    """从文件导入聊天历史"""
    
    # 初始化
    memobase = LindormMemobase()
    
    # 读取聊天历史
    with open(file_path, 'r', encoding='utf-8') as f:
        chat_history = json.load(f)
    
    # 按日期分组对话
    daily_conversations = {}
    for message in chat_history:
        date = message['timestamp'][:10]  # 提取日期部分
        if date not in daily_conversations:
            daily_conversations[date] = []
        daily_conversations[date].append(message)
    
    # 批量处理每天的对话
    for date, messages in daily_conversations.items():
        print(f"处理 {date} 的对话 ({len(messages)} 条消息)")
        
        # 创建对话块
        blob = ChatBlob(
            messages=[
                OpenAICompatibleMessage(
                    role=msg['role'],
                    content=msg['content'],
                    created_at=msg['timestamp']
                )
                for msg in messages
            ]
        )
        
        # 提取记忆
        try:
            result = await memobase.extract_memories(
                user_id=user_id,
                blobs=[blob]
            )
            print(f"  ✓ 成功提取 {date} 的记忆")
        except Exception as e:
            print(f"  ✗ 处理 {date} 失败: {e}")
        
        # 避免过快调用
        await asyncio.sleep(1)
    
    # 生成用户档案报告
    profiles = await memobase.get_user_profiles(user_id)
    print(f"\n用户档案已更新，共 {len(profiles)} 个主题")
    
    return profiles

# 使用示例
async def main():
    # 准备测试数据
    test_history = [
        {
            "role": "user",
            "content": "我是张三，在北京工作",
            "timestamp": "2024-01-01T10:00:00"
        },
        {
            "role": "assistant",
            "content": "你好张三！",
            "timestamp": "2024-01-01T10:00:30"
        },
        {
            "role": "user",
            "content": "我喜欢编程和阅读",
            "timestamp": "2024-01-01T10:01:00"
        }
    ]
    
    # 保存到文件
    with open("chat_history.json", "w", encoding="utf-8") as f:
        json.dump(test_history, f, ensure_ascii=False, indent=2)
    
    # 导入历史
    profiles = await import_chat_history("chat_history.json", "user_zhang")
    
    # 显示结果
    for profile in profiles:
        print(f"\n主题: {profile.topic}")
        for subtopic, entry in profile.subtopics.items():
            print(f"  {subtopic}: {entry.content}")

if __name__ == "__main__":
    asyncio.run(main())
```
