import sys
import importlib
import streamlit as st
import pandas as pd
from datetime import datetime
import config

# รีโหลดโมดูลภายใน office เสมอเพื่อป้องกันแคชค้างเมื่ออัปเดตระบบ
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("office"):
        try:
            importlib.reload(sys.modules[mod_name])
        except Exception:
            pass

from office.database import (
    get_active_holdings, add_holding, close_holding, delete_holding,
    get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_recent_alerts
)
from office.market_scout import scan_watchlist, fetch_stock_data, calculate_indicators, evaluate_swing_setup
from office.portfolio_guardian import inspect_portfolio, get_portfolio_summary, fetch_latest_price
from office.analyst import analyze_stock
from office.chart_helper import create_stock_chart
from office.notifier import send_line_message, send_telegram_message, broadcast_alert
from office.ai_chat import generate_ai_chat_reply, save_gemini_api_key, test_gemini_key

try:
    from office.auto_guardian import (
        start_guardian, stop_guardian, get_guardian_status, set_guardian_interval
    )
except (ImportError, AttributeError):
    import office.auto_guardian as _ag
    importlib.reload(_ag)
    start_guardian = getattr(_ag, "start_guardian", lambda *a, **k: True)
    stop_guardian = getattr(_ag, "stop_guardian", lambda *a, **k: False)
    get_guardian_status = getattr(_ag, "get_guardian_status", lambda: {"is_running": False, "interval_seconds": 60, "last_check_time": None, "check_count": 0, "last_log": ""})
    set_guardian_interval = getattr(_ag, "set_guardian_interval", lambda sec: None)

# เริ่มต้นระบบเฝ้าพอร์ตเรียลไทม์อัตโนมัติ (ตรวจราคาและยิง Alert Stop Loss / Take Profit ทุก 60 วินาที)
start_guardian(interval_seconds=60)

