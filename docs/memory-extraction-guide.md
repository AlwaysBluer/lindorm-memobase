# LindormMemobase 记忆抽取系统详细指南

本文档深入介绍 LindormMemobase 库的核心功能，包括记忆抽取流程、核心方法的输入输出，以及主要API接口的用法说明。

## 1. 主要记忆抽取流程

LindormMemobase 采用多阶段记忆抽取流程，将对话数据转换为结构化的用户画像和事件记录。

### 1.1 整体流程概览

记忆抽取系统遵循以下核心流程：

**第一阶段：数据预处理**
- **输入验证**：验证输入的 Blob 数据格式和完整性
- **内容截断**：根据配置的最大token限制，对输入内容进行智能截断
- **对话摘要**：生成对话的结构化摘要，便于后续分析

**第二阶段：并行处理**
- **用户画像抽取**：并行执行用户画像相关信息的抽取
- **事件标签生成**：并行生成事件标签和分类信息

**第三阶段：数据整合与存储**
- **画像合并**：将新抽取的信息与现有用户画像合并
- **冲突解决**：处理信息冲突和重复内容
- **结构化存储**：将处理后的数据存储到Lindorm数据库

### 1.2 详细处理步骤

#### 步骤1：数据截断与预处理

```python
# 核心函数：truncate_chat_blobs
def truncate_chat_blobs(blobs: list[Blob], max_token_size: int) -> list[Blob]:
    """
    智能截断对话数据，确保在token限制内处理最相关的内容
    - 从最新对话开始，向前累计token数量
    - 当达到限制时停止，确保上下文连贯性
    """
```

**处理逻辑**：
- 倒序遍历Blob列表（优先保留最新对话）
- 计算每个Blob的token消耗
- 累计token数不超过配置限制
- 返回截断后的有效Blob列表

#### 步骤2：对话条目摘要

**功能模块**：`entry_chat_summary`

**处理内容**：
- 分析对话中的关键信息点
- 识别用户表达的偏好、观点和行为
- 生成结构化的记忆条目摘要
- 为后续的画像抽取和事件标记提供基础数据

#### 步骤3：并行处理 - 用户画像抽取

**核心处理流程**：

1. **主题抽取** (`extract_topics`)
   - 识别对话中涉及的主要主题
   - 提取用户在各主题下的具体观点和偏好
   - 生成结构化的事实内容和属性信息

2. **信息合并** (`merge_or_valid_new_memos`)
   - 与现有用户画像进行对比
   - 识别新增、更新、删除的信息
   - 处理信息冲突和一致性验证

3. **画像组织** (`organize_profiles`)
   - 检查画像结构的合理性
   - 重新组织主题和子主题分类
   - 确保画像信息的逻辑性

4. **内容摘要** (`re_summary`)
   - 对过长的画像条目进行摘要压缩
   - 保持关键信息完整性
   - 优化存储效率

#### 步骤4：并行处理 - 事件标签生成

**核心处理流程**：

1. **事件标记** (`tag_event`)
   - 分析对话的事件性质
   - 生成时间、地点、活动类型等标签
   - 为事件检索和相关性分析提供索引

#### 步骤5：数据持久化

**存储操作**：
- **会话事件存储** (`handle_session_event`)
  - 将处理后的事件信息存储到事件表
  - 建立时间序列索引和向量索引

- **用户画像存储** (`handle_user_profile_db`)
  - 更新用户画像数据库
  - 维护主题-子主题的层次结构

### 1.3 流程控制与错误处理

**Promise模式**：
- 整个流程使用Promise模式进行异步控制
- 每个处理步骤都返回Promise对象，包含操作结果和错误信息
- 支持链式调用和并行处理

**错误传播**：
- 任何步骤失败都会中断整个流程
- 详细的错误信息会传播到最终调用者
- 支持部分失败的优雅降级处理

## 2. 核心记忆抽取方法的输入输出

