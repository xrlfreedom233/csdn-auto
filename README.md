# CSDN AI 自动发文

程序每隔 6 小时调用一个 OpenAI 兼容接口生成 Java 方向的中文 Markdown 技术文章，
每次从代码枚举中随机抽取业务场景和技术组合形成动态提示词，然后调用
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
- `PROMPT_TECH_MIN`、`PROMPT_TECH_MAX`：每篇文章随机抽取的技术数量范围。
- `PROMPT_RECENT_WINDOW`：近期不重复使用的组合数量。
- `SCHEDULE_INTERVAL_HOURS`：每次成功发布后的间隔小时数，默认 `6`。

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

## 动态选题

业务场景和 Java 技术素材直接定义在 `csdn_auto/prompts.py` 的
`DEFAULT_SCENES` 与 `DEFAULT_TECHNOLOGIES` 中，需要扩充时直接编辑这两个元组。
每次生成会随机抽取场景和技术组合。

AI 成功生成文章后，所用组合会写入 `.state/prompt_history.json`，后续随机抽取
会避开最近 `PROMPT_RECENT_WINDOW` 个组合。该 JSON 仅保存防重复历史，不保存
场景和技术素材。

## 关于 CSDN 签名

抓包里的 `x-ca-nonce` 与 `x-ca-signature` 是一组签名值，可能过期或触发防重放，
不能保证长期定时使用。程序支持配置 `CSDN_X_CA_SECRET` 后按 API Gateway 的
HMAC-SHA256 规范动态生成；如果当前 CSDN 前端更换了签名规则，应以浏览器最新
请求为准更新 `make_signature()`。HTTP 200 也不代表业务成功，程序还会检查响应
JSON 中的 `code` 是否为 200。
