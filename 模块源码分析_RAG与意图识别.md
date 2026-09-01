# RAG 检索增强生成模块 & 意图识别模块 · 源码深度分析

> 分析时间：2026-08-27
> 分析文件：rag_service.py / intent_service.py / chat_service.py / llm_service.py / memory_service.py / deps.py

---

## 一、RAG（检索增强生成）模块

### 1.1 模块定位与职责

**文件路径：** `ai-customer-backend/app/services/rag_service.py`（638 行）

**核心职责：**
- 接收用户查询文本 → 返回 Top-K 相关知识片段
- 支持混合检索（向量 + 关键词 RRF 融合）
- 提供 Query 改写、Re-rank 等进阶能力
- 负责向量化、Milvus 检索、MySQL 关键词检索的降级处理

---

### 1.2 核心数据结构

```python
@dataclass
class RetrievalResult:
    """单条检索结果。"""
    chunk_id: str          # 知识分块唯一 ID（与 Milvus 对齐）
    doc_id: str            # 所属文档 ID
    content: str           # 分块文本内容
    score: float           # 综合相关性分数（归一化到 [0, 1]）
    category: str | None   # 知识分类标签（可选）
    source: str            # "vector" / "keyword" / "keyword_ft" / "fused" / "reranked"
```

**EmbeddingClient 内部状态：**
```python
class EmbeddingClient:
    _client: AsyncOpenAI | None      # OpenAI 兼容客户端
    _mock_until: float = 0.0         # mock 冷却截止时间戳
    _mock_cooldown: float = 30.0     # 冷却期 30s
```

---

### 1.3 主流程架构（10 步流水线）

```
retrieve(query, top_k=None)
│
├─ Step 0: Redis 缓存查询（TTL 5min，key 含 top_k/threshold/hybrid/rewrite/rerank 参数）
│           └─ 命中 → 直接返回，跳过全部计算
│
├─ Step 1: Query 改写（可选，temperature=0.3，max_tokens=200）
│           └─ 产出 1~3 个改写版本，去重保序
│
├─ Step 2: 向量化主查询（EmbeddingClient.embed，缓存 TTL 1h）
│           └─ API Key 无效/失败 → mock 伪随机向量（确定性，相同文本相同向量）
│
├─ Step 3: 向量检索（Milvus COSINE，top_k*2 预召回）
│           └─ Milvus 不可用 → 返回 []，降级纯关键词
│
├─ Step 4: 关键词检索（每条改写 query 分别跑，TOP_K*2 上限）
│           ├── 优先：MySQL FULLTEXT (BOOLEAN MODE + 前缀匹配)
│           └─ 降级：LIKE '%kw%'（SQLite/无索引环境）
│
├─ Step 5: RRF 融合（Reciprocal Rank Fusion，k=60，归一化到 [0, 1]）
│           └─ 纯向量 → 手动裁剪 cosine score 到 [0, 1]
│
├─ Step 6: 低分过滤（score < threshold 全部剔除）
│
├─ Step 7: 防御性兜底（全部被过滤 → 按原始排序取 top_k 回退）
│
├─ Step 8: 截断到 top_k
│
├─ Step 9: Re-rank（可选，temperature=0.0，解析 "3,1,4,2,5" 格式）
│           └─ 解析失败/LLM 不可用 → 保持原始顺序
│
└─ Step 10: 回填 Redis 缓存（TTL 5min，失败不阻塞）
```

---

### 1.4 降级策略矩阵

| 依赖 | 故障场景 | 降级方案 |
|------|---------|---------|
| Embedding API | Key 为占位符 / 调用失败 | Mock 伪随机向量（MD5 确定性种子）|
| Milvus | 服务不可用 / 连接失败 | 跳过向量检索，仅关键词检索 |
| MySQL FULLTEXT | SQLite / 无索引 | 降级 LIKE '%kw%' |
| Redis 缓存 | GET/SET 失败 | 静默忽略，不影响主流程 |
| Re-rank | LLM 不可用 / 解析失败 | 保持原始 RRF 融合顺序 |

**Mock 向量算法（`_mock_embed_single`）：**
```
1. MD5(text) → 16 字节种子
2. 拆分为 4 个 uint32
3. 对每个维度执行 xorshift32 伪随机
4. 叠加字符权重（text[i] / 65536）
5. L2 归一化 → 单位向量
```
相同文本 → 相同向量，保证 mock 环境下检索功能可用。

---

### 1.5 依赖关系

```
RAGService
├── db: AsyncSession（MySQL 关键词检索）
├── config_service: ConfigService（动态读取 top_k/threshold/开关）
└── llm_service: LLMService（Query 改写 + Re-rank）

全局单例：
├── milvus_client: MilvusClientWrapper（Milvus 连接）
└── embedding_client: EmbeddingClient（向量化，Redis 缓存）
```

---

### 1.6 关键代码片段

**RRF 融合核心算法：**
```python
scores: dict[str, float] = {}
for lst in result_lists:
    for rank, r in enumerate(lst, 1):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + 1.0 / (k + rank)
# k=60，rank 越小 → 分数越高；多条列表中的同一 chunk 分数叠加
# 归一化：min-max 映射到 [0, 1]
```

