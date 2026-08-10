# BTC 投资阶段观察面板（公开网页版）

基于三阶段研究（价格锚归因 / 流动性接管后的动量学 / 观测面板产品化）的 BTC 投资阶段公开监测面板：四态状态机（出清→修复→扩张→分配）、E1/E2s/K6 三层建仓信号、顶部识别双轨、周期状态带，以及近 1 个月重要新闻流。静态站点（GitHub Pages）+ GitHub Actions 每日刷新。

## 框架来源

全部规则固化自三篇报告（《BTC 价格锚分阶段归因研究》《BTC 价格形成机制研究·二阶段》《BTC 观测面板·三阶段》），与 Kimi Work 内部「BTC 价格周期观察面板」看板共用同一套信号引擎（`pipeline/btc_engine.py`）：

- **阶段判定器**：回撤滞回（-30%/-18%）× 动量 10 日均 × 事件驱动转换的四态状态机
- **E1 左侧·价值**：1400DMA（200 周均线）触底——全历史 25 次触发，365 日前瞻胜率 100%
- **E2s 右侧·确认**：DD≤-40% 且 MOM4≥+0.5——2016 年后 68 次触发，365 日中位 +169%
- **K6 执行层**：四期限动量 × 15% 波动目标，四次熊市全部转正、夏普 1.80 预算不变
- **顶部识别双轨**：左侧过热组合（两年滚动分位）只做减分 + 右侧动量翻空无条件离场

## 数据源与更新

| 数据 | 来源 | 说明 |
|---|---|---|
| BTC 价格全历史日频 | blockchain.info `market-price`（`sampled=false`） | UTC 窗口均值，与三篇报告同口径 |
| 新闻流 | 人工策展（`pipeline/sentinel_web.py` 内 `NEWS`） | 近 1 个月 10 条，按时间近→远；管道刷新时保留既有条目 |

- `.github/workflows/update.yml`：每天 UTC 00:40（北京时间 08:40，UTC 日频收盘后），支持 `workflow_dispatch` 手动触发
- 管道产出仓库根 `data.json`；有变更则由 github-actions bot 自动 commit + push
- 页面 `index.html` 加载时先 `fetch('data.json')`，失败则使用内嵌兜底数据（`INITIAL_DATA`）

## 本地运行

```bash
pip install -r pipeline/requirements.txt
python pipeline/sentinel_web.py   # 产出 data.json，并打印与报告参考值的对账
```

## 免责声明

本页面为研究框架的操作化演练，不构成投资建议。信号历史有效性不代表未来，加密资产波动极端，杠杆尤甚。仓位决策责任在使用者。