### 2.1 主入口方法：`process_blobs`

#### 输入参数

```python
async def process_blobs(
    user_id: str,              # 用户唯一标识符
    profile_config: ProfileConfig,  # 画像配置参数
    blobs: list[Blob],         # 待处理的数据块列表
    config: Config             # 全局系统配置
) -> Promise[ChatModalResponse]
```

**参数详解**：

- **user_id**: 用户的唯一标识符，用于关联所有记忆数据
- **profile_config**: 画像配置对象，包含：
  - `language`: 处理语言（"zh"/"en"）
  - `max_topics`: 最大主题数量限制
  - `max_subtopics_per_topic`: 每个主题下最大子主题数
  - `topic_preference`: 主题偏好设置

- **blobs**: 数据块列表，支持的类型：
  - `ChatBlob`: 对话数据，包含消息列表
  - `DocBlob`: 文档内容
  - `CodeBlob`: 代码片段
  - `ImageBlob`: 图片数据
  - `TranscriptBlob`: 转录文本

- **config**: 全局配置，包含数据库连接、LLM设置等

#### 输出结果

```python
class ChatModalResponse:
    event_id: str                    # 生成的事件ID
    add_profiles: list[str]          # 新增的画像ID列表
    update_profiles: list[str]       # 更新的画像ID列表  
    delete_profiles: list[str]       # 删除的画像ID列表
```

### 2.2 用户画像处理：`process_profile_res`

#### 输入参数

```python
async def process_profile_res(
    user_id: str,                    # 用户标识符
    user_memo_str: str,              # 用户记忆摘要文本
    project_profiles: ProfileConfig, # 画像配置
    config: Config,                  # 系统配置
) -> Promise[tuple[MergeAddResult, list[dict]]]
```

#### 输出结果

```python
# 第一个元素：MergeAddResult
class MergeAddResult(TypedDict):
    add: list[AddProfile]            # 新增的画像条目
    update: list[UpdateProfile]      # 更新的画像条目
    delete: list[str]               # 删除的画像ID
    update_delta: list[AddProfile]   # 更新增量数据
    before_profiles: list[ProfileData] # 处理前的画像状态

# 第二个元素：delta_profile_data
# 包含新增和更新增量的合并数据，用于事件关联
```

### 2.3 事件处理：`process_event_res`

#### 输入参数

```python
async def process_event_res(
    usr_id: str,                     # 用户ID
    memo_str: str,                   # 记忆摘要
    profile_config: ProfileConfig,   # 配置
    config: Config,                  # 系统配置
) -> Promise[list | None]
```

#### 输出结果

```python
# 返回事件标签列表
list[dict] = [
    {
        "tag": "event_type",         # 事件类型标签
        "confidence": 0.8,           # 置信度
        "attributes": {              # 事件属性
            "time": "2025-08-08",
            "location": "home",
            "activity": "cooking"
        }
    },
    # ... 更多标签
]
```

## 3. 核心检索方法和输入输出

### 3.1 用户画像检索：`get_user_profiles_data`

#### 输入参数

```python
async def get_user_profiles_data(
    user_id: str,                           # 用户ID
    max_profile_token_size: int,            # 最大返回token数
    prefer_topics: Optional[List[str]],     # 偏好主题列表
    only_topics: Optional[List[str]],       # 仅包含的主题
    max_subtopic_size: Optional[int],       # 子主题大小限制
    topic_limits: Dict[str, int],           # 各主题token限制
    chats: List[OpenAICompatibleMessage],   # 当前对话用于相关性分析
    full_profile_and_only_search_event: bool, # 完整画像模式
    global_config: Config                   # 系统配置
) -> Promise[tuple[str, list[ProfileData]]]
```

#### 输出结果

