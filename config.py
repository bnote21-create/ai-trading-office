import os
import sys
import warnings
from pathlib import Path
from dotenv import load_dotenv

# ปิด Warning ที่ไม่จำเป็นจากภายนอก
warnings.filterwarnings('ignore')

# ป้องกันปัญหา UnicodeEncodeError เมื่อพิมพ์ Emoji/ภาษาไทย บน Windows Console
if sys.platform.startswith("win"):
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# โหลดตัวแปรสภาพแวดล้อมจาก .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ตัวช่วยอ่านค่า Config รองรับทั้งไฟล์ .env และ st.secrets (บน Streamlit Community Cloud)
def get_config_var(key: str, default: str = "") -> str:
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default

# --- ข้อมูลการตั้งค่าระบบ AI Trading Office ---
APP_NAME = "AI Trading Office (Thai & US Stock Desk)"
VERSION = "2.0.0"

# กุญแจ API ต่างๆ (ดึงจาก .env หรือ st.secrets)
GEMINI_API_KEY = get_config_var("GEMINI_API_KEY", "")
LINE_NOTIFY_TOKEN = get_config_var("LINE_NOTIFY_TOKEN", "")
LINE_CHANNEL_ACCESS_TOKEN = get_config_var("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = get_config_var("LINE_USER_ID", "")
TELEGRAM_BOT_TOKEN = get_config_var("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = get_config_var("TELEGRAM_CHAT_ID", "")

# ฐานข้อมูล SQLite
DB_PATH = BASE_DIR / "trading_office.db"

# รายการหุ้นไทยยอดนิยมสำหรับ Swing Trade (SET50 / SET100)
DEFAULT_WATCHLIST_TH = [
    "DELTA.BK", "PTT.BK", "CPALL.BK", "AOT.BK", "KBANK.BK",
    "SCB.BK", "BDMS.BK", "GULF.BK", "ADVANC.BK", "TRUE.BK",
    "KTB.BK", "BBL.BK", "CPN.BK", "MINT.BK"
]

# รายการหุ้นสหรัฐฯ ยอดนิยมสำหรับ Swing Trade (Big Tech & Growth)
DEFAULT_WATCHLIST_US = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN",
    "META", "TSLA", "AMD", "AVGO", "PLTR",
    "SPY", "QQQ"
]

DEFAULT_WATCHLIST = DEFAULT_WATCHLIST_TH + DEFAULT_WATCHLIST_US

# Helper ฟังก์ชันสำหรับการจัดการชื่อย่อหุ้นและสกุลเงิน (ไทย vs สหรัฐฯ)
def is_thai_stock(symbol: str) -> bool:
    s = symbol.strip().upper()
    return s.endswith(".BK") or s == "^SET" or s in [x.replace(".BK", "") for x in DEFAULT_WATCHLIST_TH]

def normalize_symbol(symbol: str, market: str = "AUTO") -> str:
    """แปลงชื่อย่อหุ้นให้พร้อมดึงข้อมูลจาก Yahoo Finance"""
    s = symbol.strip().upper()
    if market == "TH" or (market == "AUTO" and is_thai_stock(s)):
        if s.startswith("^"):
            return s if s.endswith(".BK") else f"{s}.BK"
        return s if s.endswith(".BK") else f"{s}.BK"
    elif market == "US":
        return s.replace(".BK", "")
    return s

def clean_display_symbol(symbol: str) -> str:
    """ชื่อย่อหุ้นสำหรับแสดงผลบนหน้าจอ UI แบบอ่านง่าย"""
    s = symbol.strip().upper()
    return s.replace(".BK", "")

def get_currency_symbol(symbol: str) -> str:
    return "฿" if is_thai_stock(symbol) else "$"

def get_market_tag(symbol: str) -> str:
    return "🇹🇭 หุ้นไทย" if is_thai_stock(symbol) else "🇺🇸 หุ้นสหรัฐฯ"

# พารามิเตอร์สำหรับ Swing Trading Setup (Timeframe Daily)
SWING_CONFIG = {
    "ema_fast": 20,       # EMA 20 เส้นค่าเฉลี่ยระยะสั้น
    "ema_slow": 50,       # EMA 50 เส้นแนวโน้มหลักของ Swing Trader
    "ema_trend": 200,     # EMA 200 แนวโน้มภาพใหญ่ขาขึ้น/ขาลง
    "rsi_period": 14,
    "rsi_oversold": 40,   # โซน Pullback ในขาขึ้น (35-45)
    "rsi_overbought": 70, # โซนตึงตัว ควรระวังหรือแบ่งล็อกกำไร
    "default_stop_loss_pct": 5.0,  # จุดตัดขาดทุนมาตรฐาน 5% (หรือ Swing Low)
    "min_risk_reward_ratio": 2.0,  # อัตราผลตอบแทนต่อความเสี่ยงขั้นต่ำ 1:2
    "trailing_stop_activation_pct": 8.0, # เมื่อกำไรเกิน 8% ให้เริ่มขยับ Trailing Stop
    "trailing_stop_distance_pct": 4.0    # ให้ราคาถอยได้ไม่เกิน 4% จากจุดสูงสุดใหม่
}
