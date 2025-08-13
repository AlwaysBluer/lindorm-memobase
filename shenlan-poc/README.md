# Shenlan POC - 对话数据记忆提取

这个POC项目使用 LindormMemobase 将Shenlan对话数据转换为结构化的长期记忆。

## 项目结构

```
shenlan-poc/
├── convert_stream_to_text.py   # 将流式响应转换为完整文本
├── processing.py               # 主要处理程序，将对话数据转为记忆
├── config.yaml                # 实际配置文件（需要创建）
├── config.yaml.example        # 配置模板文件
├── .gitignore                  # Git忽略文件
├── data/
│   ├── shenlandata.csv        # 原始流式数据
│   └── shenlandata_converted.csv  # 转换后的完整文本数据
└── README.md                   # 本文件
```

## 快速开始

### 1. 配置环境

复制配置模板并填入实际值：

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml` 文件，至少需要填入以下必需信息：

```yaml
# LLM API 配置（必需）
llm_api_key: sk-your-actual-openai-api-key-here

# Lindorm Table 配置（必需）
lindorm_table_host: your-lindorm-table-host
lindorm_table_username: your-username
lindorm_table_password: your-table-password

# Lindorm Search 配置（必需）
lindorm_search_host: your-lindorm-search-host
```

### 2. 转换数据格式

首先将原始的流式响应数据转换为完整文本：

```bash
python convert_stream_to_text.py
```

这会生成 `data/shenlandata_converted.csv` 文件。

### 3. 运行记忆提取

执行主处理程序：

```bash
python processing.py
```

程序将：
- 读取转换后的CSV数据
- 批量处理对话并提取记忆
- 为用户 `test_user_1` 生成档案和事件记录
- 显示处理结果和用户记忆摘要

## 配置说明

### 核心配置项

| 配置项 | 描述 | 是否必需 |
|--------|------|----------|
| `llm_api_key` | OpenAI API密钥 | ✅ 必需 |
| `lindorm_table_host` | Lindorm Table主机地址 | ✅ 必需 |
| `lindorm_table_password` | Lindorm Table密码 | ✅ 必需 |
| `lindorm_search_host` | Lindorm Search主机地址 | ✅ 必需 |
| `language` | 语言设置 (zh/en) | 可选，默认zh |
| `best_llm_model` | 主要LLM模型 | 可选，默认gpt-4o-mini |

### 性能调优配置

| 配置项 | 描述 | 默认值 |
|--------|------|---------|
| `max_chat_blob_buffer_token_size` | 缓冲区大小 | 8192 |
| `batch_size` | 批处理大小（代码中设置） | 3 |

## 数据处理流程

1. **数据读取**: 读取 CSV 文件中的对话记录
2. **数据解析**: 提取用户查询和助手响应
3. **批量处理**: 将对话组织成批次并添加到缓冲区
4. **记忆提取**: 当缓冲区满载时自动触发记忆提取
5. **结果存储**: 生成用户档案和事件记录存储到 Lindorm

## 输出结果

程序运行完成后会显示：

- 处理统计信息（总行数、成功率等）
- 用户档案主题列表
- 最近的事件记录

用户 `test_user_1` 的记忆数据将存储在 Lindorm 数据库中，可用于后续的对话上下文生成。

## 故障排除

### 1. 配置问题
- 检查 `config.yaml` 中的API密钥是否正确
- 验证 Lindorm 连接信息是否有效

### 2. 数据问题
- 确保 `data/shenlandata_converted.csv` 文件存在
- 检查CSV数据格式是否正确

### 3. 网络问题
- 确保能访问 OpenAI API
- 检查 Lindorm 服务是否可达

## 安全注意事项

- `config.yaml` 文件包含敏感信息，已添加到 `.gitignore`
- 不要将包含实际密钥的配置文件提交到版本控制
- 使用 `config.yaml.example` 作为模板分享给团队