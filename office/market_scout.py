import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from config import (
    SWING_CONFIG, 
    is_thai_stock, 
    normalize_symbol, 
    clean_display_symbol, 
    get_currency_symbol, 
    get_market_tag
)
from office.database import get_watchlist

def fetch_stock_data(symbol: str, period: str = "1y", interval: str = "1d", min_bars: int = 1) -> Optional[pd.DataFrame]:
    """ดึงข้อมูลราคาหุ้นย้อนหลัง (รองรับทั้งหุ้นไทยและสหรัฐฯ)"""
    sym = symbol.strip().upper()
    
    # พยายามดึงครั้งแรก
    try:
        ticker = yf.Ticker(sym)
        df = ticker.history(period=period, interval=interval)
        if df is not None and not df.empty and len(df) >= min_bars:
            return df
    except Exception:
        pass

    # หากไม่พบ และเป็นไปได้ว่าเป็นหุ้นไทย ให้ลองเติม .BK
    if not sym.endswith(".BK") and not sym.startswith("^"):
        try:
            ticker_bk = yf.Ticker(f"{sym}.BK")
            df_bk = ticker_bk.history(period=period, interval=interval)
            if df_bk is not None and not df_bk.empty and len(df_bk) >= min_bars:
                return df_bk
        except Exception:
            pass

    return None

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """คำนวณ Technical Indicators สำคัญสำหรับ Swing Trading"""
    df = df.copy()

    # 1. เส้น Exponential Moving Average (EMA)
    df["EMA_20"] = df["Close"].ewm(span=SWING_CONFIG["ema_fast"], adjust=False).mean()
    df["EMA_50"] = df["Close"].ewm(span=SWING_CONFIG["ema_slow"], adjust=False).mean()
    df["EMA_200"] = df["Close"].ewm(span=SWING_CONFIG["ema_trend"], adjust=False).mean()

    # 2. RSI (Relative Strength Index 14)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=SWING_CONFIG["rsi_period"]).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=SWING_CONFIG["rsi_period"]).mean()
    rs = gain / (loss + 1e-9)
    df["RSI"] = 100 - (100 / (1 + rs))

    # 3. Volume Average (SMA 20) & Volume Spike
    df["Vol_SMA20"] = df["Volume"].rolling(window=20).mean()
    df["Vol_Ratio"] = df["Volume"] / (df["Vol_SMA20"] + 1e-9)

    # 4. 20-day High and Low (สำหรับแนวรับแนวต้าน)
    df["High_20"] = df["High"].rolling(window=20).max()
    df["Low_20"] = df["Low"].rolling(window=20).min()

    # 5. Average True Range (ATR 14) วัดความผันผวนสำหรับวาง Stop Loss
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(window=14).mean()

    return df

