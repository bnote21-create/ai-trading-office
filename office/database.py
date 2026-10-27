import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import (
    DB_PATH, 
    DEFAULT_WATCHLIST_TH, 
    DEFAULT_WATCHLIST_US,
    is_thai_stock,
    normalize_symbol
)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """สร้างตารางฐานข้อมูลหากยังไม่มี และอัปเกรด Schema เพื่อรองรับตลาดหุ้นไทยและสหรัฐฯ"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # ตารางพอร์ตโฟลิโอ (รองรับทั้งหุ้นไทยและหุ้นสหรัฐฯ)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                shares REAL NOT NULL,
                cost_price REAL NOT NULL,
                buy_date TEXT NOT NULL,
                stop_loss_price REAL,
                target_price_1 REAL,
                target_price_2 REAL,
                highest_price REAL,
                notes TEXT,
                status TEXT DEFAULT 'HOLDING',
                close_price REAL,
                close_date TEXT,
                realized_pnl REAL,
                market TEXT DEFAULT 'US'
            )
        ''')

        # ตรวจสอบและเพิ่มคอลัมน์ market, last_alert_code, last_alert_time หากยังไม่มี
        cursor.execute("PRAGMA table_info(portfolio)")
        columns = [col[1] for col in cursor.fetchall()]
        if "market" not in columns:
            try:
                cursor.execute("ALTER TABLE portfolio ADD COLUMN market TEXT DEFAULT 'US'")
            except Exception:
                pass
        if "last_alert_code" not in columns:
            try:
                cursor.execute("ALTER TABLE portfolio ADD COLUMN last_alert_code TEXT DEFAULT ''")
            except Exception:
                pass
        if "last_alert_time" not in columns:
            try:
                cursor.execute("ALTER TABLE portfolio ADD COLUMN last_alert_time TEXT DEFAULT ''")
            except Exception:
                pass

        # ตาราง Watchlist หุ้นที่ให้ AI จับตาดู
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                category TEXT DEFAULT 'Swing',
                added_date TEXT NOT NULL
            )
        ''')

        # ตารางประวัติการแจ้งเตือน
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                sent_to_line INTEGER DEFAULT 0
            )
        ''')

        # ใส่ Default Watchlist หุ้นไทย (SET50) และหุ้นสหรัฐฯ
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for sym in DEFAULT_WATCHLIST_TH:
            cursor.execute(
                "INSERT OR IGNORE INTO watchlist (symbol, category, added_date) VALUES (?, ?, ?)",
                (sym, "TH", now_str)
            )
        for sym in DEFAULT_WATCHLIST_US:
            cursor.execute(
                "INSERT OR IGNORE INTO watchlist (symbol, category, added_date) VALUES (?, ?, ?)",
                (sym, "US", now_str)
            )

        conn.commit()

# --- Functions จัดการ Portfolio ---

def add_holding(symbol: str, shares: float, cost_price: float, 
                stop_loss: Optional[float] = None, 
                target_1: Optional[float] = None, 
                target_2: Optional[float] = None, 
                notes: str = "",
                *args, **kwargs) -> int:
    """เพิ่มหุ้นที่ซื้อเข้าสู่ระบบบันทึกพอร์ต (รองรับทั้งหุ้นไทยและสหรัฐฯ)"""
    market = kwargs.get("market", args[0] if len(args) > 0 else None)
    symbol = symbol.strip().upper()
    
    if market is None or market == "AUTO":
        market = "TH" if is_thai_stock(symbol) else "US"

    symbol = normalize_symbol(symbol, market)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    highest = cost_price

    # ค่าเริ่มต้น Stop loss 5% และ Target 10%, 15% หากไม่ได้ระบุ
    if stop_loss is None or stop_loss <= 0:
        stop_loss = round(cost_price * 0.95, 2)
    if target_1 is None or target_1 <= 0:
        target_1 = round(cost_price * 1.10, 2)
    if target_2 is None or target_2 <= 0:
        target_2 = round(cost_price * 1.15, 2)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfolio 
            (symbol, shares, cost_price, buy_date, stop_loss_price, target_price_1, target_price_2, highest_price, notes, status, market)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'HOLDING', ?)
        ''', (symbol, shares, cost_price, now_str, stop_loss, target_1, target_2, highest, notes, market))
        conn.commit()
        return cursor.lastrowid

def get_active_holdings(market_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """ดึงรายการหุ้นที่กำลังถืออยู่ทั้งหมด (Status: HOLDING) พร้อมตัวกรองตลาด"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if market_filter in ["TH", "US"]:
            cursor.execute("SELECT * FROM portfolio WHERE status = 'HOLDING' AND market = ? ORDER BY id DESC", (market_filter,))
        else:
            cursor.execute("SELECT * FROM portfolio WHERE status = 'HOLDING' ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def update_holding_highest_price(holding_id: int, new_highest: float):
    """อัปเดตราคาสูงสุดตั้งแต่ถือ สำหรับคำนวณ Trailing Stop"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE portfolio SET highest_price = ? WHERE id = ?", (new_highest, holding_id))
        conn.commit()

def update_holding_alert_state(holding_id: int, alert_code: str):
    """บันทึกสถานะการแจ้งเตือนล่าสุด เพื่อป้องกันการแจ้งเตือนซ้ำซ้อนทุกนาที"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE portfolio SET last_alert_code = ?, last_alert_time = ? WHERE id = ?", (alert_code, now_str, holding_id))
        conn.commit()

