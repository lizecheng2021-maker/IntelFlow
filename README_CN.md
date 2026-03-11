<p align="center">
  <h1 align="center">⚡ IntelFlow</h1>
  <p align="center"><strong>你的专属 AI 情报 Agent — 每天自动读懂世界，用你的语气写出来，帮你发出去。</strong></p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python 3.11+">
  <a href="https://github.com/lizecheng2021-maker/IntelFlow/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://www.lizecheng.net"><img src="https://img.shields.io/badge/%E5%AE%9E%E9%99%85%E4%BA%A7%E5%87%BA-lizecheng.net-orange.svg" alt="Live Demo"></a>
</p>

**[English](README.md)** | 中文

---

> **AI 每周都在爆炸式更新。加密市场永不休市。社媒信息流 80% 是噪音。**
> 你需要的不是更多信息——是能帮你过滤、分析、输出判断的系统。
>
> IntelFlow 每天早上自动运行：AI Agent 围绕**你定义的主题**搜索全网，用**你的语气**写出双语深度日报，同步发布到微信公众号、飞书、WordPress——你喝完咖啡，内容已经发出去了。
>
> 一个 API Key。自然语言配置。不需要维护爬虫。不需要订阅费。

![IntelFlow Demo](assets/demo/demo.gif)

全球唯一同时满足：

- **中英双语原生生成** — 不是翻译，两套独立编辑人格同步输出
- **微信公众号 + 飞书 + WordPress 三端一键发布** — 没有任何其他开源项目做到这三个
- **完全自定义分析维度** — AI/金融/加密/生物科技/SEO，你说了算
- **支持所有主流大模型** — Claude、GPT-4、Gemini、通义千问、智谱 GLM，或本地 Ollama
- **完全自部署，生产级可靠性，无供应商绑定，无按篇收费**

---

## 为什么是 IntelFlow？

| | Morning Brew / The Rundown | Feedly / Curated | hn-digest / newsletter-gpt | **IntelFlow** |
|---|---|---|---|---|
| 双语原生输出 | 无 — 仅英文 | 无 — 仅英文 | 无 — 仅英文 | **有 — 中英同步** |
| 微信 + 飞书 + WordPress | 无 | 无 | 无 | **有 — 一条命令** |
| 自定义分析维度 | 无 — 固定选题 | 无 — 手动整理 | 无 — 话题写死 | **有 — 完全可配** |
| 真实编辑人格 | 需要大型团队 | 不适用 | 通用 AI 腔调 | **配置文件搞定，不需要团队** |
| 自部署 + 生产级 | 无 | 无 | 业余项目，JSON 存储脆弱 | **有 — 内置故障转移** |
| 成本 | 订阅费 | 订阅费 | 免费但能力有限 | **Gemini / Ollama 可免费跑 · 其他按所选模型 API 实际调用计费** |

Morning Brew 这类商业产品需要大型编辑团队才能维持稳定的编辑风格。现有开源替代品是业余项目，没有发布流水线，存储方式也不可靠。IntelFlow 是唯一一个同时做到生产级稳定性和真实编辑人格的自部署系统——通过配置文件驱动，不需要团队。

---

## 实际产出

看看 IntelFlow 在生产环境跑出来的效果：