**缓存 Key 构造（避免配置变更后命中旧缓存）：**
```python
cache_key = (
    f"rag:retrieve:v1:{md5(query)}"
    f":{top_k}:{threshold:.3f}:{int(use_hybrid)}:{int(use_rewrite)}:{int(use_rerank)}"
)
```

---

## 二、意图识别模块

### 2.1 模块定位与职责

**文件路径：** `ai-customer-backend/app/services/intent_service.py`（274 行）

**核心职责：**
- 将用户消息分类为 `product_qa` / `off_topic` / `ambiguous`
- 双层判断：规则引擎（0ms）→ LLM Few-shot（精确判断）
- 置信度策略兜底（宁可多答不漏答）
- Prompt 注入防御

---

### 2.2 核心数据结构

```python
@dataclass
class IntentResult:
    intent: Literal["product_qa", "off_topic", "ambiguous"]
    confidence: float          # 0.0 ~ 1.0
    source: str               # "rule" / "llm" / "strategy" / "fallback"
```

**规则模式（预编译正则）：**
```python
QUICK_OFF_TOPIC_PATTERNS: list[re.Pattern]  # 无关问题：问候/闲聊/天气/股票等
QUICK_PRODUCT_PATTERNS: list[re.Pattern]    # 产品相关：出图/提示词/报错/付费/账号等
```

---

### 2.3 主流程架构（3 层判断）

```
classify(message, history)
│
├─ 边界处理：空消息 → ambiguous(0.0)
│
├─ 第一层：规则引擎（0ms，O(n) 正则扫描）
│   ├── off_topic 优先扫描（防误判）
│   │   └─ 命中 → product_qa? 否 → off_topic(conf=0.99, source="rule")
│   └── product 扫描
│       └─ 命中 → product_qa(conf=0.95, source="rule")
│
├─ 第二层：LLM Few-shot 判断（temperature=0.05）
│   ├── 构造 prompt（含 12 个 Few-shot 示例）
│   ├── 注入最近 2 轮对话上下文（防多轮歧义）
│   ├── 调用 LLMService.generate（非流式，max_tokens=80）
│   └── 解析 JSON：仅允许 {"intent", "confidence"} 两个 key
│
└─ 第三层：置信度策略
    ├── confidence ≥ 0.85 → 直取结果
    ├── 0.60 ≤ confidence < 0.85
    │   └── off_topic → 改判 product_qa（宁可多答不漏答）
    │   └── product_qa → 保留
    └── confidence < 0.60 → ambiguous（澄清引导）
```

---

### 2.4 Prompt 设计要点

**Few-shot 示例覆盖：**
- 产品类：风格/提示词/分辨率/报错/付费/账号/下载等
- 无关类：天气/闲聊
- 边界类："你们和 Midjourney 比怎么样"（product_qa, 0.92）、"这破产品太垃圾"（product_qa, 0.88）

**注入防御：**
```python
_INJECTION_DELIMITER = "---UNTRUSTED INPUT---"
# 用户消息包裹在分隔符内，防止 prompt injection
safe_message = f"{_INJECTION_DELIMITER}\n{message[:500]}\n{_INJECTION_DELIMITER}"
```

**JSON 容错解析：**
- 去除 markdown 代码块（```json ... ```）
- 正则提取第一个 `{...}` 块
- 白名单校验：仅允许 `intent` + `confidence` 两个 key

---

### 2.5 降级策略

| 场景 | 降级方案 |
|------|---------|
| LLM 不可用（service=None） | product_qa(conf=0.50, source="fallback") |
| LLM 调用失败 | product_qa(conf=0.50, source="fallback") |
| JSON 解析失败 | ambiguous(conf=0.0, source="llm") |
| 非预期 intent 值 | ambiguous(conf=0.0, source="llm") |

---

### 2.6 依赖关系

```
IntentService
└── llm_service: LLMService（第二层 LLM 判断）
    └── config_service: ConfigService（LLM 模型配置）

全局常量：
├── CONFIDENCE_HIGH: 0.85（高置信阈值）
├── CONFIDENCE_LOW: 0.60（低置信阈值）
└── INTENT_PROMPT_V2: Few-shot 提示模板
```

---

## 三、模块间调用链路

### 3.1 完整对话编排流程