```python
# 返回元组：(profile_section, raw_profiles)
tuple[str, list[ProfileData]] = (
    # profile_section: 格式化的画像文本，可直接用于对话上下文
    """## 用户画像
    
    ### 兴趣爱好
    - 音乐偏好：喜欢爵士乐和古典音乐
    - 运动习惯：每周跑步3次，喜欢户外活动
    
    ### 饮食习惯  
    - 偏好素食，避免高糖食物
    - 喜欢烹饪，经常尝试新菜谱
    """,
    
    # raw_profiles: 原始画像数据列表
    [
        ProfileData(
            profile_id="uuid-1",
            content="喜欢爵士乐和古典音乐，经常在周末听音乐放松",
            attributes={
                "topic": "兴趣爱好",
                "sub_topic": "音乐偏好"
            },
            created_at=datetime.now(),
            updated_at=datetime.now()
        ),
        # ... 更多画像数据
    ]
)
```

### 3.2 事件搜索：`search_user_event_gists`

#### 输入参数

```python
async def search_user_event_gists(
    user_id: str,                    # 用户ID
    query: str,                      # 搜索查询文本
    config: Config,                  # 系统配置
    topk: int = 10,                  # 返回结果数量
    similarity_threshold: float = 0.2, # 相似度阈值
    time_range_in_days: int = 21     # 搜索时间范围（天）
) -> Promise[UserEventGistsData]
```

#### 输出结果

```python
class UserEventGistsData:
    gists: list[EventGist]           # 事件摘要列表

class EventGist:
    id: str                          # 事件ID  
    gist_data: dict                  # 事件内容数据
    created_at: datetime             # 创建时间
    updated_at: datetime             # 更新时间
    similarity: float                # 与查询的相似度分数

# 实际返回示例
UserEventGistsData(
    gists=[
        EventGist(
            id="event-001",
            gist_data={
                "content": "用户询问了如何制作意大利面的方法",
                "tags": ["cooking", "pasta", "italian"],
                "summary": "烹饪咨询 - 意大利面制作"
            },
            created_at=datetime(2025, 8, 7, 14, 30),
            updated_at=datetime(2025, 8, 7, 14, 30),
            similarity=0.85
        ),
        # ... 更多事件
    ]
)
```

### 3.3 上下文生成：`get_user_context`

#### 输入参数

```python
async def get_user_context(
    user_id: str,                           # 用户ID
    profile_config: ProfileConfig,          # 画像配置
    global_config: Config,                  # 系统配置
    max_token_size: int = 2000,            # 最大上下文token数
    prefer_topics: Optional[List[str]] = None, # 偏好主题
    only_topics: Optional[List[str]] = None,   # 限制主题
    max_subtopic_size: Optional[int] = None,   # 子主题大小限制
    topic_limits: Dict[str, int] = {},         # 主题token限制
    chats: List[OpenAICompatibleMessage] = [], # 当前对话
    time_range_in_days: int = 30,             # 事件搜索范围
    event_similarity_threshold: float = 0.2,   # 事件相似度阈值
    profile_event_ratio: float = 0.6,         # 画像与事件的比例
    require_event_summary: bool = False,       # 是否需要事件摘要
    customize_context_prompt: Optional[str] = None, # 自定义上下文提示
    full_profile_and_only_search_event: bool = False, # 完整画像模式
    fill_window_with_events: bool = False     # 用事件填充剩余token
) -> Promise[UserContextData]
```

#### 输出结果

```python
class UserContextData:
    context: str                     # 生成的上下文文本
    profile_section: str             # 画像部分
    event_section: str               # 事件部分
    token_usage: dict                # token使用统计

# 实际返回示例
UserContextData(
    context="""## 用户上下文信息

### 用户画像
**兴趣爱好**
- 音乐：喜欢爵士乐，周末经常听音乐放松
- 烹饪：热爱烹饪，经常尝试新菜谱

**生活习惯**  
- 健身：每周跑步3次，注重健康生活方式
- 饮食：偏好素食，避免高糖食物

### 相关历史记录
- [2025-08-07] 询问了健康烹饪方法
- [2025-08-05] 分享了周末的跑步计划
- [2025-08-03] 讨论了爵士音乐推荐
""",
    
    profile_section="### 用户画像\n**兴趣爱好**\n- 音乐：喜欢爵士乐...",
    event_section="### 相关历史记录\n- [2025-08-07] 询问了健康烹饪方法...",
    token_usage={
        "total": 1850,
        "profile": 1100,
        "events": 750
    }
)
```

