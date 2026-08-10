# CSDN AI 自动发文

程序每隔 12 小时调用一个 OpenAI 兼容接口生成 MCP（Model Context Protocol）方向的中文 Markdown 面试型技术文章。
每次从代码枚举中随机抽取 MCP 实践场景和技术组合，并先从本地知识库检索相关片段，然后调用
CSDN `saveArticle` 接口发布。每篇 Markdown 原文会保存在 `output/`，
最近一次发布结果保存在 `.state/last_publish.json`。

## 安装与配置

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

- `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`：你的 OpenAI 兼容 AI 服务。
- `AI_CONNECT_TIMEOUT`、`AI_TIMEOUT`：连接超时和内容生成等待时间（秒）。
- `CSDN_COOKIE`：浏览器开发者工具中发布请求的完整 Cookie。
- `CSDN_X_CA_SECRET`：用于动态签名的密钥；推荐使用。
- `CSDN_X_CA_NONCE`、`CSDN_X_CA_SIGNATURE`：仅供临时联调的抓包值。
- `CSDN_TAGS`：动态技术标签不可用时使用的兜底标签。
- `PROMPT_TECH_MIN`、`PROMPT_TECH_MAX`：每篇文章随机抽取的技术数量范围。
- `PROMPT_RECENT_WINDOW`：近期不重复使用的组合数量。
- `RAG_ENABLED`：是否开启 RAG，默认开启。
- `RAG_BACKEND`：默认 `chroma` 向量检索；可改为 `lexical` 使用无 embedding 的关键词检索。
- `RAG_KNOWLEDGE_DIR`：知识文档目录，默认 `knowledge`。
- `RAG_VECTOR_PATH`：Chroma 向量数据库的持久化目录，默认 `.state/chroma`。
- `RAG_TOP_K`：每次最多注入的检索片段数，默认 `4`。
- `RAG_MIN_SCORE`：向量结果的最低相似度，默认 `0.2`。
- `RAG_CHUNK_SIZE`、`RAG_CHUNK_OVERLAP`：文档切块字符数和重叠字符数。
- `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`：独立的向量模型服务。当配置了独立 URL 时必须同时配置对应 Key，不会复用聊天服务 Key。
- `EMBEDDING_DIMENSIONS`：输出向量维度，当前 Qwen3-Embedding-4B 使用 `1024`。
- `EMBEDDING_FAILOVER_ENABLED`：是否向模力方舟发送 `X-Failover-Enabled: true`。
- `EMBEDDING_QUERY_INSTRUCTION`：查询向量的检索任务指令；文档向量默认不带指令。
- `SCHEDULE_INTERVAL_HOURS`：每次成功发布后的间隔小时数，默认 `12`，每天最多发布 2 篇。

`.env` 已被 `.gitignore` 忽略，不要把 Cookie、Token 或 API Key 提交到仓库。

## 运行

先只生成 Markdown，确认 AI 配置和内容：

```bash
python -m csdn_auto publish --dry-run
```

确认后立即发布：

```bash
python -m csdn_auto publish
```

启动常驻定时任务：

```bash
python -m csdn_auto schedule
```

生产环境可使用 systemd、Docker 或进程守护工具保证上述命令持续运行。

## MCP 动态选题

实践场景和 MCP 技术素材直接定义在 `csdn_auto/prompts.py` 的
`DEFAULT_SCENES` 与 `DEFAULT_TECHNOLOGIES` 中，需要扩充时直接编辑这两个元组。
每次生成会随机抽取场景和技术组合。
发布时会将本篇抽中的技术组合自动设置为 CSDN 标签，不再固定使用 `java`。
文章默认使用“面试官追问—候选人回答—面试官点评”结构，标题可使用
“大厂 MCP 面试实录”风格，但正文会明确说明是模拟面试或面试题复盘，
不伪造具体公司、真实面试官和录用结果。

AI 成功生成文章后，所用组合会写入 `.state/prompt_history.json`，后续随机抽取
会避开最近 `PROMPT_RECENT_WINDOW` 个组合。该 JSON 仅保存防重复历史，不保存
场景和技术素材。

## 持久化向量 RAG 知识库

`knowledge/` 保存原始文档，`.state/chroma/` 保存持久化向量索引。项目已放入一份 MCP 基础资料，
可继续添加 `.md`、`.markdown`、`.mdx` 或 `.txt` 文件。每次生成前程序都会比对文档指纹：
仅对新增或变更的切块请求 embedding，并自动删除已不存在的旧向量。随后通过余弦距离召回 Top-K 片段。
命中片段的文件名会记录在日志中，
模型被要求在正文中以 `[资料1]` 引用它们。

知识目录不存在、文件为空或没有匹配片段时，会自动降级为不带检索上下文的生成。
当前默认使用模力方舟 `Qwen3-Embedding-4B` 的 OpenAI 兼容 `/embeddings` 接口，
输出 1024 维向量。服务器 `.env` 必须填入重新生成且未泄露的 `EMBEDDING_API_KEY`。
若当前向量服务不提供 `/embeddings`，需单独配置另一个 OpenAI 兼容的 embedding 服务，
或临时设置 `RAG_BACKEND=lexical` 使用原有关键词检索。

## 知识文档导入与清洗

统一导入网页、PDF、Word、HTML、Markdown 或 TXT：

```bash
python -m csdn_auto import-knowledge \
  "https://modelcontextprotocol.io/docs/learn/architecture" \
  ./资料/mcp-spec.pdf \
  ./资料/内部实践.docx
```

也可导入整个目录，程序会递归处理支持的文件：

```bash
python -m csdn_auto import-knowledge ./待导入资料
```

清洗结果默认写入 `knowledge/imported/`，文件名带内容指纹，文档头部保留
原始 URL 或文件路径以便追溯。该命令不需要 AI 和 CSDN 配置。下次发文时
Chroma 会自动发现新 Markdown 并增量向量化。

清洗规则：

- 网页：优先提取 `article` 或 `main`，移除脚本、样式、导航、页脚、广告、评论和推荐区，转换为 Markdown。
- PDF：提取每页文字，删除重复页眉/页脚，尝试修复中英文断行。
- Word `.docx`：保留标题层级、段落、列表和表格。旧版 `.doc` 需先转换为 `.docx`。
- Markdown/TXT：清理控制字符、行尾空格和过多空行。
- 默认拒绝超过 25 MB 的单文档，可使用 `--max-mb` 调整。
- 纯图片扫描版 PDF 无法直接提取文字，命令会明确提示先做 OCR。

指定其他输出目录或网络超时：

```bash
python -m csdn_auto import-knowledge URL_OR_FILE \
  --output-dir knowledge/imported \
  --timeout 60 \
  --max-mb 50
```

## 关于 CSDN 签名

抓包里的 `x-ca-nonce` 与 `x-ca-signature` 是一组签名值，可能过期或触发防重放，
不能保证长期定时使用。程序支持配置 `CSDN_X_CA_SECRET` 后按 API Gateway 的
HMAC-SHA256 规范动态生成；如果当前 CSDN 前端更换了签名规则，应以浏览器最新
请求为准更新 `make_signature()`。HTTP 200 也不代表业务成功，程序还会检查响应
JSON 中的 `code` 是否为 200。