# กำหนดค่าหน้าเว็บ Streamlit
st.set_page_config(
    page_title="AI Trading Office - Thai & US Stock Desk",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #90A4AE;
        margin-bottom: 1.2rem;
    }
    .badge-th { background-color: #0277bd; color: white; padding: 3px 7px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
    .badge-us { background-color: #6a1b9a; color: white; padding: 3px 7px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ส่วนหัวของแอป
st.markdown('<div class="main-header">🏛️ AI Trading Office (Thai & US Stock Desk)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">สำนักงาน AI ส่วนตัวสำหรับดูแลพอร์ตหุ้นไทย (SET) & หุ้นสหรัฐฯ (US) • สแกนหาหุ้นน่าซื้อ • เฝ้าระวังและเตือนจุดขาย</div>', unsafe_allow_html=True)

# Sidebar: เมนูและตัวกรองตลาด
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=400&q=80", use_container_width=True)
    st.title("ห้องสั่งการ AI Office")
    
    menu = st.radio(
        "เลือกแผนกงาน:",
        [
            "📊 1. ภาพรวมพอร์ต & ตลาด (Overview)",
            "🛡️ 2. ผู้จัดการพอร์ต (Portfolio Guardian)",
            "🔭 3. แมวมองสแกนหุ้น (Market Scout)",
            "🧠 4. วิเคราะห์หุ้นรายตัว (AI Deep Dive)",
            "💬 5. แชทปรึกษา AI Office (AI Chat Advisor)",
            "⚙️ 6. ตั้งค่า & คู่มือ (Settings & Guide)"
        ]
    )
    
    st.divider()
    
    # ตัวกรองตลาดหลัก
    st.subheader("🌐 ตัวกรองตลาด")
    market_filter = st.selectbox(
        "เลือกตลาดที่ต้องการดู:",
        ["🌐 ทั้งหมด (All Markets)", "🇹🇭 หุ้นไทย (SET)", "🇺🇸 หุ้นสหรัฐฯ (US)"],
        index=0
    )
    market_code = "ALL" if "ทั้งหมด" in market_filter else ("TH" if "หุ้นไทย" in market_filter else "US")

    st.divider()

    # ส่วนทดสอบการแจ้งเตือน
    st.subheader("🔔 การแจ้งเตือน (LINE & Telegram)")
    t_col1, t_col2 = st.columns(2)
    with t_col1:
        if st.button("ทดสอบ Telegram"):
            res = send_telegram_message("🔔 [AI Office] ทดสอบส่งเข้า Telegram สำเร็จ! ระบบพร้อมส่งสัญญาณเทรดหุ้นไทย & สหรัฐฯ ให้คุณแล้วครับ")
            ok, msg = res if isinstance(res, tuple) else (res, "ส่งเข้า Telegram สำเร็จ!" if res else "ส่งไม่สำเร็จ")
            if ok:
                st.success(msg)
            else:
                st.warning(msg)

    with t_col2:
        if st.button("ทดสอบ LINE"):
            res = send_line_message("🔔 [AI Office] ทดสอบส่งเข้า LINE สำเร็จ! พร้อมดูแลพอร์ตหุ้นไทย & สหรัฐฯ ของคุณครับ")
            ok, msg = res if isinstance(res, tuple) else (res, "ส่งเข้า LINE สำเร็จเรียบร้อยแล้ว!" if res else "ส่งไม่สำเร็จ")
            if ok:
                st.success(msg)
            else:
                st.warning(msg)

    st.divider()

    # แสดงสถานะระบบเฝ้าพอร์ตเรียลไทม์อัตโนมัติ (Auto Guardian)
    g_side_stat = get_guardian_status()
    st.subheader("🤖 AI Auto-Guardian")
    if g_side_stat["is_running"]:
        st.success(f"🟢 **เฝ้าพอร์ตอัตโนมัติ (ทุก {g_side_stat['interval_seconds']} วินาที)**\n\nพร้อมเตือน TP/SL เข้า LINE & Telegram ทันที")
        st.caption(f"เช็คล่าสุด: {g_side_stat['last_check_time'] or 'กำลังเริ่มตรวจรอบแรก...'}")
    else:
        st.warning("⏸️ ระบบเฝ้าพอร์ตหยุดทำงานชั่วคราว")

# ==========================================
# แผนก 1: ภาพรวมพอร์ต & ตลาด (Overview)
# ==========================================
if "1. ภาพรวมพอร์ต" in menu:
    st.subheader("📊 ภาพรวมพอร์ตและการเคลื่อนไหวดัชนีตลาดหุ้น")
    
    with st.spinner("กำลังดึงราคาล่าสุดของหุ้นในพอร์ต..."):
        evaluated_holdings = inspect_portfolio(send_alerts=False)
        summary = get_portfolio_summary(evaluated_holdings)

    # การแสดงยอดแยกตลาด ไทย ฿ vs สหรัฐฯ $
    th_val = summary.get('th_value', 0.0)
    th_pnl = summary.get('th_pnl', 0.0)
    th_pnl_pct = summary.get('th_pnl_pct', 0.0)
    th_cost = summary.get('th_cost', 0.0)
    th_pos = summary.get('th_positions', 0)

    us_val = summary.get('us_value', summary.get('total_value', 0.0))
    us_pnl = summary.get('us_pnl', summary.get('total_pnl_usd', 0.0))
    us_pnl_pct = summary.get('us_pnl_pct', summary.get('total_pnl_pct', 0.0))
    us_cost = summary.get('us_cost', summary.get('total_cost', 0.0))
    us_pos = summary.get('us_positions', summary.get('total_positions', 0))

    tot_pos = summary.get('total_positions', th_pos + us_pos)
    win_count = summary.get('winning_count', 0)
    loss_count = summary.get('losing_count', 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "🇹🇭 มูลค่าหุ้นไทย (THB)", 
            f"฿{th_val:,.2f}", 
            delta=f"{th_pnl:+,.2f} ({th_pnl_pct:+.2f}%)" if th_cost > 0 else None
        )
        st.caption(f"ถืออยู่ {th_pos} ตัว (ต้นทุน ฿{th_cost:,.2f})")
    with col2:
        st.metric(
            "🇺🇸 มูลค่าหุ้นสหรัฐฯ (USD)", 
            f"${us_val:,.2f}", 
            delta=f"${us_pnl:+,.2f} ({us_pnl_pct:+.2f}%)" if us_cost > 0 else None
        )
        st.caption(f"ถืออยู่ {us_pos} ตัว (ต้นทุน ${us_cost:,.2f})")
    with col3:
        st.metric("จำนวนหุ้นทั้งหมดในพอร์ต", f"{tot_pos} ตัว")
    with col4:
        st.metric("สถิติกำไร / ขาดทุน", f"🟢 {win_count} / 🔴 {loss_count}")

    st.divider()
    
    # ดัชนีตลาดสำคัญ (SET, S&P 500, NASDAQ, Dow Jones)
    st.markdown("#### 🌐 ทิศทางดัชนีหลักตลาดหุ้น (ไทย & สหรัฐฯ)")
    
    @st.cache_data(ttl=120, show_spinner=False)
    def fetch_major_indices():
        import yfinance as yf
        target_indices = [
            {"symbol": "^SET.BK", "name": "🇹🇭 SET Index (หุ้นไทย)", "market": "TH", "desc": "ดัชนีตลาดหลักทรัพย์แห่งประเทศไทย", "curr": "฿"},
            {"symbol": "SPY", "name": "🇺🇸 S&P 500 (SPY)", "market": "US", "desc": "หุ้นใหญ่ 500 บริษัทสหรัฐฯ", "curr": "$"},
            {"symbol": "QQQ", "name": "🇺🇸 NASDAQ 100 (QQQ)", "market": "US", "desc": "หุ้นกลุ่มเทคโนโลยีชั้นนำโลก", "curr": "$"},
            {"symbol": "DIA", "name": "🇺🇸 Dow Jones (DIA)", "market": "US", "desc": "หุ้นอุตสาหกรรมขนาดใหญ่", "curr": "$"}
        ]
        results = []
        for item in target_indices:
            sym = item["symbol"]
            curr_price = None
            prev_price = None
            try:
                t = yf.Ticker(sym)
                if hasattr(t, "fast_info"):
                    curr_price = getattr(t.fast_info, "last_price", None)
                    prev_price = getattr(t.fast_info, "previous_close", None)
                if curr_price is None or prev_price is None or curr_price <= 0:
                    hist = t.history(period="5d", interval="1d")
                    if hist is not None and not hist.empty:
                        curr_price = float(hist["Close"].iloc[-1])
                        prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else curr_price
            except Exception:
                pass
            
            if curr_price is not None and curr_price > 0:
                prev_price = prev_price if (prev_price is not None and prev_price > 0) else curr_price
                chg = ((curr_price - prev_price) / prev_price) * 100
                diff = curr_price - prev_price
                results.append({
                    "symbol": sym,
                    "name": item["name"],
                    "market": item["market"],
                    "desc": item["desc"],
                    "curr": item["curr"],
                    "price": float(curr_price),
                    "diff": float(diff),
                    "change_pct": float(chg)
                })
        return results

    indices_list = fetch_major_indices()

    if market_code == "TH":
        active_indices = [idx for idx in indices_list if idx["market"] == "TH"]
    elif market_code == "US":
        active_indices = [idx for idx in indices_list if idx["market"] == "US"]
    else:
        active_indices = indices_list

    if active_indices:
        cols = st.columns(len(active_indices))
        for col, idx in zip(cols, active_indices):
            with col:
                st.metric(
                    idx["name"], 
                    f"{idx['curr']}{idx['price']:,.2f}", 
                    delta=f"{idx['diff']:+,.2f} ({idx['change_pct']:+.2f}%)"
                )
                st.caption(idx["desc"])
    else:
        st.info("💡 กำลังดึงข้อมูลดัชนีตลาดหุ้น... กรุณากด Rerun หรือรอสักครู่")

    st.divider()
    # ประวัติแจ้งเตือน
    st.markdown("#### 📢 ประวัติสัญญาณและการแจ้งเตือนล่าสุดของ AI Office")
    alerts = get_recent_alerts(limit=5)
    if alerts:
        for a in alerts:
            with st.container():
                st.markdown(f"**[{a['timestamp']}] {config.clean_display_symbol(a['symbol'])} - {a['alert_type']}**")
                st.info(a['message'])
    else:
        st.caption("ยังไม่มีประวัติการแจ้งเตือน ระบบจะบันทึกเมื่อมีสัญญาณซื้อ-ขายเกิดขึ้น")

# ==========================================
# แผนก 2: ผู้จัดการพอร์ต (Portfolio Guardian)
# ==========================================
elif "2. ผู้จัดการพอร์ต" in menu:
    st.subheader("🛡️ ผู้จัดการพอร์ตหุ้น (Portfolio Guardian & Sell Advisor)")
    st.write("บันทึกหุ้นที่คุณซื้อ (ทั้งหุ้นไทย SET และหุ้นสหรัฐฯ) เพื่อให้ AI ช่วยเฝ้าจุด **'Take Profit'** หรือ **'Cut Loss'**")

    # ฟอร์มเพิ่มหุ้นแบบอัจฉริยะ (คำนวณราคาและจุดตัดขาดทุนให้อัตโนมัติจากราคาตลาดจริง)
    with st.expander("➕ เพิ่มหุ้นที่คุณเพิ่งซื้อ (ระบบดึงราคาจริง & คำนวณค่าต่างๆ ให้อัตโนมัติ)", expanded=True):
        m_col1, m_col2, m_col3 = st.columns([2, 3, 2])
        with m_col1:
            sel_market_radio = st.radio("เลือกตลาดของหุ้น:", ["🇺🇸 หุ้นสหรัฐฯ (US)", "🇹🇭 หุ้นไทย (SET)"], horizontal=True, key="add_mkt_radio")
            sel_market = "US" if "สหรัฐฯ" in sel_market_radio else "TH"
            curr_sym = "$" if sel_market == "US" else "฿"
            curr_name = "USD" if sel_market == "US" else "บาท"

        with m_col2:
            placeholder_sym = "เช่น ARM, NVDA, TSLA, AAPL" if sel_market == "US" else "เช่น PTT, DELTA, CPALL, BDMS"
            in_symbol = st.text_input(
                "ชื่อย่อหุ้น (พิมพ์ชื่อแล้วกด Enter หรือกดปุ่มด้านขวาเพื่อดึงราคา):",
                placeholder=placeholder_sym,
                key="input_stock_sym"
            ).strip().upper()

        with m_col3:
            st.write("")
            st.write("")
            st.button("⚡ ดึงราคาและคำนวณใหม่", key="btn_fetch_realtime")

        # ตรวจสอบและดึงราคาตลาดจริงทันที
        market_price = 0.0
        if in_symbol:
            norm_sym = config.normalize_symbol(in_symbol, sel_market)
            with st.spinner(f"กำลังดึงราคาตลาดล่าสุดของ {config.clean_display_symbol(norm_sym)}..."):
                market_price = fetch_latest_price(norm_sym)
            
            if market_price > 0:
                calc_cost = market_price
                calc_sl = round(calc_cost * 0.95, 2)
                calc_tp1 = round(calc_cost * 1.10, 2)
                calc_tp2 = round(calc_cost * 1.18, 2)
                st.success(
                    f"✅ **พบราคาตลาดล่าสุดของ {config.clean_display_symbol(norm_sym)}: {curr_sym}{market_price:,.2f}** "
                    f"| ระบบคำนวณต้นทุน, Stop Loss ({curr_sym}{calc_sl:.2f}), TP1 ({curr_sym}{calc_tp1:.2f}), TP2 ({curr_sym}{calc_tp2:.2f}) ให้เรียบร้อยแล้วด้านล่าง"
                )
            else:
                st.warning(f"⚠️ ไม่พบราคาของหุ้น {in_symbol} ในตลาด {sel_market} (กรุณาตรวจตัวสะกด)")
                calc_cost = 100.0 if sel_market == "US" else 50.0
                calc_sl = round(calc_cost * 0.95, 2)
                calc_tp1 = round(calc_cost * 1.10, 2)
                calc_tp2 = round(calc_cost * 1.18, 2)
        else:
            calc_cost = 100.0 if sel_market == "US" else 50.0
            calc_sl = round(calc_cost * 0.95, 2)
            calc_tp1 = round(calc_cost * 1.10, 2)
            calc_tp2 = round(calc_cost * 1.18, 2)

        # ฟอร์มยืนยันและแก้ไขค่าจริงก่อนบันทึก
        with st.form("add_stock_form"):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                default_shares = 1.0 if sel_market == "US" else 100.0
                in_shares = st.number_input(
                    "จำนวนหุ้นที่ซื้อ:", 
                    min_value=0.001, 
                    value=default_shares, 
                    step=1.0 if sel_market == "TH" else 0.1
                )
            with f_col2:
                in_cost = st.number_input(
                    f"ราคาต้นทุนเฉลี่ยต่อหุ้น ({curr_sym} {curr_name}):", 
                    min_value=0.01, 
                    value=float(calc_cost), 
                    step=0.25 if sel_market == "TH" else 0.5
                )
            with f_col3:
                in_sl = st.number_input(
                    f"จุดตัดขาดทุน Stop Loss ({curr_sym}) [แนะนำ -5%]:", 
                    value=float(calc_sl), 
                    step=0.25 if sel_market == "TH" else 0.5
                )

            f_col4, f_col5 = st.columns(2)
            with f_col4:
                in_tp1 = st.number_input(
                    f"เป้ากำไร 1 Take Profit ({curr_sym}) [แนะนำ +10%]:", 
                    value=float(calc_tp1), 
                    step=0.25 if sel_market == "TH" else 0.5
                )
            with f_col5:
                in_tp2 = st.number_input(
                    f"เป้ากำไร 2 Take Profit ({curr_sym}) [แนะนำ +18%]:", 
                    value=float(calc_tp2), 
                    step=0.25 if sel_market == "TH" else 0.5
                )

            in_notes = st.text_input("บันทึกช่วยจำ (เช่น ซื้อสะสม / เบรกเอาท์):", value="")
            submit_btn = st.form_submit_button("💾 บันทึกหุ้นเข้าพอร์ต", type="primary")

            if submit_btn:
                if not in_symbol:
                    st.error("กรุณากรอกชื่อย่อหุ้นก่อนกดบันทึก")
                else:
                    norm_sym = config.normalize_symbol(in_symbol, sel_market)
                    add_holding(norm_sym, in_shares, in_cost, in_sl, in_tp1, in_tp2, in_notes, market=sel_market)
                    st.success(f"บันทึกหุ้น {config.clean_display_symbol(norm_sym)} ({in_shares} หุ้น ที่ต้นทุน {curr_sym}{in_cost:.2f}) เข้าพอร์ตเรียบร้อยแล้ว!")
                    st.rerun()

    # แผงควบคุมระบบเฝ้าพอร์ตและแจ้งเตือนอัตโนมัติ (AI Auto-Guardian)
    g_info = get_guardian_status()
    with st.container():
        st.markdown("#### 🤖 ระบบเฝ้าพอร์ต & ส่งแจ้งเตือนอัตโนมัติ (Real-time Auto-Guardian)")
        
        if g_info["is_running"]:
            st.success(
                f"🟢 **ระบบกำลังเฝ้าพอร์ตอัตโนมัติ (ตรวจราคาทุก {g_info['interval_seconds']} วินาที)**\n\n"
                f"✨ **เมื่อราคาแตะจุด Stop Loss (ตัดขาดทุน) หรือ Take Profit (ทำกำไร) ระบบจะส่งข้อความแจ้งเตือนเข้า LINE และ Telegram ทันทีโดยที่คุณไม่ต้องกดตรวจสอบเอง!**\n\n"
                f"• ตรวจสอบล่าสุด: `{g_info['last_check_time'] or 'เพิ่งเริ่มต้นระบบ (กำลังตรวจรอบแรก)...'}` "
                f"| ตรวจสอบไปแล้ว: `{g_info['check_count']}` ครั้ง "
                f"| สถานะ: `{g_info['last_log']}`"
            )
        else:
            st.warning("⏸️ ระบบเฝ้าพอร์ตอัตโนมัติถูกหยุดชั่วคราว (คุณสามารถกดปุ่ม '▶️ เริ่มเฝ้าพอร์ตต่อ' ด้านล่างเพื่อเปิดใช้งาน)")

        g_col1, g_col2, g_col3 = st.columns([3, 4, 3])
        with g_col1:
            if g_info["is_running"]:
                if st.button("⏸️ หยุดเฝ้าพอร์ตชั่วคราว", key="btn_stop_guardian"):
                    stop_guardian()
                    st.rerun()
            else:
                if st.button("▶️ เริ่มเฝ้าพอร์ตอัตโนมัติ", type="primary", key="btn_start_guardian"):
                    start_guardian(60)
                    st.rerun()

        with g_col2:
            if st.button("🔄 ตรวจสอบราคาเดี๋ยวนี้ (Manual Check)", key="btn_manual_inspect"):
                with st.spinner("AI กำลังตรวจราคาและประเมินสัญญาณขาย..."):
                    holdings_evaluated = inspect_portfolio(send_alerts=True)
                    st.success("ตรวจเช็คและส่งแจ้งเตือน (LINE/Telegram) เรียบร้อย!")
                    st.rerun()

        with g_col3:
            cur_interval = g_info.get("interval_seconds", 60)
            int_options = [30, 60, 120, 300]
            int_index = int_options.index(cur_interval) if cur_interval in int_options else 1
            sel_int = st.selectbox(
                "ความถี่ในการตรวจราคา:",
                int_options,
                index=int_index,
                format_func=lambda x: f"ทุก {x} วินาที" if x < 60 else f"ทุก {x//60} นาที",
                key="sel_guardian_interval"
            )
            if sel_int != cur_interval:
                set_guardian_interval(sel_int)
                st.rerun()

    st.markdown("---")

    # แสดงรายการหุ้นในพอร์ต (รองรับการกรองตลาด)
    all_holdings = inspect_portfolio(send_alerts=False)
    if market_code == "TH":
        holdings = [h for h in all_holdings if h.get("is_thai") or str(h.get("symbol", "")).endswith(".BK")]
    elif market_code == "US":
        holdings = [h for h in all_holdings if not h.get("is_thai") and not str(h.get("symbol", "")).endswith(".BK")]
    else:
        holdings = all_holdings
    
    if not holdings:
        st.info("💡 ขณะนี้ยังไม่มีหุ้นในพอร์ต (สำหรับมุมมองที่เลือก) กดปุ่ม '➕ เพิ่มหุ้นที่คุณเพิ่งซื้อ' ด้านบนเพื่อเริ่มต้นใช้งาน")
    else:
        st.markdown(f"#### 📋 รายการหุ้นที่ถืออยู่ ({len(holdings)} รายการ):")
        for h in holdings:
            with st.container():
                pnl_color = "green" if h.get("pnl_pct", 0) >= 0 else "red"
                sign = "+" if h.get("pnl_pct", 0) >= 0 else ""
                curr = h.get("currency", "฿" if str(h.get("symbol", "")).endswith(".BK") else "$")
                disp_sym = h.get("display_symbol", str(h.get("symbol", "")).replace(".BK", ""))
                m_tag = h.get("market_tag", "🇹🇭 หุ้นไทย" if curr == "฿" else "🇺🇸 หุ้นสหรัฐฯ")
                pnl_val = h.get("pnl_amount", h.get("pnl_usd", 0.0))
                is_th = h.get("is_thai", curr == "฿")
                
                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 4, 2])
                with c1:
                    m_badge = "badge-th" if is_th else "badge-us"
                    st.markdown(f"<span class='{m_badge}'>{m_tag}</span>", unsafe_allow_html=True)
                    st.markdown(f"### **{disp_sym}**")
                    st.caption(f"{h.get('shares', 0):,.1f} หุ้น | ทุน {curr}{h.get('cost_price', 0):.2f}")
                with c2:
                    st.markdown(f"**ราคาล่าสุด:** {curr}{h.get('current_price', 0):.2f}")
                    st.markdown(f"**PnL:** :{pnl_color}[{sign}{curr}{pnl_val:,.2f} ({sign}{h.get('pnl_pct', 0):.2f}%)]")
                with c3:
                    st.markdown(f"🛑 **SL:** {curr}{h.get('stop_loss_price', 0):.2f}")
                    st.markdown(f"🎯 **TP1:** {curr}{h.get('target_price_1', 0):.2f} | **TP2:** {curr}{h.get('target_price_2', 0):.2f}")
                with c4:
                    st.markdown(f"**คำแนะนำ AI:** {h.get('action_text', '-')}")
                    st.caption(h.get('advice', ''))
                with c5:
                    if st.button("ปิดออเดอร์/ขายแล้ว", key=f"close_{h['id']}"):
                        close_holding(h['id'], h.get('current_price', 0), "ปิดออเดอร์จาก Dashboard")
                        st.success(f"บันทึกการขาย {disp_sym} แล้ว")
                        st.rerun()
                    if st.button("ลบรายการ", key=f"del_{h['id']}"):
                        delete_holding(h['id'])
                        st.warning(f"ลบ {disp_sym} เรียบร้อย")
                        st.rerun()
                st.divider()