```
FastAPI Router（/api/v1/chat/sessions/{id}/messages）
│
├── Depends(get_chat_service)
│   ├── Depends(get_intent_service)
│   │   └── Depends(get_llm_service)
│   │       └── Depends(get_config_service)
│   ├── Depends(get_rag_service)
│   │   ├── Depends(get_config_service)
│   │   └── Depends(get_llm_service)
│   ├── Depends(get_memory_service)
│   └── Depends(get_config_service)
│
└── ChatService.handle_message_stream()
    │
    ├── Step 1: intent_service.classify(message, history)
    │   └── 返回 IntentResult
    │
    ├── Step 2a: off_topic → config_service.get_fallback_message()
    │              → yield answer(兜底话术) + fallback + done
    │
    ├── Step 2b: ambiguous → config_service.get_fallback_message()
    │              → yield answer(澄清引导) + done
    │
    └── Step 2c: product_qa → 完整流程
        │
        ├── Step 3: rag_service.retrieve(message)
        │   ├── EmbeddingClient.embed(query) → Milvus 向量检索
        │   ├── RAGService._keyword_search(query) → MySQL LIKE/FULLTEXT
        │   ├── RAGService._rrf_fusion(vector_results, keyword_results)
        │   ├── 低分过滤 + 兜底回退
        │   └── (可选) RAGService._rerank(query, candidates)
        │
        ├── Step 4: memory_service.get_history(session_id)
        │   └── Redis lrange → 最近 20 条
        │
        ├── Step 5: 组装 Prompt（system + history + current_message）
        │
        ├── Step 6: yield source_event(retrieval_results[:5])
        │
        ├── Step 7: llm_service.generate(messages, system_prompt, stream=True)
        │   └── SSE answer(token) × N + done
        │
        └── finally: memory_service.save_message(user + assistant)
            ├── Redis rpush + ltrim + expire（24h）
            └── MySQL INSERT ChatMessage
```

---

### 3.2 依赖注入链（FastAPI Depends）

```
get_db（MySQL Session）
  │
  ├──→ get_config_service(db) → ConfigService
  │       │
  │       ├──→ get_llm_service(config_service) → LLMService
  │       │       │
  │       │       ├──→ get_intent_service(llm_service) → IntentService
  │       │       │
  │       │       └──→ get_rag_service(db, config_service, llm_service) → RAGService
  │       │
  │       └──→ get_memory_service(db) → MemoryService
  │
  └──→ get_chat_service(
          db,
          intent_service,     # 来自 get_intent_service
          rag_service,        # 来自 get_rag_service
          llm_service,        # 来自 get_llm_service
          memory_service,     # 来自 get_memory_service
          config_service,     # 来自 get_config_service
      ) → ChatService
```

---

### 3.3 SSE 事件流协议

```python
# sse.py - 事件构造
def make_answer_event(content: str) → SSEEvent(type="answer", content=...)
def make_source_event(sources: list[dict]) → SSEEvent(type="source", sources=...)
def make_fallback_event(data: dict) → SSEEvent(type="fallback", data=...)
def make_done_event(message_id) → SSEEvent(type="done", data={message_id})
def make_error_event(message: str) → SSEEvent(type="error", message=...)

# SSE 帧格式
# event: answer
# data: {"type":"answer","content":"你好"}
#
# （双换行结束）
```

**事件顺序（product_qa 分支）：**
```
source(["知识片段-xxx", ...])    ← 引用来源（最多 5 条）
answer("用户消息...")            ← LLM token 流式下发（多次）
done({"message_id": "xxx"})      ← 流结束
```

---

## 四、配置参数速查

### RAG 相关（settings.py）
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_DIM` | 1024 | 向量维度 |
| `EMBEDDING_MODEL` | text-embedding-v3 | 嵌入模型 |
| `MILVUS_COLLECTION` | knowledge_embeddings | Milvus 集合名 |
| `RAG_TOP_K` | 5 | 返回结果数 |
| `RAG_SCORE_THRESHOLD` | 0.60 | 最低分数阈值 |
| `RAG_CHUNK_SIZE` | 512 | 分块大小 |
| `RAG_CHUNK_OVERLAP` | 64 | 分块重叠 |
| `RAG_RERANK_ENABLED` | False | Re-rank 开关 |

### 意图识别相关（settings.py）
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INTENT_CONFIDENCE_HIGH` | 0.85 | 高置信阈值 |
| `INTENT_CONFIDENCE_LOW` | 0.60 | 低置信阈值 |

### 记忆服务相关（settings.py）
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SHORT_TERM_TTL` | 86400 | Redis TTL（秒） |
| `MAX_SHORT_TERM` | 20 | 滑动窗口大小 |

---

## 五、设计亮点总结

### RAG 模块
1. **多级降级**：Milvus → 关键词 LIKE → 纯兜底，确保任何时候都有结果
2. **RRF 融合**：向量检索 + 关键词检索融合，提升召回率
3. **Redis 缓存**：检索结果缓存 5min，避免重复计算
4. **确定性 Mock**：MD5 种子生成单位向量，相同文本相同向量，mock 环境下检索可用
5. **配置热更新**：top_k/threshold 等参数通过 ConfigService 动态读取，无需重启

### 意图识别模块
1. **零延迟规则层**：正则匹配 0ms，覆盖高频边界场景（问候/天气/无关词）
2. **Few-shot Prompt**：12 个示例覆盖产品问答的常见边界
3. **置信度策略**：宁可多答不漏答（中间区间 off_topic 改判 product_qa）
4. **Prompt 注入防御**：用户输入包裹在分隔符内，JSON 白名单校验
5. **上下文感知**：注入最近 2 轮对话，处理多轮短回复歧义

---

*分析完成于 2026-08-27*