## 4. LindormMemoBase透出接口的功能和用法说明

### 4.1 核心接口类：`LindormMemobase`

LindormMemobase 是整个系统的主要入口点，提供了完整的记忆管理功能。

#### 4.1.1 初始化方法

```python
# 方法1：使用默认配置
memobase = LindormMemobase()

# 方法2：从YAML文件加载配置  
memobase = LindormMemobase.from_yaml_file("config.yaml")

# 方法3：通过参数创建配置
memobase = LindormMemobase.from_config(
    language="zh",
    llm_api_key="your-api-key",
    best_llm_model="gpt-4"
)

# 方法4：使用Config对象
config = Config.load_config()
memobase = LindormMemobase(config)
```

### 4.2 记忆抽取接口

#### 4.2.1 `extract_memories` - 抽取用户记忆

**功能**：从对话数据中抽取并更新用户画像和事件记录

**用法示例**：

```python
from lindormmemobase.models.blob import ChatBlob, OpenAICompatibleMessage
from datetime import datetime

# 创建对话数据
messages = [
    OpenAICompatibleMessage(role="user", content="我最喜欢在周末弹吉他，特别是爵士乐"),
    OpenAICompatibleMessage(role="assistant", content="太棒了！爵士乐很有魅力")
]

conversation_blob = ChatBlob(
    messages=messages,
    fields={"user_id": "user123", "session_id": "chat_001"},
    created_at=datetime.now()
)

# 执行记忆抽取
result = await memobase.extract_memories(
    user_id="user123",
    blobs=[conversation_blob]
)

print(f"事件ID: {result.event_id}")
print(f"新增画像: {len(result.add_profiles)} 个")
print(f"更新画像: {len(result.update_profiles)} 个")
```

**返回值说明**：
- `event_id`: 新创建的事件唯一标识符
- `add_profiles`: 新增的用户画像条目ID列表
- `update_profiles`: 更新的现有画像条目ID列表
- `delete_profiles`: 删除的画像条目ID列表

### 4.3 用户画像查询接口

#### 4.3.1 `get_user_profiles` - 获取用户画像

**功能**：检索用户的完整画像信息，支持主题过滤

**用法示例**：

```python
# 获取所有画像
profiles = await memobase.get_user_profiles("user123")

# 获取特定主题的画像
profiles = await memobase.get_user_profiles(
    "user123", 
    topics=["兴趣爱好", "饮食习惯"]
)

# 遍历画像信息
for profile in profiles:
    print(f"主题: {profile.topic}")
    for subtopic, entry in profile.subtopics.items():
        print(f"  {subtopic}: {entry.content}")
```

#### 4.3.2 `get_relevant_profiles` - 获取相关画像

**功能**：基于当前对话内容，智能筛选最相关的用户画像

**用法示例**：

```python
conversation = [
    OpenAICompatibleMessage(role="user", content="我想计划一次旅行")
]

relevant_profiles = await memobase.get_relevant_profiles(
    user_id="user123",
    conversation=conversation,
    topics=["旅行", "兴趣爱好"],
    max_profiles=5
)

for profile in relevant_profiles:
    print(f"相关主题: {profile.topic}")
```

#### 4.3.3 `search_profiles` - 搜索画像

**功能**：通过文本查询搜索相关的用户画像信息

**用法示例**：

