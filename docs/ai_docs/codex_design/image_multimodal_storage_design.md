# 图片多模态存储与检索设计（定稿）

## 1. 目标与边界

目标（交付优先）：
- 独立于现有记忆系统的图片检索链路与存储。
- 支持以文搜图 / 以图搜图，满足多租户（project_id）和用户过滤（user_id）。
- URL 优先存储（OSS），VARBINARY 作为兜底。
- 向量字段仅保留 1 个，使用图文多模态 embedding 模型。

非目标（本期不做）：
- 与记忆系统深度耦合或重构现有链路。
- 多向量字段（caption_embedding + image_embedding）。
- 人脸/人体特征抽取等复杂生物识别（可作为后续扩展）。

## 2. 核心设计决策

1) **单表方案（MVP）**
- 选择单表 `ImageStore`，把场景信息、用户关联与向量特征合并存储。
- 允许“同图多用户”场景，通过多行冗余实现（可接受）。

2) **URL 优先 + VARBINARY 兜底**
- 默认仅存 `image_url`（推荐 OSS）。
- 支持 `image_data`（VARBINARY）作为兜底场景。
- 由于 Lindorm 需要 byte[]，应用层负责 byte[] 转换与大小控制。

3) **单向量字段**
- 仅保留 `feature_vector`（多模态 embedding）。
- 以文搜图可用文本向量与该字段匹配；以图搜图用图片向量匹配。

## 3. 表结构设计

### 3.1 ImageStore 表

```sql
CREATE TABLE ImageStore (
    -- 主键字段
    project_id VARCHAR(255) NOT NULL,      -- 项目隔离标识
    user_id VARCHAR(255) NOT NULL,         -- 用户标识
    image_id VARCHAR(255) NOT NULL,        -- 图片唯一标识 (UUID)

    -- 场景信息（支持文本检索）
    caption TEXT,                          -- 场景描述（VL 模型生成，string）

    -- 图片存储（URL 优先，可选直接存储）
    image_url VARCHAR(2048),               -- 图片 URL（优先，如 OSS 链接）
    image_data VARBINARY,                  -- 原始图片 byte[]（可选，应用层控制大小）

    -- 向量特征（多模态 embedding）
    feature_vector VARCHAR,                -- 图片/文本向量，用于检索

    -- 元数据
    content_type VARCHAR(64),              -- MIME 类型
    file_size BIGINT,                      -- 文件大小（字节）
    metadata JSON,                         -- 扩展元数据（标签、来源等）

    -- 时间戳
    created_at TIMESTAMP,
    updated_at TIMESTAMP,

    PRIMARY KEY(project_id, user_id, image_id)
)
```

**约束与说明**：
- `image_url` 与 `image_data` 至少提供一个。
- `image_id` 在 (project_id, user_id) 维度内唯一即可。
- 允许同一图片被多个用户关联（多行冗余）。

### 3.2 搜索索引

```sql
CREATE INDEX img_store_srh_idx USING SEARCH ON ImageStore(
    project_id,
    user_id,
    image_id,
    created_at,
    updated_at,
    caption(mapping='{
        "type": "text",
        "analyzer": "ik_smart"
    }'),
    feature_vector(mapping='{
        "type": "knn_vector",
        "dimension": ${MULTIMODAL_EMBEDDING_DIM},
        "data_type": "float",
        "method": {
            "engine": "lvector",
            "name": "hnsw",
            "space_type": "cosinesimil",
            "parameters": {
                "m": 24,
                "ef_construction": 500
            }
        }
    }'),
    metadata
) PARTITION BY hash(project_id) WITH (
    SOURCE_SETTINGS='{
        "excludes": ["feature_vector", "image_data"]
    }',
    INDEX_SETTINGS='{
        "index": {
            "knn": true,
            "knn_routing": true,
            "knn.vector_empty_value_to_keep": true
        }
    }'
)
```

备注：若 `ik_smart` 不可用，改用默认分词或移除 analyzer。

## 4. SDK 入口与接口

新增入口类（与 LindormMemobase 并列）：
- `LindormImageStore`（独立链路，可共享 Config）

核心接口（MVP）：
- `add_image(project_id, user_id, image_url|image_data, caption?, auto_generate_caption, generate_embedding, metadata)`
- `get_image(project_id, user_id, image_id, include_data=False)`
- `update_image(project_id, user_id, image_id, caption?, metadata?, regenerate_embedding=False)`
- `delete_image(project_id, user_id, image_id)`
- `list_images(project_id, user_id, page, page_size, time_from?, time_to?)`
- `search_by_text(project_id, query, user_id?, top_k, min_score, search_mode)`
- `search_by_image(project_id, image_url|image_data, user_id?, top_k, min_score)`
- `reset(project_id, user_id?)`

检索模式：
- `caption`：仅全文检索
- `embedding`：仅向量检索
- `hybrid`：RRF 混合（建议二期默认关闭）

## 5. 多模态处理流程

### 5.1 入库
1) 校验输入（URL/bytes 至少一个、大小、MIME）。
2) 若 image_data：确保 byte[]（模型调用可用 base64，但入库保持 byte[]）。
3) 生成 caption（VLM），可选改写。
4) 生成多模态 embedding（图或文）。
5) 写入 ImageStore。

### 5.2 以文搜图
- 文本 → 多模态 embedding → feature_vector 检索
- 可选：caption 全文检索 + RRF 融合（默认关闭）

### 5.3 以图搜图
- 图片 → 多模态 embedding → feature_vector 检索

## 6. 配置（新增字段）

```python
# 图片存储配置
image_storage_type: Literal["url", "binary", "both"] = "url"
image_oss_endpoint: Optional[str] = None
image_oss_bucket: Optional[str] = None
image_oss_access_key: Optional[str] = None  # 建议从环境变量读取
image_oss_secret_key: Optional[str] = None  # 建议从环境变量读取

# 多模态模型配置
multimodal_embedding_provider: Literal["lindormai", "dashscope"] = "lindormai"
multimodal_embedding_model: str = "qwen2.5-vl-embedding"
multimodal_embedding_dim: int = 1024

vl_model_provider: Literal["lindormai", "dashscope"] = "lindormai"
vl_model: str = "qwen3-vl-plus"
caption_rewrite_model: str = "qwen-plus"

# 检索配置
image_search_default_top_k: int = 10
image_search_min_score: float = 0.5
image_enable_rerank: bool = False  # MVP 默认关闭
image_rerank_model: str = "qwen3-rerank"
```

## 7. 安全与性能

- **URL 安全**：建议使用签名 URL 或访问控制。
- **密钥管理**：OSS 访问密钥仅通过环境变量注入。
- **大小限制**：限制图片大小（例如 10MB 内）。
- **向量字段**：仅保留 `feature_vector`，降低索引成本。

## 8. 后续扩展（不影响 MVP）

- 双表规范化：`ImageScenes` + `ImageUserLink`（同图多用户去重）。
- 生物信息识别与特征提取（单独表）。
- OCR / 审核 / 视频帧检索。

