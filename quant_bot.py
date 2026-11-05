#!/usr/bin/env python3
"""Sade BIST tarayıcısı: yalnızca RSI, MACD ve SuperTrend kullanır."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

BIST30 = [
    "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", "BRSAN.IS",
    "CIMSA.IS", "CWENE.IS", "DOAS.IS", "EKGYO.IS", "ENKAI.IS", "EREGL.IS",
    "EUPWR.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS",
    "KCHOL.IS", "KONTR.IS", "KOZAL.IS", "KRDMD.IS", "ODAS.IS", "PGSUS.IS",
    "SAHOL.IS", "SASA.IS", "SISE.IS", "TCELL.IS", "THYAO.IS", "TUPRS.IS",
    "YKBNK.IS",
]
PERIOD = "2y"
RSI_PERIODS, RSI_OVERSOLD, RSI_OVERBOUGHT = (7, 10, 14), 30, 70
MACD_CONFIGS, MACD_SIGNAL = ((8, 21), (12, 26)), 9
MACD_FAST, MACD_SLOW = MACD_CONFIGS[-1]
ST_CONFIGS = ((10, 3.0), (14, 2.0))
STOP_RATES = (0.05, 0.08, 0.12)
COMMISSION = 0.002
OUTPUT = Path(__file__).resolve().parent / "signals.json"


def extract_ticker(raw: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker in raw.columns.get_level_values(0):
            df = raw[ticker].copy()
        elif ticker in raw.columns.get_level_values(1):
            df = raw.xs(ticker, axis=1, level=1).copy()
        else:
            return None
    else:
        df = raw.copy()
    df.columns = [str(col).title() for col in df.columns]
    required = ["Open", "High", "Low", "Close"]
    if not all(col in df.columns for col in required):
        return None
    df = df[required].apply(pd.to_numeric, errors="coerce").dropna()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df if len(df) >= 50 else None


def calculate_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False).mean()
    relative_strength = avg_gain / (avg_loss + 1e-10)
    return 100 - 100 / (1 + relative_strength)


def calculate_supertrend(df: pd.DataFrame, period: int, multiplier: float) -> tuple[pd.Series, pd.Series]:
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = pd.Series(tr, index=df.index).rolling(period, min_periods=period).mean().to_numpy()
    midpoint = (high + low) / 2
    basic_upper = midpoint + multiplier * atr
    basic_lower = midpoint - multiplier * atr
    final_upper = np.full(len(df), np.nan)
    final_lower = np.full(len(df), np.nan)
    trend = np.zeros(len(df), dtype=int)
    line = np.full(len(df), np.nan)

    for i in range(len(df)):
        if not np.isfinite(atr[i]):
            continue
        if i == 0 or not np.isfinite(final_upper[i - 1]):
            final_upper[i], final_lower[i] = basic_upper[i], basic_lower[i]
            trend[i], line[i] = 1, final_lower[i]
            continue
        final_upper[i] = basic_upper[i] if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1] else final_upper[i - 1]
        final_lower[i] = basic_lower[i] if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1] else final_lower[i - 1]
        previous_trend = trend[i - 1]
        if previous_trend < 0 and close[i] > final_upper[i - 1]:
            trend[i] = 1
        elif previous_trend > 0 and close[i] < final_lower[i - 1]:
            trend[i] = -1
        else:
            trend[i] = previous_trend or 1
        line[i] = final_lower[i] if trend[i] > 0 else final_upper[i]

    trend_series = pd.Series(trend, index=df.index).replace(0, np.nan).ffill()
    return trend_series, pd.Series(line, index=df.index)


def backtest_signal(close: pd.Series, signals: pd.Series, trailing_rate: float) -> float:
    """Eski algoritmadaki kapanış fiyatlı, komisyonlu ve yüzde iz süren stop backtesti."""
    cash, shares, peak = 10000.0, 0.0, 0.0
    for price, signal in zip(close.to_numpy(dtype=float), signals.to_numpy(dtype=float)):
        if not np.isfinite(signal):
            continue
        if shares > 0:
            peak = max(peak, price)
            if price <= peak * (1 - trailing_rate):
                cash = shares * price * (1 - COMMISSION)
                shares, peak = 0.0, 0.0
                continue
        if signal == 1 and cash > 0:
            shares = cash * (1 - COMMISSION) / price
            cash, peak = 0.0, price
        elif signal == -1 and shares > 0:
            cash = shares * price * (1 - COMMISSION)
            shares, peak = 0.0, 0.0
    final_value = cash + shares * float(close.iloc[-1])
    return (final_value / 10000.0 - 1) * 100


def choose_best_model(prices: pd.DataFrame) -> dict:
    """RSI, MACD ve SuperTrend'in eski botta kullanılan parametrelerini karşılaştırır."""
    close = prices["Close"]
    candidates = []
    for period in RSI_PERIODS:
        rsi = calculate_rsi(close, period)
        signal = pd.Series(np.where(rsi < RSI_OVERSOLD, 1, np.where(rsi > RSI_OVERBOUGHT, -1, 0)), index=close.index)
        candidates.append(("RSI", {"periyot": period}, signal))
    for fast, slow in MACD_CONFIGS:
        line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
        signal_line = line.ewm(span=MACD_SIGNAL, adjust=False).mean()
        state = pd.Series(np.where(line > signal_line, 1, -1), index=close.index)
        candidates.append(("MACD", {"hizli": fast, "yavas": slow, "sinyal": MACD_SIGNAL}, state.diff() / 2))
    for period, multiplier in ST_CONFIGS:
        trend, _ = calculate_supertrend(prices, period, multiplier)
        candidates.append(("SuperTrend", {"periyot": period, "carpan": multiplier}, trend.diff() / 2))

    best = None
    for name, params, signal in candidates:
        for stop in STOP_RATES:
            result = backtest_signal(close, signal, stop)
            if best is None or result > best["backtest_getiri_yuzde"]:
                best = {"ad": name, "parametreler": params, "stop_yuzde": stop * 100,
                        "backtest_getiri_yuzde": result, "sinyal_serisi": signal}
    return best


