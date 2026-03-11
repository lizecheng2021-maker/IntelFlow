<p align="center">
  <h1 align="center">IntelFlow</h1>
  <p align="center"><strong>多源情报引擎</strong></p>
  <p align="center">不是新闻聚合器，是一台思维机器。</p>
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

IntelFlow 是一个自部署的 AI 情报日报系统。它从 30+ 数据源自动采集信息，通过 10 个维度交叉分析，生成中英双语深度报告，并自动发布到多个平台。

大多数 AI 新闻工具做的是摘要——把长文变短。IntelFlow 做的是分析：**这件事的本质是什么？它反映了什么正在发生的结构性变化？不同领域的信号之间有什么关联？**

产出的不是一份资讯流水账，而是一份训练商业判断力的情报简报。

**实际产出：** [www.lizecheng.net](https://www.lizecheng.net)

## 核心指标

| 指标 | 数值 |
|------|------|
| 数据源 | 30+（新闻、财经、AI、SEO、电商、Reddit、YouTube、RSS） |
| 分析维度 | 10 个（宏观、财经、AI、SEO、电商、增长、创业、创作者经济、Reddit 痛点、YouTube Builder） |
| 端到端耗时 | 约 25 分钟 |
| 每日 API 成本 | 约 $2-3 |
| 输出 | 中英双语报告 + AI 封面图，自动发布到 5+ 平台 |
| 硬件要求 | 一台 MacBook 即可运行 |

## 为什么选 IntelFlow？

**1. 多维交叉覆盖，打破信息茧房**

不只看科技，不只看财经。10 个维度同时覆盖——宏观政策、资金流向、AI 动态、SEO 变化、电商趋势、创业信号、Builder 实战策略。洞察往往出现在维度的交叉点上。

**2. 思维模型驱动分析，不是简单摘要**

每条信息经过多层分析框架处理。系统识别根因、结构性变化、跨领域影响，输出的是独立判断——不是复读机式的"值得关注"。

**3. 分板块并行生成**

数据按维度拆分，每个板块独立生成、独立重试。单个板块失败不影响其他板块。这让生成过程既快又稳。

**4. 三层去重引擎**

30+ 数据源必然有大量重复。IntelFlow 在采集、预处理、生成三个阶段逐层去重，确保每一段都有独立信息增量。

**5. 可配置的编辑风格**

通过 Web 配置面板，你可以定义分析人格——语气、维度权重、深度偏好。系统根据你的设定调整写作风格，输出的是"你的"日报，不是千篇一律的 AI 生成文。

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

## 十维情报框架

| # | 维度 | 采集什么 | 主要数据源 |
|---|------|----------|-----------|
| 1 | 宏观趋势与政策 | 监管变化、地缘信号 | GNews、中文 RSS |
| 2 | 财经与投资 | 资金流向、财报、市场结构 | FMP、AKShare、yfinance |
| 3 | AI 与技术前沿 | 模型发布、工具上线、前沿研究 | Hacker News、GitHub Trending |
| 4 | SEO 与搜索生态 | 算法更新、流量模式变化 | SEJ、Moz、Ahrefs Blog、Search Engine Land |
| 5 | 独立站与电商 | 平台变动、转化策略 | WP Tavern、Shopify、WooCommerce |
| 6 | 增长与变现 | 漏斗策略、定价实验 | a16z、First Round Review、Neil Patel |
| 7 | 创业与商业模式 | 新产品、融资、业务转型 | Product Hunt、Indie Hackers、Reddit |
| 8 | 个人品牌与创作者经济 | 受众构建、内容策略 | Publish Press 等 |
| 9 | Reddit 商业痛点 | 真实用户问题、未满足的需求 | r/Entrepreneur、r/SideProject、r/startups、r/SaaS |
| 10 | YouTube Builder 情报 | 实战经验、战术拆解 | 22+ 频道（三层优先级） |

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

## 实际产出

每天的 IntelFlow 产出发布在 **[www.lizecheng.net](https://www.lizecheng.net)**

## 开源协议

[MIT License](LICENSE) — 自由使用、修改、发布。

---

<p align="center">
  如果 IntelFlow 对你有帮助，欢迎给个 Star。<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
