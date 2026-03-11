<p align="center">
  <h1 align="center">IntelFlow</h1>
  <p align="center"><strong>构建你自己的 AI 情报系统</strong></p>
  <p align="center">开源框架，不是成品工具。定义你的维度，接入你的数据源，生成你的日报。</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python 3.11+">
  <a href="https://github.com/lizecheng2021-maker/IntelFlow/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://www.lizecheng.net"><img src="https://img.shields.io/badge/%E5%AE%9E%E9%99%85%E4%BA%A7%E5%87%BA-lizecheng.net-orange.svg" alt="Live Demo"></a>
</p>

**[English](README.md)** | 中文

---

## 这是什么？

IntelFlow 是一个**开源框架**，用来构建你自己的 AI 情报日报系统。

它提供底层引擎能力——并行数据采集、智能去重、分板块 AI 分析、报告组装、多平台发布。**你来决定追踪什么领域、接入什么数据源、用什么风格输出。**

大多数 AI 新闻工具是写死的：固定源、固定话题、通用摘要。IntelFlow 把底层架构开放出来，让你针对自己的领域构建情报系统——不管你关注的是加密货币、生物科技、SaaS 竞品、本地政策、还是其他任何方向。

**作者用 IntelFlow 构建的实际作品：** [www.lizecheng.net](https://www.lizecheng.net)

## 核心指标

| 指标 | 数值 |
|------|------|
| 数据源类型 | RSS、API、网页抓取、YouTube 转录、Reddit、搜索引擎 |
| 分析维度 | 完全自定义（默认模板包含 7 个维度） |
| 端到端耗时 | 约 25 分钟 |
| 每日 API 成本 | 约 $2-3 |
| 输出 | 双语报告 + AI 封面图，自动发布到多平台 |
| 硬件要求 | 一台笔记本即可运行 |

## 为什么选 IntelFlow？

**1. 维度完全由你定义**

IntelFlow 不替你决定什么重要——你自己定。通过 Web 配置面板定义分析维度和权重。一个 VC 可能设：Deal Flow 30%、市场信号 25%、投后跟踪 20%、监管 15%、人才 10%。一个游戏开发者可能设：行业动态 30%、技术发布 25%、社区舆情 20%、竞品动向 15%、平台政策 10%。框架适配任何领域。

**2. 插件式数据架构**

数据采集器是独立的 Python 脚本。框架自带常用采集器（RSS、新闻 API、Hacker News、GitHub、Reddit、YouTube、财经 API）。添加自己的数据源很简单——写一个输出 JSON 的脚本，放到 `scripts/` 目录，自动接入流水线。

**3. 思维模型驱动分析，不是简单摘要**

AI 不只是缩写——它会跨维度交叉分析、识别结构性变化、输出独立判断。你可以配置分析深度和编辑风格。

**4. 分板块并行生成**

数据按维度拆分，每个板块独立生成、独立重试。单个板块失败不影响其他板块。既快又稳。

**5. 三层去重引擎**

多源数据必然有大量重复。IntelFlow 在采集、预处理、生成三个阶段逐层去重，确保每一段都有独立信息增量。

**6. 可配置的编辑人格**

通过 Web 配置面板定义分析人格——语气、口头禅、分析风格。输出的是「你的」日报，不是千篇一律的 AI 生成文。

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/lizecheng2021-maker/IntelFlow.git
cd IntelFlow

# 2. 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 通过 Web 界面配置
python web/app.py
# 浏览器打开 http://localhost:5000
# 配置 API 密钥、数据源、关注维度、写作风格

# 4. 运行第一次采集
bash scripts/run_daily.sh
```

### 需要的 API 密钥

| 服务 | 用途 | 免费额度 |
|------|------|----------|
| Claude (Anthropic) | 分析与写作 | 按量付费 |
| Gemini (Google) | 封面图生成 | 有免费额度 |
| GNews | 国际新闻采集 | 每天 100 次免费 |
| FMP | 美股数据 | 每天 250 次免费 |
| SerpAPI | 搜索兜底补充 | 每月 250 次免费 |

大部分数据源（Hacker News、GitHub Trending、AKShare、RSS 订阅、Reddit、YouTube 转录）**无需 API 密钥**。

## Web 配置面板

IntelFlow 内置 Flask Web 界面（`http://localhost:5000`）：

- **仪表盘** — 查看近期报告、系统状态、生成进度
- **密钥管理** — 安全配置所有服务凭据
- **数据源** — 启用/禁用单个源，设置采集参数
- **关注维度** — 调整各维度权重（例如 AI 30%、创业 20%、SEO 10%）
- **编辑风格** — 定义写作语气、分析深度、人格特征
- **发布平台** — 配置自动发布到 WordPress、飞书、公众号、Dev.to、LinkedIn
- **定时任务** — 设置每日运行时间，开关周末深度分析

## 维度框架（完全自定义）

IntelFlow 的核心概念是**维度**——独立的分析方向，每个维度有自己的数据源和权重。你来定义什么重要。

### 默认模板（7 个维度）

| 维度 | 默认权重 | 说明 |
|------|---------|------|
| AI 与技术 | 25% | 模型发布、工具上线、前沿研究 |
| 财经与市场 | 15% | 资金流向、财报、市场结构变化 |
| SEO 与搜索 | 15% | 算法更新、流量模式变化 |
| 创业与商业 | 15% | 新产品、融资、商业模式创新 |
| 电商 | 10% | 平台变动、转化策略、市场趋势 |
| 创作者经济 | 10% | 受众构建、内容策略、变现路径 |
| 宏观与政策 | 10% | 监管变化、地缘信号 |

### 按你的领域自定义

**加密货币交易员：**
- 市场信号 30% | 链上数据 25% | 监管动态 20% | DeFi 协议 15% | 宏观 10%

**SaaS 创始人：**
- 竞品情报 25% | 用户痛点 25% | 技术栈 20% | 融资动向 15% | 增长策略 15%

**学术研究者：**
- 论文发布 30% | 基金资助 20% | 会议动态 20% | 产业应用 15% | 政策影响 15%

通过 Web 配置面板或 `config/focus.json` 添加、删除、重命名维度。每个维度映射到你配置的数据源。

## 系统架构

```
                        IntelFlow 流水线（约 25 分钟）
 ============================================================================

 采集（并行）                预处理              生成（并行）           发布
 ______________________     ___________         ____________________   ________
| collect_news.py      |   |           |       |                    | |        |
| collect_finance.py   |   |  prepare  |       |  板块1: AI 前沿     | | 飞书   |
| collect_ai.py        |-->|  briefing |--+--->|  板块2: Builder    |->| WP    |
| collect_business.py  |   |   .py     |  |   |  板块3: 创业商机    | | 公众号 |
| collect_youtube.py   |   |___________|  |   |  板块4: SEO        | | Dev.to|
| collect_tavily.py    |        |         |   |  板块5: 资金信号    | | LI    |
| search_supplement.py |        v         |   |  板块6: 宏观       | |________|
| collect_lunar.py     |   WebSearch      |   |____________________|
|______________________|   信息验证        |            |
                          (Claude)        |            v
                                          |     assemble_report.py
                                          |     （组装完整报告）
                                          |            |
                                          |            v
                                          |     AI 封面图生成
                                          |     (Gemini + 风格参考图)
                                          |            |
                                          +------------+
```

**关键设计决策：**
- 每个采集器有 10 分钟超时保护——单个慢 API 不会阻塞整条管道
- 分板块生成意味着每个维度只读自己那部分数据
- 失败板块自动重试一次，不影响其他板块
- YouTube 转录 API 有三层降级：直接 API、WebSearch 补充、板块级搜索

## 三层去重引擎

| 层级 | 阶段 | 方法 |
|------|------|------|
| 第一层 | 数据采集 | URL + 标题去重，跨源合并 |
| 第二层 | 预处理 | 语义相似度聚类，合并同一事件的多源报道 |
| 第三层 | 内容生成 | 跨板块引用检查，消除重复分析 |

## 月度成本估算

| 项目 | 费用 |
|------|------|
| Claude API（分析 + 写作） | 约 $60-75/月 |
| Gemini API（封面图） | 约 $8/月 |
| GNews、FMP、SerpAPI | 免费额度内 |
| 其他数据源 | 免费（RSS、公开 API） |
| **合计** | **约 $70-85/月** |

全部在本地运行，无需服务器。

## 输出格式

- **日报** — 4,000-5,000 字，中英双语，含 AI 生成封面图
- **周报** — 8,000-10,000 字，跨维度聚合深度分析
- **月报** — 12,000-15,000 字，趋势综合 + 30 天财经数据回顾

## 参与贡献

IntelFlow 正在积极开发中，欢迎在以下方向贡献：

- **新数据源采集器** — 支持更多 RSS、API 或平台
- **分析能力提升** — 更好的去重算法、更智能的板块拆分
- **发布平台集成** — 新的平台适配器（Substack、Medium、Ghost 等）
- **Web 界面增强** — 更丰富的仪表盘、实时进度展示
- **文档完善** — 教程、配置指南、部署说明

重大改动请先开 Issue 讨论。

## 作者实际产出

作者每天用 IntelFlow 追踪 AI、SEO、财经、创业方向，发布在：

- **英文日报：** [www.lizecheng.net](https://www.lizecheng.net)
- **中文日报（飞书）：** [飞书文档](https://xv7exvpv861.feishu.cn/wiki/Sh8OwOyqningOvkE8MAcYSOwn8e?fromScene=spaceOverview)

你的配置会完全不同——取决于你定义的维度和数据源。

## 开源协议

[MIT License](LICENSE) — 自由使用、修改、发布。

---

<p align="center">
  如果 IntelFlow 对你有帮助，欢迎给个 Star。<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