def scan_one(ticker: str, prices: pd.DataFrame) -> dict:
    close = prices["Close"]
    rsi = calculate_rsi(close, 14)
    macd_line = close.ewm(span=MACD_FAST, adjust=False).mean() - close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_signal = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    macd_state = (macd_line > macd_signal).astype(int).replace(0, -1)
    macd_change = macd_state.diff()
    st_trend, st_line = calculate_supertrend(prices, 10, 3.0)
    st_change = st_trend.diff()

    last = prices.index[-1]
    last_rsi = float(rsi.loc[last])
    rsi_signal = "AL" if last_rsi < RSI_OVERSOLD else "SAT" if last_rsi > RSI_OVERBOUGHT else "NÖTR"
    macd_event = "AL" if macd_change.loc[last] == 2 else "SAT" if macd_change.loc[last] == -2 else "YOK"
    st_event = "AL" if st_change.loc[last] == 2 else "SAT" if st_change.loc[last] == -2 else "YOK"

    buy_reasons, sell_reasons = [], []
    if rsi_signal == "AL":
        buy_reasons.append("RSI 30 altı")
    elif rsi_signal == "SAT":
        sell_reasons.append("RSI 70 üstü")
    if macd_event == "AL":
        buy_reasons.append("MACD yukarı kesişim")
    elif macd_event == "SAT":
        sell_reasons.append("MACD aşağı kesişim")
    if st_event == "AL":
        buy_reasons.append("SuperTrend yukarı döndü")
    elif st_event == "SAT":
        sell_reasons.append("SuperTrend aşağı döndü")

    best = choose_best_model(prices)
    winning_signal = best["sinyal_serisi"].iloc[-1]
    winning_signal = 0 if pd.isna(winning_signal) else int(winning_signal)
    overall = "AL" if winning_signal == 1 else "SAT" if winning_signal == -1 else "İZLE"
    return {
        "hisse": ticker.removesuffix(".IS"), "tarih": last.strftime("%Y-%m-%d"), "sinyal": overall,
        "aktif_gosterge_tetikleri": {"al": buy_reasons, "sat": sell_reasons},
        "en_iyi_model": best["ad"], "en_iyi_parametreler": best["parametreler"],
        "izleyen_stop_yuzde": best["stop_yuzde"], "model_backtest_getirisi_yuzde": round(best["backtest_getiri_yuzde"], 2),
        "fiyat": round(float(close.loc[last]), 2), "rsi": round(last_rsi, 2), "rsi_durumu": rsi_signal,
        "macd": round(float(macd_line.loc[last]), 4), "macd_sinyal_cizgisi": round(float(macd_signal.loc[last]), 4),
        "macd_yonu": "YUKARI" if macd_state.loc[last] == 1 else "AŞAĞI", "macd_tetik": macd_event,
        "supertrend_yonu": "YUKARI" if st_trend.loc[last] > 0 else "AŞAĞI",
        "supertrend_cizgisi": round(float(st_line.loc[last]), 2) if pd.notna(st_line.loc[last]) else None,
        "supertrend_tetik": st_event,
        "en_iyi_model_tetik": winning_signal,
    }


