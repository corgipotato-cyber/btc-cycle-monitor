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
    {"date": "2026-08-20", "importance": "high", "tag": "宏观",
     "title": "美联储纪要偏鹰但市场反转：BTC 时隔近 3 个月重回 6.9 万美元，AI 交易两日重挫",
     "summary": "多数官员称通胀不降则加息、Warsh 提议议息会议 8→6 次；但高盛美国广义 AI 篮子两日 -7.5%、SOXX -7.7%，动量崩塌、对冲基金创两年多最差单日——AI 交易降温引发资金轮动，BTC 与黄金（+4%）成为承接方向。",
     "source": "新浪财经", "url": "https://finance.sina.com.cn/roll/2026-08-20/doc-ininxeix6824701.shtml"},
    {"date": "2026-08-19", "importance": "high", "tag": "监管",
     "title": "特朗普出席白宫加密高管会议：Coinbase/Ripple/Gemini 等 CEO 与 CFTC、SEC 主席同台",
     "summary": "会议为 8/20 CFTC 创新咨询委员会首会（议题「从不确定走向清晰」）的前奏；CLARITY 法案 9 月将迎来参议院程序性表决——监管明晰化进程明显提速。",
     "source": "Odaily / 彭博", "url": "https://www.odaily.news/zh-CN/post/5212531"},
    {"date": "2026-08-18", "importance": "high", "tag": "资金流",
     "title": "三重卖压压顶：矿工抛售 + ETF 净流出 + Strategy 买盘放缓，BTC 回落至 6.42 万附近",
     "summary": "交易所余额增加，6.2 万美元支撑成为短线多空焦点——需求退潮期「边际买家」减速与供给端压力的叠加，正是本面板 K6 风控框架重点监测的组合形态。",
     "source": "币界网 / Decrypt", "url": "https://m.528btc.com/news/129384784.html"},
    {"date": "2026-08-18", "importance": "mid", "tag": "机构",
     "title": "花旗计划年内推出机构比特币托管服务，纳入 Custody+ 平台",
     "summary": "继托管、结算之后，华尔街大行在加密基础设施上的布局继续下沉；机构管道建设与价格周期并不同步，但决定下一轮需求复苏的承接能力。",
     "source": "币界网 / Decrypt", "url": "https://m.528btc.com/news/129384784.html"},
    {"date": "2026-08-18", "importance": "mid", "tag": "市场结构",
     "title": "Glassnode：Q3 可能构筑底部并出现早期积累迹象；Mudrex 预计 10–12 月见底、低点 5–5.5 万",
     "summary": "链上数据开始出现长期持有者的早期积累信号，与底部建仓区域的判定维度相互印证；但底部是「区间」而非「点位」，机构预测分歧仍大。",
     "source": "Cryptopolitan", "url": "https://www.cryptopolitan.com/bitcoin-price-prediction/"},
    {"date": "2026-08-15", "importance": "mid", "tag": "监管",
     "title": "韩国新规落地：8/19 起单一股票杠杆产品受限，8/20 起加密运营商审查扩至主要股东",
     "summary": "亚洲重要零售市场收紧杠杆与准入审查，短期压制局部投机需求；全球监管「收口子、立规矩」的节奏延续。",
     "source": "Odaily", "url": "https://www.odaily.news/zh-CN/post/5212515"},
    {"date": "2026-08-14", "importance": "mid", "tag": "资金流",
     "title": "2026 年以来上市矿企已卖出 2.8 万枚 BTC（约 17.8 亿美元）",
     "summary": "矿企持续抛售既是熊市中现金流压力的结果，也与转型 AI 算力的资本开支相关——矿工净卖出是供给端压力的常态化来源，已纳入哨兵体系监测。",
     "source": "Odaily", "url": "https://www.odaily.news/zh-CN/newsflash/509698"},
    {"date": "2026-08-13", "importance": "high", "tag": "ETF",
     "title": "截至 8/7 当周美国现货 BTC ETF 净流入 8.54 亿美元，创 4 月中旬以来最大单周净流入",
     "summary": "ETF 总 AUM 超 760 亿美元、占比特币市值 6.1%——需求端出现 4 个月来最强单周信号，但需观察其在 8 月中旬三重卖压下的持续性。",
     "source": "币界网 / SoSoValue", "url": "https://m.528btc.com/zhuanti/5313559.html"},
    {"date": "2026-08-11", "importance": "mid", "tag": "DeFi",
     "title": "cbBTC 接入 Syntetika 代币化策略平台，Morpho 抵押需求超 14 亿美元",
     "summary": "BTC 作为抵押品在链上信贷中的使用继续扩张；同期恐慌贪婪指数 28，仍处恐惧区间——基础设施在恐惧期持续建设是历次底部区域的共同特征。",
     "source": "CoinStats", "url": "https://coinstats.app/ai/a/latest-news-for-coinbase-wrapped-btc"},
    {"date": "2026-07-29", "importance": "high", "tag": "宏观",
     "title": "FOMC 9–3 维持利率 3.50–3.75%：三名鹰派一致异议为 2016 年来首次",
     "summary": "Warsh 主席任内第二次会议按兵不动，但 Hammack/Kashkari/Logan 三人主张立即加息 25bp；30 年期美债收益率盘中创 2007 年以来新高——高利率环境对估值的压制贯穿整个 8 月。",
     "source": "Lugen Family Office", "url": "https://lugenfamilyoffice.com/economic-calendar-insights-wednesday-july-29-2026/"},
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
    artifact["newsUpdatedAt"] = "2026-08-20"
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