# ==========================================
# แผนก 3: แมวมองสแกนหุ้น (Market Scout)
# ==========================================
elif "3. แมวมองสแกนหุ้น" in menu:
    st.subheader("🔭 แผนกสแกนหาหุ้นน่าซื้อ (AI Swing Trade Scout)")
    st.write("สแกนหุ้นไทย (SET50/100) และหุ้นสหรัฐฯ ตามกลยุทธ์ Swing Trading (จับจังหวะ Pullback ใกล้ EMA และ Breakout)")

    col_s1, col_s2 = st.columns([3, 7])
    with col_s1:
        do_scan = st.button("🚀 เริ่มสแกนหาจังหวะซื้อตอนนี้", type="primary")

    if do_scan or "scout_results" in st.session_state:
        if do_scan:
            with st.spinner("ฝ่าย Market Scout กำลังวิเคราะห์กราฟหุ้นทั้งหมด..."):
                st.session_state["scout_results"] = scan_watchlist()

        results = st.session_state.get("scout_results", [])
        
        # กรองผลตาม market_code หากผู้ใช้สลับตัวกรอง
        if market_code == "TH":
            results = [r for r in results if config.is_thai_stock(r.get("symbol", ""))]
        elif market_code == "US":
            results = [r for r in results if not config.is_thai_stock(r.get("symbol", ""))]

        buy_candidates = [r for r in results if r.get("signal") == "BUY"]
        
        st.markdown(f"#### 🎯 พบหุ้นที่มีสัญญาณเข้าซื้อ (BUY): {len(buy_candidates)} ตัว")
        if buy_candidates:
            for b in buy_candidates:
                curr = b.get("currency", "฿" if str(b.get("symbol", "")).endswith(".BK") else "$")
                disp = b.get("display_symbol", str(b.get("symbol", "")).replace(".BK", ""))
                tag = b.get("market_tag", "🇹🇭 หุ้นไทย" if curr == "฿" else "🇺🇸 หุ้นสหรัฐฯ")
                
                with st.expander(f"🟢 **[{tag}] {disp}** | ราคา {curr}{b['price']:.2f} | กลยุทธ์: {b['setup']} | คะแนน {b['score']}/100", expanded=True):
                    sc1, sc2 = st.columns([1, 1])
                    with sc1:
                        st.markdown(f"**เหตุผลที่น่าสนใจ:**\n{b['reason']}")
                        st.markdown(f"- **จุดเข้าซื้อแนะนำ:** {curr}{b['price']:.2f}")
                        st.markdown(f"- **จุด Stop Loss:** {curr}{b['stop_loss']:.2f} (สำคัญมาก)")
                        st.markdown(f"- **เป้าหมายกำไร 1:** {curr}{b['target_1']:.2f} | **เป้าหมาย 2:** {curr}{b['target_2']:.2f}")
                        st.markdown(f"- **Risk/Reward Ratio:** 1:{b['rr_ratio']}")
                    with sc2:
                        fig = create_stock_chart(b['df'], b['symbol'], stop_loss=b['stop_loss'], target_1=b['target_1'], target_2=b['target_2'])
                        st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("ขณะนี้ยังไม่มีหุ้นใน Watchlist ที่เข้าเกณฑ์ Buy Setup อย่างสมบูรณ์ (รอตลาดสร้างจังหวะที่ได้เปรียบ)")

        st.divider()
        st.markdown("#### 📋 สรุปผลการสแกน Watchlist ทั้งหมด:")
        table_data = []
        for r in results:
            curr = r["currency"]
            table_data.append({
                "ตลาด": r["market_tag"],
                "หุ้น (Symbol)": r["display_symbol"],
                "ราคาล่าสุด": f"{curr}{r['price']:.2f}",
                "เปลี่ยนแปลงวันนี้": f"{r['change_pct']:+.2f}%",
                "สัญญาณ": r["signal"],
                "คะแนน": f"{r['score']}/100",
                "RSI 14": r["rsi"],
                "วอลุ่มเทียบเฉลี่ย": f"{r['vol_ratio']}x",
                "ทรงกราฟ/กลยุทธ์": r["setup"]
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)

# ==========================================
# แผนก 4: วิเคราะห์หุ้นรายตัวตามสั่ง (AI Deep Dive)
# ==========================================
elif "4. วิเคราะห์หุ้นรายตัว" in menu:
    st.subheader("🧠 แผนกวิเคราะห์หุ้นรายตัว (AI Stock Deep Dive)")
    st.write("พิมพ์ชื่อย่อหุ้นไทย (เช่น PTT, DELTA, CPALL) หรือหุ้นสหรัฐฯ (เช่น NVDA, TSLA, AAPL) AI จะนำข้อมูลมาวิเคราะห์และวางแผนเทรดให้คุณทันที")

    c_mkt, c_sym, c_btn = st.columns([2, 3, 1])
    with c_mkt:
        dive_mkt = st.selectbox("ตลาดของหุ้น:", ["🇹🇭 หุ้นไทย (SET)", "🇺🇸 หุ้นสหรัฐฯ (US)"], index=0)
        sel_dive_mkt = "TH" if "หุ้นไทย" in dive_mkt else "US"
    with c_sym:
        default_val = "PTT" if sel_dive_mkt == "TH" else "NVDA"
        search_sym = st.text_input("กรอกชื่อย่อหุ้น:", value=default_val).strip().upper()
    with c_btn:
        st.write("")
        st.write("")
        run_analysis = st.button("🔍 วิเคราะห์หุ้น", type="primary")

    if run_analysis and search_sym:
        with st.spinner(f"หัวหน้านักวิเคราะห์ AI กำลังศึกษาข้อมูลหุ้น {search_sym}..."):
            result = analyze_stock(search_sym, market=sel_dive_mkt)
            if not result:
                st.error(f"ไม่พบข้อมูลหุ้น {search_sym} กรุณาตรวจสอบตัวสะกดและตลาดที่เลือกอีกครั้ง")
            else:
                tech = result["technical"]
                fund = result["fundamental"]
                df = result["df"]
                curr = result["currency"]
                disp = result["display_symbol"]

                st.markdown(f"### 🏢 [{result['market_tag']}] {disp} : {fund.get('name', disp)}")
                st.caption(f"กลุ่มธุรกิจ: {fund.get('sector')} | อุตสาหกรรม: {fund.get('industry')}")

                # Metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("ราคาปัจจุบัน", f"{curr}{tech['price']:.2f}", f"{tech['change_pct']:+.2f}%")
                m2.metric("RSI (14)", f"{tech['rsi']}")
                m3.metric("จุด Stop Loss แนะนำ", f"{curr}{tech['stop_loss']:.2f}")
                m4.metric("เป้าหมายกำไร 1", f"{curr}{tech['target_1']:.2f}")

                # กราฟ
                fig = create_stock_chart(df, result["symbol"], stop_loss=tech['stop_loss'], target_1=tech['target_1'], target_2=tech['target_2'])
                st.plotly_chart(fig, use_container_width=True)

                # บทวิเคราะห์ AI
                st.markdown(result["ai_commentary"])
                st.info(f"💡 อยากสอบถามหรือวางแผนเทรดหุ้น **{disp}** เพิ่มเติม? คุณสามารถไปที่เมนู **'💬 5. แชทปรึกษา AI Office'** เพื่อพูดคุยกับ Chief AI Advisor ได้เลยครับ")

# ==========================================
# แผนก 5: แชทปรึกษา AI Office (AI Chat Consultant)
# ==========================================
elif "แชทปรึกษา AI" in menu:
    st.subheader("💬 ห้องแชทปรึกษาการลงทุน AI Office (Chief AI Advisor)")
    st.write("ที่ปรึกษาส่วนตัวสไตล์ Swing Trade ช่วยวิเคราะห์จังหวะเข้าซื้อ, ตรวจสุขภาพพอร์ต, วางแผน Stop Loss และแนะนำขั้นตอนการส่งคำสั่งบน Webull & Streaming")

    # กล่องตั้งค่า Google Gemini API เพื่อเปิดพลัง LLM สนทนาอิสระเต็มพิกัด
    is_gemini_active = bool(config.GEMINI_API_KEY and config.GEMINI_API_KEY.strip().startswith("AIzaSy"))
    with st.expander("⚙️ ตั้งค่า Google Gemini API Key (ฟรี เพื่อปลดล็อก AI สนทนาอิสระแบบไม่มีขีดจำกัด)", expanded=False):
        if is_gemini_active:
            st.success("🟢 เชื่อมต่อ Google Gemini API สำเร็จ: กำลังใช้สมองกล Gemini 2.5 Flash ตอบคำถาม")
        else:
            st.info("💡 ขณะนี้ระบบกำลังใช้ **Built-in AI Expert Engine** ซึ่งวิเคราะห์สูตรคำนวณและหลักการเทรดจริงได้ครบถ้วน\nหากต้องการเปิดพลัง AI ให้ตอบสนทนาได้อิสระรอบด้าน สามารถนำ Google Gemini API Key มาใส่ได้ฟรีครับ")
        
        g_c1, g_c2 = st.columns([4, 1])
        with g_c1:
            in_key = st.text_input("กรอก Gemini API Key (ขึ้นต้นด้วย AIzaSy...):", value=config.GEMINI_API_KEY if is_gemini_active else "", type="password", placeholder="AIzaSy...")
        with g_c2:
            st.write("")
            st.write("")
            if st.button("💾 บันทึก Key", key="btn_save_gemini"):
                if in_key:
                    with st.spinner("กำลังทดสอบการเชื่อมต่อ Google Gemini API..."):
                        ok, g_msg = save_gemini_api_key(in_key)
                        if ok:
                            st.success(g_msg)
                            st.rerun()
                        else:
                            st.error(g_msg)
                else:
                    st.warning("กรุณากรอก API Key ก่อนกดบันทึก")
        st.caption("สมัครรับ Gemini API Key ฟรีใน 30 วินาทีได้ที่: [Google AI Studio](https://aistudio.google.com/app/apikey)")

    # แถบปุ่มลัดคำถามยอดนิยม
    st.markdown("##### ⚡ คำถามด่วนยอดนิยม (คลิกเพื่อให้ AI ตอบได้ทันที):")
    q_col1, q_col2, q_col3, q_col4 = st.columns(4)
    quick_prompt = None
    with q_col1:
        if st.button("💡 แนะนำหุ้นน่าซื้อวันนี้", key="qp_1", use_container_width=True):
            quick_prompt = "วันนี้มีหุ้นตัวไหนน่าสนใจซื้อสไตล์ Swing Trade บ้างครับ"
    with q_col2:
        if st.button("📊 วิเคราะห์ PTT (หุ้นไทย)", key="qp_2", use_container_width=True):
            quick_prompt = "ช่วยวิเคราะห์กราฟหุ้น PTT ให้หน่อยครับ ตอนนี้น่าซื้อมั้ย จุด Stop Loss และเป้าหมายเท่าไหร่"
    with q_col3:
        if st.button("🚀 วิเคราะห์ ARM (Webull)", key="qp_3", use_container_width=True):
            quick_prompt = "ช่วยวิเคราะห์กราฟหุ้น ARM บน Webull ให้หน่อยครับ ควรตั้งราคาซื้อและ Stop Loss ตรงไหน"
    with q_col4:
        if st.button("🛡️ ตรวจสุขภาพพอร์ตของฉัน", key="qp_4", use_container_width=True):
            quick_prompt = "ช่วยตรวจสุขภาพพอร์ตของฉันตอนนี้ให้หน่อยครับ มีตัวไหนต้องระวังหรือควรขายมั้ย"

    # ปุ่มล้างแชท
    col_clear1, col_clear2 = st.columns([8, 2])
    with col_clear2:
        if st.button("🗑️ ล้างการสนทนา", key="btn_clear_chat", use_container_width=True):
            st.session_state["chat_messages"] = []
            st.rerun()

    # จัดการประวัติการสนทนา
    if "chat_messages" not in st.session_state or not st.session_state["chat_messages"]:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "สวัสดีครับ! ผมคือ **Chief AI Advisor** ประจำ AI Trading Office 🏛️\n\n"
                    "คุณสามารถพิมพ์ถามคำถามเพื่อปรึกษาการลงทุนได้เลย เช่น:\n"
                    "- 📊 *'PTT ตอนนี้น่าซื้อมั้ย'* หรือ *'NVDA ย่อลงมารับได้ตรงไหน'*\n"
                    "- 🛡️ *'ตรวจสุขภาพพอร์ตของฉันตอนนี้หน่อย'*\n"
                    "- 🔭 *'มีหุ้นตัวไหนน่าซื้อบ้างในวันนี้'*\n"
                    "- 📱 *'สอนวิธีตั้ง Stop Loss บนแอป Webull หน่อย'*\n\n"
                    "พิมพ์ข้อความที่ต้องการปรึกษาด้านล่าง หรือกดปุ่มลัดด้านบนได้เลยครับ!"
                )
            }
        ]

    # แสดงประวัติการสนทนา
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ช่องกรอกคำถามของผู้ใช้
    user_input = st.chat_input("พิมพ์คำถามปรึกษา AI Office ที่นี่ เช่น 'DELTA ซื้อได้มั้ย', 'วิเคราะห์ NVDA', 'พอร์ตเป็นยังไงบ้าง'...")
    prompt_to_run = quick_prompt or user_input

    if prompt_to_run:
        # บันทึกข้อความของผู้ใช้
        st.session_state["chat_messages"].append({"role": "user", "content": prompt_to_run})
        with st.chat_message("user"):
            st.markdown(prompt_to_run)

        # ให้ AI วิเคราะห์และตอบคำถาม
        with st.chat_message("assistant"):
            with st.spinner("AI Office กำลังวิเคราะห์ข้อมูลตลาดสดและวางแผนให้คุณ..."):
                reply = generate_ai_chat_reply(prompt_to_run, st.session_state["chat_messages"])
                st.markdown(reply)

        st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
        st.rerun()

