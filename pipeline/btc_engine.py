# -*- coding: utf-8 -*-
"""
BTC 哨兵信号引擎 —— 规则全部固化自三篇报告：
- 一阶段：三锚归因（供给失能 / 需求链下化 / 流动性接管）
- 二阶段：动量体制、MOM4、K6 波动目标仓位、熊市波浪
- 三阶段：四态状态机、E1(1400DMA触底)/E2s(深度+动量确认)、顶部识别双轨
数据源：blockchain.info market-price 全历史日频（与报告同口径）。
"""
import json
import math
import urllib.request
import datetime as dt

import numpy as np
import pandas as pd

FETCH_URL = "https://api.blockchain.info/charts/market-price?timespan=all&format=json&sampled=false"

STATE_LABELS = {
    "capitulation": "出清期",
    "repair": "修复期",
    "expansion": "扩张期",
    "distribution": "分配/观望",
}


def fetch_prices():
    req = urllib.request.Request(FETCH_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode("utf-8"))
    df = pd.DataFrame(data["values"])
    df["date"] = pd.to_datetime(df["x"], unit="s", utc=True).dt.tz_localize(None).dt.normalize()
    df = df.rename(columns={"y": "price"})[["date", "price"]]
    df["price"] = df["price"].astype(float)
    df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    # 丢弃未完结的当日（UTC）数据点，保证信号稳定
    today_utc = pd.Timestamp(dt.datetime.utcnow().date())
    df = df[df["date"] < today_utc].reset_index(drop=True)
    return df


def _pct_rank_latest(series, window=730):
    s = series.dropna()
    if len(s) < 30:
        return None
    w = s.iloc[-window:]
    return float((w <= s.iloc[-1]).mean())


def _state_machine(s, dd, mom_ma10):
    """四态状态机（事件驱动，抗闪烁）。返回当前状态信息与逐日状态序列。"""
    state = "expansion"
    state_start = None
    seg_low = None          # 本段（出清/修复）迄今低点（不含当日）
    pos_streak = 0          # 出清期内 momMA10 连续 >0 天数
    neg_streak = 0          # 扩张期内 momMA10 连续 <0 天数
    states = {}
    for date, price in s.items():
        m = mom_ma10.get(date, np.nan)
        d = dd.get(date, np.nan)
        if np.isnan(m) or np.isnan(d):
            continue
        price = float(price)
        if state_start is None:
            state_start, seg_low = date, price
        # 全局规则：DD <= -30% 任何状态直接转出清
        if d <= -0.30 and state != "capitulation":
            state, state_start, seg_low = "capitulation", date, None
            pos_streak = 0
        elif state == "capitulation":
            pos_streak = pos_streak + 1 if m > 0 else 0
            if pos_streak >= 10:
                state, state_start, seg_low = "repair", date, None
        elif state == "repair":
            if seg_low is not None and price < seg_low * 0.97:
                # 证伪：跌破本段低点 3% → 退回出清
                state, state_start, seg_low = "capitulation", date, None
                pos_streak = 0
            elif d > -0.18:
                state, state_start = "expansion", date
                neg_streak = 0
        elif state == "expansion":
            neg_streak = neg_streak + 1 if m < 0 else 0
            if neg_streak >= 20:
                state, state_start = "distribution", date
        elif state == "distribution":
            if m > 0:
                state, state_start = "expansion", date
                neg_streak = 0
        # 更新段低点（不含当日，供次日证伪比较）
        if state in ("capitulation", "repair"):
            seg_low = price if seg_low is None else min(seg_low, price)
        states[date] = state
    last_date = s.index[-1]
    day_in_state = (last_date - state_start).days + 1
    return {
        "state": state,
        "state_start": state_start,
        "day_in_state": int(day_in_state),
        "seg_low": float(seg_low) if seg_low is not None else None,
        "pos_streak": int(pos_streak),
        "states": states,
    }


