# -*- coding: utf-8 -*-
"""
BTC 投资阶段观察面板 · 公开网页数据管道
- 复用 btc_engine（与 Kimi Work 内部日度哨兵同一套规则引擎）
- 产出仓库根目录 data.json；新闻流（news）为人工策展，管道运行时保留既有条目
- 静态研究表格（四次熊市/E1/E2s/右侧离场/K6 回测）固化自三篇报告
运行：python pipeline/sentinel_web.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from btc_engine import fetch_prices, compute_signals  # noqa: E402

DATA_PATH = os.path.join(ROOT, "data.json")

# ---- 静态研究内容（三篇报告的结论表，随报告版本手动更新）----
RESEARCH = {
    "bears": [
        {"name": "B1 · 2013–15", "path": "1,050 → 172", "depth": "-83.6%", "days": "407 天",
         "structure": "Mt.Gox 信用崩塌贯穿"},
        {"name": "B2 · 2017–18", "path": "17.5k → 3.2k", "depth": "-81.5%", "days": "365 天",
         "structure": "ICO 泡沫分层出清，约 5 主浪"},
        {"name": "B3 · 2021–22", "path": "67.0k → 15.8k", "depth": "-76.5%", "days": "377 天",
         "structure": "三层信用出清：LUNA/3AC → Celsius/矿企 → FTX/Genesis"},
        {"name": "B4 · 2025–进行中", "path": "124.8k → 58.6k（迄今）", "depth": "-53.1%（进行中）", "days": "267 天至谷底",
         "structure": "无信用事件浪：需求退潮型阴跌，六段反弹止步 +12~14%"},
    ],
    "e1Stats": {
        "title": "E1 左侧·价值信号（1400DMA 触底）· 全历史 25 次首次触发",
        "cols": ["", "90 日", "180 日", "365 日"],
        "rows": [
            ["前瞻收益中位", "+26%", "+70%", "+152%"],
            ["胜率", "74%", "84%", "100%"],
            ["同期任意日基准（2016+ 中位）", "+15%", "+36%", "+88%"],
        ],
        "note": "365 日胜率 100% 的样本 n=19 且含早期高波动年代，应读作「该位置历史上从未在一年后亏损」，而非「未来必胜」。",
    },
    "e2sStats": {
        "title": "E2s 右侧·确认信号（DD≤-40% 且 MOM4≥+0.5）· 2016 年后 68 次触发",
        "text": "180 日中位 +57%（基准 +36%）、365 日中位 +169%（基准 +88%）。E2s 的意义不是比 E1 更准，而是把「便宜」和「不再跌」分开确认。",
    },
    "topExits": {
        "title": "右侧动量离场轨 · 历次顶部 MOM4 首次翻空的耗时与成本（唯一单调改善的顶部指标）",
        "rows": [
            ["2013 顶", "+52 天", "-26%"],
            ["2017 顶", "+46 天", "-42%"],
            ["2021 春顶", "+8 天", "-15%"],
            ["2021 顶", "+9 天", "-15%"],
            ["2025 顶", "+4 天", "-9%"],
        ],
        "note": "左侧绝对阈值随周期衰减（距 200DMA 乖离 911%→18%），固定阈值全部失效；顶部不可左侧预测，只能左侧减分 + 右侧离场。",
    },
    "k6": {
        "title": "K6 执行层 · 四期限动量 × 15% 波动目标（2011–2026 全期回测）",
        "rows": [
            ["全期净值", "3,741x", "39x"],
            ["年化收益", "+72%", "+27%"],
            ["夏普比率", "0.72", "1.80"],
            ["最大回撤", "-87%", "-14%"],
            ["B1–B4 四次熊市", "-84% / -80% / -77% / -53%", "+21% / +13% / +7% / +12%"],
        ],
        "cols": ["", "买入持有", "K6 叠加策略"],
        "note": "动量作为 alpha 正在消失（IC 0.20→0.05），作为风控框架从未失效：夏普在 10%–40% 波动预算下恒为 1.79–1.80。",
    },
}

# ---- 新闻流（人工策展，近 1 个月最重要 10 条，按时间近→远；importance: high/mid）----
NEWS = [
    {"date": "2026-08-09", "importance": "high", "tag": "资金流",
     "title": "BTC 周涨 3.4% 收于 64,900 附近：ETF 回流 + 疲软就业数据重燃 9 月降息预期",
     "summary": "现货 ETF 需求回暖与弱于预期的美国劳动力数据共同推动反弹；但 66,800 美元阻力位未能突破，30 年期美债收益率 5.28% 创 19 年新高仍构成压制。",
     "source": "CoinStats", "url": "https://coinstats.app/ai/a/latest-news-for-bitcoin"},
    {"date": "2026-08-05", "importance": "mid", "tag": "安全事件",
     "title": "Coldcard 钱包漏洞（约 594 BTC）引发安全冲击，恐慌贪婪指数跌至 21",
     "summary": "硬件钱包 Coldcard 漏洞事件加剧避险情绪的波动，叠加 8 月历史季节性偏弱（中位收益约 -7%），市场一度滑向极度恐惧区间后随宏观数据缓和修复。",
     "source": "CoinStats", "url": "https://coinstats.app/ai/a/latest-news-for-bitcoin"},
    {"date": "2026-08-01", "importance": "high", "tag": "市场结构",
     "title": "7 月复盘：BTC 月度反弹 +9.8%，但成交量创 2023 年 11 月以来最弱",
     "summary": "K33 估算 7 月现货日均成交约 22 亿美元。反弹守在 6 月下旬低点之上、价格高于已实现价格（约 52,900），但仍低于 200 日均线逾 16%——「修复情绪多于修复图形」。",
     "source": "Business Finance News", "url": "https://businessfinance.news/bitcoin-august-2026-outlook-after-julys-9-8-rebound/"},
    {"date": "2026-07-31", "importance": "high", "tag": "ETF",
     "title": "现货 ETF 月底剧烈摆动：7/30 净流入 2.33 亿美元，7/31 净流出 2.65 亿美元",
     "summary": "Farside 数据显示月末两个交易日方向截然相反，印证需求退潮期资金流的无序特征——这正是需求驱动时代「边际买家」定价的直接观测窗口。",
     "source": "Farside / Business Finance News", "url": "https://businessfinance.news/bitcoin-august-2026-outlook-after-julys-9-8-rebound/"},
    {"date": "2026-07-29", "importance": "high", "tag": "宏观",
     "title": "FOMC 9–3 维持利率 3.50–3.75%：三名鹰派一致异议为 2016 年来首次",
     "summary": "Warsh 主席任内第二次会议按兵不动，但 Hammack/Kashkari/Logan 三人主张立即加息 25bp；30 年期美债收益率盘中创 2007 年以来新高，美股录得 2024 年末以来最差「美联储日」。",
     "source": "Lugen Family Office / Trading Strategy Guides", "url": "https://lugenfamilyoffice.com/economic-calendar-insights-wednesday-july-29-2026/"},
    {"date": "2026-07-22", "importance": "mid", "tag": "监管",
     "title": "CLARITY 法案推迟：参议院 8 月休会前表决无望，最早 9 月重启",
     "summary": "Lummis 参议员 7/22 发布最新草案，但民主党参议员认为官员伦理、消费者保护等条款仍不足；近期监管催化缺位，市场焦点转向 FOMC、ETF 资金流与经济数据。",
     "source": "Mobee", "url": "https://mobee.com/en/mobee-academy/market-update/market-update-hari-ini"},
    {"date": "2026-07-14", "importance": "mid", "tag": "宏观",
     "title": "6 月 CPI 低于预期：BTC 隔夜跳涨约 3.6% 逼近 65,000 美元",
     "summary": "通胀数据回落令加息预期骤降，再次验证流动性接管时代的定价结构——BTC 日频波动已是「美股时段风险偏好的同期映射」。",
     "source": "Pintu", "url": "https://pintu.co.id/news/286341-fomc-28-29-juli-2026-suku-bunga-ditahan-bitcoin-tunggu-sinyal-warsh"},
    {"date": "2026-07-13", "importance": "mid", "tag": "金库公司",
     "title": "Metaplanet 启动 Project Nova：以 43,000 枚 BTC 为日本数字公司债增信",
     "summary": "BTC 财库从「被动储备」转向「生产性金融基础设施」；公司目标 2027 年底持仓 210,000 枚。同周 Strategy 美元储备增至 30 亿美元（BTC 持仓 843,775 枚）。",
     "source": "Cryptonomist / Odaily", "url": "https://en.cryptonomist.ch/2026/07/13/metaplanet-bitcoin-securities-launch/"},
    {"date": "2026-07-10", "importance": "high", "tag": "资金流",
     "title": "资金大迁移：4 月以来黄金+比特币 ETF 净流出约 120 亿美元，半导体 ETF 净流入超 200 亿",
     "summary": "资金未离场而是换赛道；上市矿企加速转型 AI 算力（TeraWulf 年内 +73%），年底上市矿企或多达七成收入来自 AI 合约。Saylor 称系「周期性轮动」，市场分歧仍存。",
     "source": "币币情 / AMBCrypto", "url": "https://www.68bbq.com/news/detail/188086"},
    {"date": "2026-07-06", "importance": "high", "tag": "金库公司",
     "title": "Strategy 一周内卖出超 2 亿美元 BTC；Metaplanet 十周来首次买入 2,823 枚",
     "summary": "Strategy 于 6/30、7/5 两度减持合计 3,588 枚（均价约 5.9–6.1 万美元），持仓降至 843,775 枚；Metaplanet 以 $79,664 买入 2,823 枚。最大「边际买家」的杠杆与负债结构变化，是需求退潮型熊市的核心观测点。",
     "source": "ChainCatcher / SoSoValue", "url": "https://www.chaincatcher.com/article/2275169"},
]


def main():
    df = fetch_prices()
    artifact = compute_signals(df)

    # 保留既有新闻流（人工策展），否则写入内置版本
    news = NEWS
    if os.path.exists(DATA_PATH):
        try:
            old = json.load(open(DATA_PATH, encoding="utf-8"))
            if isinstance(old.get("news"), list) and old["news"]:
                news = old["news"]
        except Exception:
            pass

    artifact["news"] = news
    artifact["newsUpdatedAt"] = "2026-08-10"
    artifact["research"] = RESEARCH

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, separators=(",", ":"))

    # 与三阶段报告参考值的对账打印
    print("== 对账（报告 2026-08-09 读数）==")
    print(f"asOf={artifact['asOf']}  price={artifact['price']}  DD={artifact['ddFromPeak']}")
    print(f"state={artifact['state']['code']} day={artifact['state']['day']} since={artifact['state']['since']}")
    print(f"MOM4={artifact['momentum']['mom4']} signs={artifact['momentum']['signs']} K6={artifact['k6']['position']}")
    print(f"E1 active={artifact['e1']['active']} DEV1400={artifact['e1']['dev1400']} 证伪线={artifact['e1']['invalidationLine']}")
    print(f"E2s active={artifact['e2s']['active']}  top.overheat={artifact['top']['overheatScore']}")
    print(f"data.json written: {os.path.getsize(DATA_PATH)} bytes, news={len(news)} 条")


if __name__ == "__main__":
    main()