def evaluate_swing_setup(symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
    """ประเมินกราฟและจับคู่กลยุทธ์ Swing Trade (ทั้งไทยและสหรัฐฯ)"""
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = float(last["Close"])
    prev_close = float(prev["Close"])
    change_pct = ((price - prev_close) / prev_close) * 100
    
    ema20 = float(last["EMA_20"])
    ema50 = float(last["EMA_50"])
    ema200 = float(last["EMA_200"])
    rsi = float(last["RSI"])
    vol_ratio = float(last["Vol_Ratio"])
    atr = float(last["ATR"]) if not np.isnan(last["ATR"]) else price * 0.03
    high20 = float(last["High_20"])
    low20 = float(last["Low_20"])

    curr_sym = get_currency_symbol(symbol)
    disp_sym = clean_display_symbol(symbol)
    market_tag = get_market_tag(symbol)

    # ตรวจสอบแนวโน้มหลัก
    is_bullish_trend = price > ema200 and ema50 > ema200
    is_short_trend_up = price > ema50

    setup_found = None
    signal = "NEUTRAL"
    score = 50
    reason = []

    # Setup A: Pullback to EMA (ย่อตัวในแนวโน้มขาขึ้น)
    dist_to_ema20 = abs(price - ema20) / ema20
    dist_to_ema50 = abs(price - ema50) / ema50
    if is_bullish_trend and (dist_to_ema20 < 0.028 or dist_to_ema50 < 0.028) and (38 <= rsi <= 56):
        setup_found = "ย่อพักตัวใกล้แนวรับ EMA (Trend Pullback)"
        signal = "BUY"
        score = 85
        reason.append(f"ราคาอยู่ในแนวโน้มขาขึ้นเหนือ EMA 200 ({curr_sym}{ema200:.2f}) แต่กำลังย่อพักตัวใกล้เส้น EMA 20/50")
        reason.append(f"RSI อยู่ที่ {rsi:.1f} โซนพักตัว ยังไม่ตึงตัว มีโอกาสเด้งกลับตามแนวโน้มเดิม")

    # Setup B: Breakout with Volume (เบรกเอาท์พร้อมแรงซื้อ)
    elif is_short_trend_up and price >= high20 * 0.99 and vol_ratio > 1.3:
        setup_found = "ทะลุแนวต้าน 20 วันพร้อมวอลุ่ม (Momentum Breakout)"
        signal = "BUY"
        score = 80
        reason.append(f"ราคาทะลุกรอบ High 20 วัน พร้อมปริมาณการซื้อขายหนาแน่นกว่าปกติ {vol_ratio:.1f} เท่า")
        reason.append(f"โมเมนตัมแข็งแกร่ง RSI อยู่ที่ {rsi:.1f}")

    # Setup C: Oversold Reversal (เด้งจากจุดขายมากเกินไป)
    elif rsi < 36 and price >= prev_close:
        setup_found = "สัญญาณดีดตัวจากโซนขายมากเกินไป (Oversold Bounce)"
        signal = "WATCH"
        score = 65
        reason.append(f"RSI ตกลงมาต่ำมาก ({rsi:.1f}) และเริ่มมีแรงซื้อพยุงราคากลับ")

    # Setup D: Overbought Warning (หุ้นขึ้นมาสูงเกินไป ไม่ควรไล่ราคา)
    elif rsi > 72:
        setup_found = "ราคาตึงตัวสูง (Overbought - ห้ามไล่ราคา)"
        signal = "OVERBOUGHT"
        score = 40
        reason.append(f"RSI สูงถึง {rsi:.1f} เสี่ยงที่จะเกิดการย่อตัวแรง ไม่เหมาะกับการเข้าซื้อใหม่")

    else:
        if is_bullish_trend:
            setup_found = "ประคองตัวในแนวโน้มขาขึ้น (Consolidating)"
            signal = "WATCH"
            score = 60
            reason.append("ทรงกราฟยังเป็นขาขึ้น แต่ยังไม่มีจุดเข้าซื้อที่ได้เปรียบ")
        else:
            setup_found = "แนวโน้มไม่ชัดเจนหรือขาลง (Sideway / Downtrend)"
            signal = "AVOID"
            score = 30
            reason.append("ราคาอยู่ใต้เส้นค่าเฉลี่ยหลัก แนะนำหลีกเลี่ยงการเข้าซื้อ")

    # คำนวณจุด Swing Stop Loss และ Target
    stop_loss = round(max(price - (atr * 1.5), price * 0.94), 2)
    risk_per_share = price - stop_loss
    target_1 = round(price + (risk_per_share * 1.5), 2)
    target_2 = round(price + (risk_per_share * 2.5), 2)
    rr_ratio = round((target_1 - price) / (risk_per_share + 1e-9), 1)

    return {
        "symbol": symbol,
        "display_symbol": disp_sym,
        "market_tag": market_tag,
        "currency": curr_sym,
        "price": price,
        "change_pct": change_pct,
        "signal": signal,
        "setup": setup_found,
        "score": score,
        "reason": " \n".join(reason),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "rsi": round(rsi, 1),
        "vol_ratio": round(vol_ratio, 2),
        "atr": round(atr, 2),
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "rr_ratio": rr_ratio,
        "df": df
    }

def scan_watchlist(symbols: Optional[List[str]] = None, *args, **kwargs) -> List[Dict[str, Any]]:
    """สแกนหุ้นใน Watchlist ทั้งหมดและจัดอันดับความน่าสนใจ (กรองตลาด TH / US ได้)"""
    market_filter = kwargs.get("market_filter", args[0] if len(args) > 0 else "ALL")
    if symbols is None:
        symbols = get_watchlist(market=market_filter if market_filter in ["TH", "US"] else None)

    results = []
    for sym in symbols:
        df = fetch_stock_data(sym)
        if df is not None:
            df = calculate_indicators(df)
            analysis = evaluate_swing_setup(sym, df)
            results.append(analysis)

    # เรียงลำดับคะแนนจากสูงไปต่ำ (BUY นำหน้า)
    results.sort(key=lambda x: (x["signal"] == "BUY", x["score"]), reverse=True)
    return results