def close_holding(holding_id: int, close_price: float, notes: str = ""):
    """บันทึกการขายหุ้นออกจากพอร์ต"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT shares, cost_price FROM portfolio WHERE id = ?", (holding_id,))
        row = cursor.fetchone()
        if not row:
            return
        shares, cost = row["shares"], row["cost_price"]
        pnl = (close_price - cost) * shares

        cursor.execute('''
            UPDATE portfolio 
            SET status = 'CLOSED', close_price = ?, close_date = ?, realized_pnl = ?, notes = notes || ' | ' || ?
            WHERE id = ?
        ''', (close_price, now_str, pnl, notes, holding_id))
        conn.commit()

def delete_holding(holding_id: int):
    """ลบรายการหุ้น"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolio WHERE id = ?", (holding_id,))
        conn.commit()

# --- Functions จัดการ Watchlist ---

def get_watchlist(*args, **kwargs) -> List[str]:
    """ดึงรายชื่อหุ้นใน Watchlist (สามารถกรองตามตลาด TH / US ได้)"""
    market = kwargs.get("market", args[0] if len(args) > 0 else None)
    with get_connection() as conn:
        cursor = conn.cursor()
        if market == "TH":
            cursor.execute("SELECT symbol FROM watchlist WHERE category = 'TH' OR symbol LIKE '%.BK' ORDER BY symbol ASC")
        elif market == "US":
            cursor.execute("SELECT symbol FROM watchlist WHERE category = 'US' AND symbol NOT LIKE '%.BK' ORDER BY symbol ASC")
        else:
            cursor.execute("SELECT symbol FROM watchlist ORDER BY symbol ASC")
        return [row["symbol"] for row in cursor.fetchall()]

def add_to_watchlist(symbol: str, *args, **kwargs):
    category = kwargs.get("category", args[0] if len(args) > 0 else None)
    symbol = symbol.strip().upper()
    if category is None or category == "AUTO":
        category = "TH" if is_thai_stock(symbol) else "US"
    
    symbol = normalize_symbol(symbol, category)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO watchlist (symbol, category, added_date) VALUES (?, ?, ?)",
            (symbol, category, now_str)
        )
        conn.commit()

def remove_from_watchlist(symbol: str):
    s = symbol.strip().upper()
    s_bk = f"{s}.BK" if not s.endswith(".BK") else s
    s_raw = s.replace(".BK", "")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE symbol = ? OR symbol = ?", (s_raw, s_bk))
        conn.commit()

# --- Functions บันทึก Alert Log ---

def log_alert(symbol: str, alert_type: str, message: str, sent_to_line: bool = False):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts_history (timestamp, symbol, alert_type, message, sent_to_line)
            VALUES (?, ?, ?, ?, ?)
        ''', (now_str, symbol, alert_type, message, 1 if sent_to_line else 0))
        conn.commit()

def get_recent_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts_history ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

# สั่งเริ่มต้นฐานข้อมูลทันทีที่โหลดโมดูล
init_db()
