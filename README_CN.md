<p align="center">
  <h1 align="center">IntelFlow</h1>
  <p align="center"><strong>一个 API Key，告诉 AI 你关注什么，自动生成你的日报</strong></p>
  <p align="center">开源框架，让 AI 通过搜索自动发现、分析、交付你定义的任何领域的情报。</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python 3.11+">
  <a href="https://github.com/lizecheng2021-maker/IntelFlow/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://www.lizecheng.net"><img src="https://img.shields.io/badge/%E5%AE%9E%E9%99%85%E4%BA%A7%E5%87%BA-lizecheng.net-orange.svg" alt="Live Demo"></a>
</p>

**[English](README.md)** | 中文

---

## 怎么用？

1. **填一个 AI 模型的 API Key** — Claude、GPT、Gemini、智谱 GLM、通义千问，或本地 Ollama 都行
2. **告诉它你关注什么** — 在 Web 面板定义你的关注维度（比如「AI 30%、加密货币 25%、SaaS 20%…」）
3. **AI 自动发现信息源** — 引擎通过搜索和内置采集器，自动找到你关注领域的相关信息
4. **拿到你的日报** — 多维度交叉分析报告，自动生成，自动发布

没有固定数据源，没有写死的话题。AI 根据**你定义的维度**去搜索和发现。

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/lizecheng2021-maker/IntelFlow.git
cd IntelFlow

# 2. 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 打开 Web 面板，粘贴你的 AI API Key
python web/app.py
# 浏览器打开 http://localhost:5050 → 粘贴一个 API Key → 设定关注领域 → 完成

# 4. 运行第一次采集
bash scripts/run_daily.sh
```

**就这么简单。** 一个 API Key 就能开始。其他全是可选的。

## 支持的 AI 模型

| 厂商 | 模型 | 说明 |
|------|------|------|
| Anthropic | Claude Sonnet / Opus / Haiku | 分析深度最强 |
| OpenAI | GPT-4o / GPT-4o-mini / o1 | 全球可用 |
| Google | Gemini 2.5 Pro / Flash | 有免费额度 |
| 智谱 AI | GLM-4-Plus / GLM-4 | 中文能力优秀 |
| 阿里通义 | Qwen-Max / Plus / Turbo | OpenAI 兼容接口 |
| Ollama | Llama 3 / Mistral / Qwen2 | 100% 本地运行，无需 API |

在 Web 面板随时切换，无需改代码。

## 核心指标

| 指标 | 数值 |
|------|------|
| 启动时间 | 约 5 分钟（粘贴 API Key + 设定维度） |
| 端到端运行 | 约 25 分钟/次 |
| 每日成本 | 约 $2-3（取决于你选的模型） |
| 输出 | 多维度分析报告，可选 AI 封面图 |
| 硬件要求 | 一台笔记本即可 |

## 定义你的维度

IntelFlow 的核心概念是**维度**——AI 用来组织研究方向的独立分析轨道。你在 Web 面板定义什么重要。

**加密货币交易员：**
- 市场信号 30% | 链上数据 25% | 监管动态 20% | DeFi 协议 15% | 宏观 10%

**SaaS 创始人：**
- 竞品情报 25% | 用户痛点 25% | 技术栈 20% | 融资动向 15% | 增长策略 15%

**学术研究者：**
- 论文发布 30% | 基金资助 20% | 会议动态 20% | 产业应用 15% | 政策影响 15%

**游戏开发者：**
- 行业动态 30% | 技术发布 25% | 社区舆情 20% | 竞品动向 15% | 平台政策 10%

AI 用这些维度来引导搜索方向、筛选信息优先级、组织最终报告。

## IntelFlow 的不同之处

**AI 驱动发现** — 你不需要手动收集信息源。AI 用搜索自动找到每个维度的相关信息。它发现的是正在发生的事，而不只是你已经知道要去哪找的东西。

**深度分析，不是摘要** — AI 跨维度交叉验证信号、识别结构性变化、输出独立判断。你可以配置分析深度和写作风格。

**分板块并行生成** — 每个维度独立分析、并行生成。单个板块失败不影响其他板块。

**可配置的编辑人格** — 在 Web 面板定义语气、口头禅、分析风格。输出的是「你的」日报，不是千篇一律的 AI 生成文。

**多平台发布** — 自动发布到 WordPress、飞书、Dev.to、Hashnode。或者直接本地看 Markdown。

## 系统架构

```
                        IntelFlow 流水线（约 25 分钟）
 ============================================================================

 采集（并行）                预处理              生成（并行）           发布
 ______________________     ___________         ____________________   ________
| Web 搜索              |   |           |       |                    | |        |
| RSS 订阅              |   |  prepare  |       |  板块 1             | | WP    |
| Hacker News          |-->|  briefing |--+--->|  板块 2             |->| 飞书  |
| GitHub Trending      |   |   .py     |  |   |  板块 3             | | Dev.to|
| Reddit               |   |___________|  |   |  板块 N             | |________|
| YouTube 转录          |        |         |   |____________________|
| 自定义采集器           |        v         |            |
|______________________|   AI 搜索验证     |            v
                                          |     assemble_report.py
                                          +------------+
```

**关键设计：**
- 每个采集器有 10 分钟超时——单个慢源不会阻塞整条管道
- AI 模型可插拔——切换厂商不需要改任何管道代码
- 失败板块自动重试一次，不影响其他板块
- 内置采集器（RSS、HN、GitHub、Reddit、YouTube）无需 API Key

## 扩展自定义采集器

想加自己的数据源？写一个输出 JSON 的 Python 脚本：

```bash
# 1. 创建 scripts/collect_mydata.py
#    - 接受 --date 和 --output 参数
#    - 输出 raw_mydata.json

# 2. 就这样——管道自动发现 collect_*.py 脚本
```

## 输出格式

- **日报** — 4,000-5,000 字，可选 AI 封面图
- **周报** — 8,000-10,000 字，跨维度聚合深度分析
- **月报** — 12,000-15,000 字，趋势综合

## 作者实际产出

作者每天用 IntelFlow 生成情报报告：

- **英文日报：** [www.lizecheng.net](https://www.lizecheng.net)
- **中文日报（飞书）：** [飞书文档](https://xv7exvpv861.feishu.cn/wiki/Sh8OwOyqningOvkE8MAcYSOwn8e?fromScene=spaceOverview)

你的配置会完全不同——取决于你定义的维度和你选的 AI 模型。

## 参与贡献

欢迎贡献：

- **新数据采集器** — 更多 RSS、API 或平台适配器
- **AI 模型适配** — 支持更多大模型厂商
- **发布平台** — Substack、Medium、Ghost、LinkedIn 等
- **Web 界面** — 更好的引导流程、实时进度

重大改动请先开 Issue 讨论。

## 开源协议

[MIT License](LICENSE) — 自由使用、修改、发布。

---

<p align="center">
  如果 IntelFlow 对你有帮助，欢迎给个 Star。<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