def main() -> int:
    print(f"⏳ Yalnızca RSI, MACD ve SuperTrend ile {len(BIST30)} hisse taranıyor...")
    raw = yf.download(BIST30, period=PERIOD, interval="1d", auto_adjust=True,
                      group_by="ticker", progress=False, threads=True)
    results = []
    for ticker in BIST30:
        prices = extract_ticker(raw, ticker)
        if prices is None:
            print(f"⚠️ {ticker}: yeterli veri yok, atlandı.")
            continue
        try:
            results.append(scan_one(ticker, prices))
        except Exception as exc:
            print(f"⚠️ {ticker}: {type(exc).__name__}: {exc}")

    minimum_coverage = max(1, len(BIST30) // 2)
    if len(results) < minimum_coverage:
        raise RuntimeError(f"Yetersiz veri kapsamı ({len(results)}/{len(BIST30)}); mevcut signals.json korunuyor.")

    priority = {"AL": 0, "SAT": 1, "İZLE": 2}
    results.sort(key=lambda row: (priority[row["sinyal"]], -row["model_backtest_getirisi_yuzde"]))
    counts = {name: sum(row["sinyal"] == name for row in results) for name in ("AL", "SAT", "İZLE")}
    payload = {
        "surum": "rsi-macd-supertrend-only",
        "guncelleme_utc": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "parametre_araligi": {"rsi_periyotlari": RSI_PERIODS, "rsi_al": RSI_OVERSOLD, "rsi_sat": RSI_OVERBOUGHT,
                               "macd_hizli_yavas": MACD_CONFIGS, "macd_sinyal": MACD_SIGNAL,
                               "supertrend_periyot_carpan": ST_CONFIGS, "izleyen_stop_yuzde": [round(x * 100) for x in STOP_RATES]},
        "kurallar": "RSI<30 AL, RSI>70 SAT; MACD ve SuperTrend yön değişiminde AL/SAT; yalnızca RSI, MACD ve SuperTrend modelleri karşılaştırılır; her hisse için en iyi backtest modeli seçilir.",
        "sinyal_sayilari": counts, "sinyaller": results,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Sinyal sayıları: AL {counts['AL']} | SAT {counts['SAT']} | İZLE {counts['İZLE']}")
    for row in results:
        print(f"{row['hisse']}: {row['sinyal']} | Model {row['en_iyi_model']} {row['en_iyi_parametreler']} | "
              f"RSI {row['rsi']} ({row['rsi_durumu']}) | "
              f"MACD {row['macd_yonu']} / {row['macd_tetik']} | "
              f"ST {row['supertrend_yonu']} / {row['supertrend_tetik']} | "
              f"2y model sonucu %{row['model_backtest_getirisi_yuzde']} | stop %{row['izleyen_stop_yuzde']}")
    print(f"JSON kaydedildi: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