def compute_signals(df):
    s = df.set_index("date")["price"].sort_index()
    peak = s.cummax()
    dd = s / peak - 1.0

    ma1400 = s.rolling(1400).mean()
    ma200 = s.rolling(200).mean()
    ma111 = s.rolling(111).mean()
    ma350 = s.rolling(350).mean()
    dev1400 = s / ma1400 - 1.0
    dev200 = s / ma200 - 1.0
    pi_gap = ma111 / (2.0 * ma350) - 1.0

    mom_signs = []
    for n in (20, 60, 120, 250):
        mom_signs.append(np.sign(s / s.shift(n) - 1.0))
    mom4 = sum(mom_signs) / 4.0
    mom_ma10 = mom4.rolling(10).mean()

    ret = s.pct_change()
    vol60 = ret.rolling(60).std() * math.sqrt(365.0)
    k6_pos = (mom4 * (0.15 / vol60).clip(upper=2.0)).clip(-2.0, 2.0)

    r90 = s / s.shift(90) - 1.0

    sm = _state_machine(s, dd, mom_ma10)

    last = s.index[-1]
    price = float(s.iloc[-1])

    # ---- E1 左侧·价值信号：1400DMA 触底 ----
    lookback = 60
    dev_recent = dev1400.dropna().iloc[-lookback:]
    e1_touched = bool((dev_recent <= 0).any())
    touch_dates = dev1400.dropna()
    touch_dates = touch_dates[touch_dates <= 0]
    last_touch = touch_dates.index[-1] if len(touch_dates) else None
    seg_low = sm["seg_low"]
    invalidation_line = seg_low * 0.97 if seg_low else None
    e1_invalidated = bool(invalidation_line and price < invalidation_line)
    e1_active = bool(e1_touched and not e1_invalidated)

    # ---- E2s 右侧·确认信号：DD<=-40% 且 MOM4>=+0.5 ----
    depth_met = bool(dd.iloc[-1] <= -0.40)
    momentum_met = bool(mom4.iloc[-1] >= 0.5)
    e2s_active = bool(depth_met and momentum_met)

    # ---- 顶部识别双轨 ----
    dev1400_pct = _pct_rank_latest(dev1400)
    r90_pct = _pct_rank_latest(r90)
    overheat = 0
    if dev1400_pct is not None and dev1400_pct > 0.90:
        overheat += 1
    if r90_pct is not None and r90_pct > 0.90:
        overheat += 1
    pi_cross = bool(pi_gap.iloc[-1] >= 0) if not np.isnan(pi_gap.iloc[-1]) else False
    if pi_cross:
        overheat += 1

    # 右侧轨：扩张/分配期内 MOM4 翻空（首次 <=0）为离场扳机
    m = mom4.dropna()
    flip_date = None
    if len(m) >= 2:
        prev_pos = m.shift(1) > 0
        cur_nonpos = m <= 0
        flips = m.index[(~prev_pos) & cur_nonpos]
        if len(flips):
            flip_date = flips[-1]
    days_since_flip = (last - flip_date).days if flip_date is not None else None
    exit_cost = None
    if flip_date is not None:
        ref = float(s.loc[:flip_date].iloc[-1])
        exit_cost = price / ref - 1.0
    right_exit_active = bool(
        sm["state"] in ("expansion", "distribution")
        and days_since_flip is not None
        and days_since_flip <= 5
    )

    # ---- 顶部/底部区域合成 ----
    bottom_alert = bool(e1_active or e2s_active)
    bottom_reasons = []
    if e1_active:
        bottom_reasons.append("E1 价值信号已亮（价格触及 1400DMA 地板区）")
    if e2s_active:
        bottom_reasons.append("E2s 右侧确认已亮（深回撤 + 动量修复）")
    top_alert = bool(overheat >= 2 or right_exit_active)
    top_reasons = []
    if overheat >= 2:
        top_reasons.append(f"左侧过热组合 {overheat}/3 项命中（减分提示）")
    if right_exit_active:
        top_reasons.append("右侧动量翻空——离场扳机（无条件执行）")

    # ---- 状态机下一扳机 ----
    if sm["state"] == "capitulation":
        next_trigger = f"动量10日均连续为正满10天（当前 {sm['pos_streak']}/10）→ 转修复期"
    elif sm["state"] == "repair":
        next_trigger = "DD > -18% → 转扩张期；跌破本段低点3% → 证伪回出清"
    elif sm["state"] == "expansion":
        next_trigger = "动量连续20天<0 → 转分配/观望；DD ≤ -30% → 转出清"
    else:
        next_trigger = "动量回正 → 转扩张期；DD ≤ -30% → 转出清"

    # ---- 合成指令 ----
    if right_exit_active or (sm["state"] == "distribution" and overheat >= 2):
        directive = "顶部警戒区：左侧减分 + 右侧离场纪律优先，不加仓。"
    elif e2s_active:
        directive = "右侧确认已亮（E2s）：趋势不再与你为敌，可加速建仓至主仓位。"
    elif e1_active and sm["state"] in ("capitulation", "repair"):
        directive = ("左侧分批窗口开启（E1 已亮），右侧确认未亮：分批建仓、仓位压低档"
                     f"（波动预算 10–15%），跌破证伪线 {invalidation_line:,.0f} 停止分批。")
    elif sm["state"] == "expansion":
        directive = "扩张期：持有与加仓为主，顶部警戒双轨监控中。"
    elif sm["state"] == "distribution":
        directive = "分配/观望：减仓为主，等待动量回正或深度回撤信号。"
    else:
        directive = "出清/修复中：耐心等待 E1 触底或 E2s 右侧确认。"

    # ---- 图表序列（近 560 天）----
    win = s.iloc[-560:]
    series = {
        "dates": [d.strftime("%Y-%m-%d") for d in win.index],
        "price": [round(float(v), 0) for v in win.values],
        "ma1400": [None if np.isnan(v) else round(float(v), 0) for v in ma1400.loc[win.index].values],
        "ma200": [None if np.isnan(v) else round(float(v), 0) for v in ma200.loc[win.index].values],
    }

    signs = [int(np.sign(s.iloc[-1] / s.iloc[-1 - n] - 1.0)) for n in (20, 60, 120, 250)]

    # ---- 周期 cadence 带（像素场数据：逐日回撤深度 × 状态）----
    state_char = {"capitulation": "c", "repair": "r", "expansion": "e", "distribution": "d"}
    band = {
        "dd": [round(float(v), 4) for v in dd.loc[win.index].values],
        "states": "".join(state_char.get(sm["states"].get(d, "expansion"), "e") for d in win.index),
    }

    artifact = {
        "asOf": last.strftime("%Y-%m-%d"),
        "price": round(price, 0),
        "cyclePeak": round(float(peak.iloc[-1]), 0),
        "cyclePeakDate": s[s == peak.iloc[-1]].index[-1].strftime("%Y-%m-%d"),
        "ddFromPeak": round(float(dd.iloc[-1]), 4),
        "daysSincePeak": int((last - s[s == peak.iloc[-1]].index[-1]).days),
        "state": {
            "code": sm["state"],
            "label": STATE_LABELS[sm["state"]],
            "day": sm["day_in_state"],
            "since": sm["state_start"].strftime("%Y-%m-%d"),
            "nextTrigger": next_trigger,
        },
        "momentum": {
            "mom4": round(float(mom4.iloc[-1]), 2),
            "signs": signs,
            "momMA10": round(float(mom_ma10.iloc[-1]), 3),
            "posStreak": sm["pos_streak"],
        },
        "k6": {
            "position": round(float(k6_pos.iloc[-1]), 2),
            "vol60": round(float(vol60.iloc[-1]), 4),
            "budget": 0.15,
        },
        "e1": {
            "active": e1_active,
            "dev1400": round(float(dev1400.iloc[-1]), 4),
            "ma1400": round(float(ma1400.iloc[-1]), 0),
            "lastTouchDate": last_touch.strftime("%Y-%m-%d") if last_touch is not None else None,
            "segLow": round(seg_low, 0) if seg_low else None,
            "invalidationLine": round(invalidation_line, 0) if invalidation_line else None,
            "invalidated": e1_invalidated,
        },
        "e2s": {
            "active": e2s_active,
            "depthMet": depth_met,
            "momentumMet": momentum_met,
        },
        "top": {
            "overheatScore": int(overheat),
            "dev200": round(float(dev200.iloc[-1]), 4),
            "dev1400Pct": round(dev1400_pct, 3) if dev1400_pct is not None else None,
            "r90": round(float(r90.iloc[-1]), 4),
            "r90Pct": round(r90_pct, 3) if r90_pct is not None else None,
            "piGap": round(float(pi_gap.iloc[-1]), 4) if not np.isnan(pi_gap.iloc[-1]) else None,
            "piCross": pi_cross,
            "rightExitActive": right_exit_active,
            "daysSinceFlip": int(days_since_flip) if days_since_flip is not None else None,
            "exitCost": round(float(exit_cost), 4) if exit_cost is not None else None,
        },
        "directive": directive,
        "alerts": {
            "bottom": bottom_alert,
            "top": top_alert,
            "bottomReason": "；".join(bottom_reasons),
            "topReason": "；".join(top_reasons),
        },
        "series": series,
        "band": band,
    }
    return artifact