- **英文日报：** [www.lizecheng.net](https://www.lizecheng.net)
- **中文日报（飞书）：** [飞书文档](https://xv7exvpv861.feishu.cn/wiki/Sh8OwOyqningOvkE8MAcYSOwn8e)

你的产出会完全不同——取决于你定义的维度、你选的模型和你配置的编辑风格。

---

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/lizecheng2021-maker/IntelFlow.git
cd IntelFlow

# 2. 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 打开 Web 面板，粘贴一个 API Key，设定关注领域，完成
python web/app.py
# 浏览器打开 http://localhost:5050
```

这就是全部设置。运行第一次日报：

```bash
bash scripts/run_daily.sh
```

一个 API Key 就能启动。其他——发布目标、额外数据源、编辑人格——都是可选配置。

---

## 你能拿到什么

一次完整的日报流程输出：

```
output/2026-03-11/
├── daily_zh.md          # 中文日报（约 4000-5000 字）
├── daily_en.md          # 英文日报（约 4000-5000 字，独立编辑视角）
├── cover_zh.png         # AI 生成封面图
├── cover_en.png         # AI 生成封面图
└── briefing.json        # 结构化原始数据
```

**日报结构**（根据你配置的维度自动调整）：

```
30 秒速览
─────────────────
[你的维度 1]   例如：AI 动态 — 3-5 条，每条有独立判断
[你的维度 2]   例如：加密货币 — 信号，不是摘要
[你的维度 3]   例如：SaaS — 竞品动作、融资信号
...
今日精华        跨维度串联洞察，400-600 字
```

每条不是标题搬运，AI 跨维度交叉验证信号，识别结构性变化后给出判断。

**输出节奏：**

| 格式 | 篇幅 | 周期 |
|------|------|------|
| 日报 | 4000-5000 字 | 每天 |
| 周报 | 8000-10000 字 | 聚合分析 |
| 月报 | 12000-15000 字 | 趋势综合 |

---

## 配置你的领域

IntelFlow 的核心概念是**维度**——AI 用来组织研究方向的独立分析轨道。在 Web 面板一次性定义好。

**加密货币交易员：**
- 市场信号 30% | 链上数据 25% | 监管动态 20% | DeFi 协议 15% | 宏观 10%

**SaaS 创始人：**
- 竞品情报 25% | 用户痛点 25% | 技术栈 20% | 融资动向 15% | 增长策略 15%

**学术研究者：**
- 论文发布 30% | 基金资助 20% | 会议动态 20% | 产业应用 15% | 政策影响 15%

**游戏开发者：**
- 行业动态 30% | 技术发布 25% | 社区舆情 20% | 竞品动向 15% | 平台政策 10%

除了维度，你还可以配置：

- **编辑人格** — 语气、风格、口头禅、分析深度
- **语言输出** — 仅中文、仅英文，或双语同步
- **发布目标** — 微信公众号、飞书、WordPress，或只看本地 Markdown
- **AI 模型** — 在 Claude、GPT-4、Gemini、通义、智谱或本地 Ollama 之间随时切换，无需改代码

---

## 系统架构

```
                     IntelFlow AI-First 流水线

  用户描述兴趣（自然语言）
         │
         ▼
  Quick Setup 对话
  "AI 工具、加密货币、独立开发…"
         │  AI 分析 → 推荐维度 + 信息源
         ▼
  focus.json（维度配置 + 权重）
         │
         ▼
  ┌──────────────────────────────────────────┐
  │            AI Agent 并行执行              │
  │                                          │
  │  维度 1 ──► web_search ──► 中文 + 英文   │
  │  维度 2 ──► web_search ──► 中文 + 英文   │
  │  维度 3 ──► web_search ──► 中文 + 英文   │
  │  维度 N ──► web_search ──► 中文 + 英文   │
  │                                          │
  │  LLM 自主决定：搜什么 / 搜几次 / 怎么分析  │
  └──────────────────────────────────────────┘
         │
         ▼
  assemble（速览 + 精华 + 拼装完整日报）
         │
         ▼
  ┌─────────────────┐
  │      发布        │
  │  微信公众号       │
  │  飞书文档         │
  │  WordPress       │
  └─────────────────┘

  可选插件（plugins/collect_*.py 自动发现）：
  RSS / Hacker News / GitHub Trending / Reddit / YouTube 转录
```

**关键设计：**

- **AI 即采集器** — LLM 携带 web search tool 自主搜索，不需要预配置爬虫
- **一个 Key 即可启动** — 自动检测可用模型（Claude → GPT-4o → Gemini → 通义 → …）
- **维度并行** — 所有维度同时生成，互不阻塞
- **双语原生** — 中英文并行生成，不是翻译
- **模型可插拔** — 切换厂商无需改代码
- **插件可选** — `plugins/collect_*.py` 自动接入，用于补充结构化数据

---

## 支持的 AI 模型

| 厂商 | 推荐模型 | 原生搜索 | API 地址 | 获取 Key |
|------|----------|----------|----------|----------|
| **Anthropic** | claude-opus-4-6 / claude-sonnet-4-6 / claude-haiku-4-5-20251001 | ✅ tool use | `https://api.anthropic.com/v1/messages` | [console.anthropic.com](https://console.anthropic.com/) |
| **OpenAI** | gpt-5 / gpt-5-mini / o3 / o3-pro | ✅ MCP 原生 | `https://api.openai.com/v1/chat/completions` | [platform.openai.com](https://platform.openai.com/) |
| **Google** | gemini-2.5-pro / gemini-2.5-flash / gemini-2.5-flash-lite | ✅ google_search | `https://generativelanguage.googleapis.com/v1beta` | [aistudio.google.com](https://aistudio.google.com/) |
| **智谱 AI** | glm-4.6 / glm-4.6v / glm-4.6v-flash | ✅ web_search 插件 | `https://open.bigmodel.cn/api/paas/v4/chat/completions` | [bigmodel.cn](https://open.bigmodel.cn/) |
| **阿里通义** | qwen3-max / qwen3.5-plus / qwen3-coder-next | ✅ enable_search | `https://dashscope.aliyuncs.com/compatible-mode/v1` | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com/) |
| **月之暗面** | kimi-k2.5 / kimi-k2-0905-preview | ✅ $web_search | `https://api.moonshot.ai/v1/chat/completions` | [platform.moonshot.ai](https://platform.moonshot.ai/) |
| **百度文心** | ernie-5.0-thinking-preview / ernie-4.5 / ernie-x1.1-preview | ✅ baidu_search | `https://aistudio.baidu.com/llm/lmapi/v3/chat/completions` | [aistudio.baidu.com](https://aistudio.baidu.com/) |
| **Ollama** | llama3.3 / qwen2.5 / deepseek-r1 | ❌ 本地无联网 | `http://localhost:11434/v1` | 本地运行，无需 Key |

> GPT-4o 已于 2026年2月停用，OpenAI 低成本选项改用 `gpt-5-mini`。

**每日参考成本**（生成一期日报，4-5个维度）：

| 选择 | 每日费用 |
|------|---------|
| Ollama 本地 | **$0** — 跑在你自己机器上 |
| Gemini 2.5 Flash | **$0** — 免费额度足够日常使用 |
| 通义 qwen-plus / 智谱 glm-4.6 | **约 ¥0.5–2** |
| GPT-4o-mini / Claude Haiku | **约 $0.10–0.30** |
| GPT-4o / Claude Sonnet | **约 $1–3** |
| Claude Opus / o3 | **约 $5–15**（不建议日常用） |

**从免费开始**：Gemini Flash 或 Ollama 零成本跑起来，效果满意再升级模型。

---

## 参与贡献

欢迎贡献：

- **新数据采集器** — 更多 RSS、API 或平台适配器
- **AI 模型适配** — 支持更多大模型厂商
- **发布平台** — Substack、Medium、Ghost、LinkedIn 等
- **Web 界面** — 更好的引导流程、实时进度

重大改动请先开 Issue 讨论。

---

## 开源协议

**[MIT + Commons Clause](LICENSE)**

| 使用场景 | 费用 |
|----------|------|
| 个人使用、自部署 | 免费 |
| 学习、开源贡献、fork 改造 | 免费 |
| 商业部署（SaaS、代理服务、嵌入付费产品）| $1,000 USD / 部署授权 |

商业授权咨询：[GitHub Issues](https://github.com/lizecheng2021-maker/IntelFlow)

---

<p align="center">
  如果 IntelFlow 对你有帮助，欢迎给个 Star。<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