# ==========================================
# แผนก 6: ตั้งค่า & คู่มือ (Settings & Guide)
# ==========================================
elif "ตั้งค่า & คู่มือ" in menu:
    st.subheader("⚙️ การตั้งค่าระบบ & คู่มือการเทรดสำหรับมือใหม่")

    tab1, tab2 = st.tabs(["⚙️ จัดการ Watchlist & การแจ้งเตือน", "📖 คู่มือเทรดหุ้นไทย & สหรัฐฯ"])

    with tab1:
        st.markdown("#### 📋 จัดการรายชื่อหุ้นใน Watchlist")
        
        all_watch = get_watchlist()
        w_th = [x for x in all_watch if config.is_thai_stock(x) or str(x).endswith(".BK")]
        w_us = [x for x in all_watch if not config.is_thai_stock(x) and not str(x).endswith(".BK")]
        
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            st.markdown(f"**🇹🇭 หุ้นไทยใน Watchlist ({len(w_th)} ตัว):**")
            st.caption(", ".join([config.clean_display_symbol(x) for x in w_th]))
        with col_w2:
            st.markdown(f"**🇺🇸 หุ้นสหรัฐฯใน Watchlist ({len(w_us)} ตัว):**")
            st.caption(", ".join([config.clean_display_symbol(x) for x in w_us]))

        st.divider()
        
        add_col1, add_col2 = st.columns(2)
        with add_col1:
            st.markdown("##### ➕ เพิ่มหุ้นเข้า Watchlist")
            add_mkt = st.selectbox("เลือกตลาด:", ["🇹🇭 หุ้นไทย (SET)", "🇺🇸 หุ้นสหรัฐฯ (US)"], key="add_mkt_select")
            add_mkt_code = "TH" if "หุ้นไทย" in add_mkt else "US"
            new_sym = st.text_input("ชื่อย่อหุ้น (เช่น BDMS หรือ AMD):").strip().upper()
            if st.button("บันทึกเข้า Watchlist") and new_sym:
                add_to_watchlist(new_sym, category=add_mkt_code)
                st.success(f"เพิ่ม {new_sym} เข้า Watchlist เรียบร้อยแล้ว")
                st.rerun()

        with add_col2:
            st.markdown("##### 🗑️ ลบหุ้นออกจาก Watchlist")
            all_watch = get_watchlist()
            disp_options = {config.clean_display_symbol(s): s for s in all_watch}
            del_choice = st.selectbox("เลือกหุ้นที่ต้องการลบ:", options=list(disp_options.keys()) if disp_options else [""])
            if st.button("ลบออกจาก Watchlist") and del_choice:
                remove_from_watchlist(disp_options[del_choice])
                st.warning(f"ลบ {del_choice} ออกจาก Watchlist แล้ว")
                st.rerun()

    with tab2:
        st.markdown("""
        ### 📖 คู่มือการเทรดสำหรับมือใหม่ (หุ้นไทย & สหรัฐฯ)

        #### 1. เวลาเปิด-ปิดตลาดหุ้น:
        *   **🇹🇭 ตลาดหุ้นไทย (SET):**
            *   รอบเช้า: **10:00 - 12:30 น.**
            *   รอบบ่าย: **14:30 - 16:30 น.**
            *   *แอปแนะนำ:* Streaming, Webull Thailand, InnovestX ฯลฯ
        *   **🇺🇸 ตลาดหุ้นสหรัฐฯ (US):**
            *   เวลาเปิด: **20:30 - 03:00 น.** (ฤดูหนาว: 21:30 - 04:00 น.)
            *   *แอปแนะนำ:* Webull, Dime, InnovestX ฯลฯ

        #### 2. กลยุทธ์ Swing Trade สำหรับมือใหม่:
        *   **เน้นซื้อเมื่อย่อตัวในขาขึ้น (Pullback):** หุ้นที่อยู่เหนือ EMA 200 และย่อลงมาแตะแนวรับ EMA 20/50 เป็นจุดซื้อที่ได้เปรียบที่สุดและเสี่ยงต่ำ
        *   **ตั้ง Stop Loss เสมอ (-5%):** ไม่ว่าจะเป็นหุ้นไทยหรือหุ้นสหรัฐฯ หากหลุดจุดตัดขาดทุน ให้ตัดขาดทุนทันทีตามสัญญาณเตือนของ AI เพื่อรักษาเงินต้น
        *   **แบ่งขายทำกำไร (Take Profit):** เมื่อกำไรถึงเป้าแรก (+10%) ให้แบ่งขาย 50% แล้วเลื่อน Stop Loss มาบังทุน เพื่อให้กลายเป็นการเทรดที่ **ไร้ความเสี่ยง (Risk-Free Trade)**
        """)