```python
profiles = await memobase.search_profiles(
    user_id="user123",
    query="喜欢的餐厅",
    topics=["饮食", "生活"],
    max_results=5
)
```

### 4.4 事件查询接口

#### 4.4.1 `get_events` - 获取历史事件

**功能**：检索用户的历史事件记录

**用法示例**：

```python
events = await memobase.get_events(
    user_id="user123",
    time_range_in_days=30,  # 最近30天
    limit=50                # 最多50条记录
)

for event in events:
    print(f"[{event['created_at']}] {event['content']}")
```

#### 4.4.2 `search_events` - 搜索事件

**功能**：通过向量相似度搜索相关的历史事件

**用法示例**：

```python
events = await memobase.search_events(
    user_id="user123",
    query="烹饪计划",
    limit=10,
    similarity_threshold=0.3,
    time_range_in_days=21
)

for event in events:
    print(f"相似度: {event['similarity']:.2f}")
    print(f"内容: {event['content']}")
    print("---")
```

### 4.5 上下文生成接口

#### 4.5.1 `get_conversation_context` - 生成对话上下文

**功能**：为当前对话生成包含相关画像和历史事件的智能上下文

**用法示例**：

```python
conversation = [
    OpenAICompatibleMessage(role="user", content="今晚我应该做什么菜？")
]

context = await memobase.get_conversation_context(
    user_id="user123",
    conversation=conversation,
    max_token_size=2000,
    prefer_topics=["烹饪", "饮食习惯"],
    profile_event_ratio=0.7  # 70%画像，30%事件
)

print("生成的上下文:")
print(context)
```

**高级参数说明**：

- `profile_event_ratio`: 控制画像和事件内容的比例
- `time_range_in_days`: 事件搜索的时间窗口
- `event_similarity_threshold`: 事件相关性的最小阈值
- `topic_limits`: 为不同主题设置token限制
- `fill_window_with_events`: 用事件填充剩余的token预算

### 4.6 配置管理

#### 4.6.1 ProfileConfig - 画像配置

```python
from lindormmemobase.models.profile_topic import ProfileConfig

profile_config = ProfileConfig(
    language="zh",                    # 处理语言
    max_topics=20,                   # 最大主题数
    max_subtopics_per_topic=10,      # 每主题最大子主题数
    topic_preference=[               # 主题偏好权重
        "兴趣爱好",
        "工作学习", 
        "生活习惯"
    ]
)
```

#### 4.6.2 Config - 系统配置

```python
from lindormmemobase import Config

config = Config.load_config()
print(f"LLM模型: {config.best_llm_model}")
print(f"语言设置: {config.language}")
print(f"最大处理token: {config.max_chat_blob_buffer_process_token_size}")
```

### 4.7 异常处理

```python
from lindormmemobase import LindormMemobaseError, ConfigurationError

try:
    result = await memobase.extract_memories(user_id, blobs)
except ConfigurationError as e:
    print(f"配置错误: {e}")
except LindormMemobaseError as e:
    print(f"处理错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")
```

### 4.8 最佳实践建议

1. **批量处理**：建议将相关的对话合并成一个ChatBlob进行处理，提高效率

2. **配置优化**：根据实际需求调整token限制和主题数量，平衡性能和效果

3. **错误处理**：always包装异步调用，适当处理网络和数据库异常

4. **资源管理**：对于长时间运行的应用，考虑连接池和缓存策略

5. **隐私保护**：确保用户ID的唯一性和隐私性，避免数据泄露风险

---

## 总结

LindormMemobase 提供了完整的记忆管理解决方案，从对话数据到结构化用户画像，再到智能上下文生成。通过理解其核心流程和接口设计，开发者可以构建出智能化的个性化AI应用。

系统的异步设计保证了高性能，而灵活的配置机制则支持各种定制化需求。无论是简单的记忆抽取还是复杂的上下文分析，LindormMemobase 都能提供稳定可靠的服务。