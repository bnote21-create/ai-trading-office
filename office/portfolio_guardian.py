import yfinance as yf
from typing import List, Dict, Any, Tuple, Optional
from config import (
    SWING_CONFIG, 
    is_thai_stock, 
    clean_display_symbol, 
    get_currency_symbol, 
    get_market_tag
)
from office.database import (
    get_active_holdings, 
    update_holding_highest_price, 
    update_holding_alert_state,
    log_alert
)
from office.notifier import notify_portfolio_action

def fetch_latest_price(symbol: str) -> float:
    """ดึงราคาล่าสุดของหุ้น (รองรับทั้งหุ้นไทยและสหรัฐฯ)"""
    try:
        ticker = yf.Ticker(symbol)
        fast_info = getattr(ticker, "fast_info", None)
        if fast_info and hasattr(fast_info, "last_price") and fast_info.last_price:
            return float(fast_info.last_price)
        
        hist = ticker.history(period="5d", interval="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return 0.0
    except Exception as e:
        print(f"Error fetching latest price for {symbol}: {e}")
        return 0.0

def evaluate_holding_status(holding: Dict[str, Any], current_price: float) -> Tuple[str, str, str]:
    """
    ประเมินสถานะหุ้นในพอร์ตเพื่อดูว่าควรขายหรือถือต่อ
    ส่งค่ากลับ: (action_code, action_text, detailed_advice)
    """
    symbol = holding["symbol"]
    cost = holding["cost_price"]
    shares = holding["shares"]
    sl = holding["stop_loss_price"] or (cost * 0.95)
    tp1 = holding["target_price_1"] or (cost * 1.10)
    tp2 = holding["target_price_2"] or (cost * 1.15)
    highest = holding["highest_price"] or cost

    curr = get_currency_symbol(symbol)
    disp_sym = clean_display_symbol(symbol)
    app_name = "Streaming หรือ Webull TH" if is_thai_stock(symbol) else "Webull"

    pnl_pct = ((current_price - cost) / cost) * 100
    highest_gain_pct = ((highest - cost) / cost) * 100

    # 1. เช็คจุดตัดขาดทุน (Stop Loss)
    if current_price <= sl:
        action_code = "STOP_LOSS"
        action_text = "🔴 แนะนำตัดขาดทุน (Cut Loss ด่วน)"
        advice = (
            f"ราคาปัจจุบัน {curr}{current_price:.2f} ต่ำกว่าหรือเท่ากับจุด Stop Loss ({curr}{sl:.2f}) "
            f"แนะนำให้เปิดแอป {app_name} แล้วส่งคำสั่ง Sell ทันที เพื่อป้องกันไม่ให้ขาดทุนบานปลาย"
        )
        return action_code, action_text, advice

    # 2. เช็คเป้าหมายกำไรที่ 2 (Take Profit 2)
    if current_price >= tp2:
        action_code = "TAKE_PROFIT_2"
        action_text = "🏆 ถึงเป้าหมายใหญ่ (Take Profit 100%)"
        advice = (
            f"ราคาพุ่งถึงเป้าหมายกำไร 2 ({curr}{tp2:.2f}) กำไรปัจจุบัน +{pnl_pct:.2f}% "
            f"แนะนำขายปิดทำกำไรทั้งหมดบน {app_name} เพื่อล็อกผลกำไรก้อนใหญ่เข้ากระเป๋า"
        )
        return action_code, action_text, advice

    # 3. เช็คเป้าหมายกำไรที่ 1 (Take Profit 1)
    if current_price >= tp1:
        action_code = "TAKE_PROFIT_1"
        action_text = "🎯 ถึงเป้าแรก (ขาย 50% + ยก Stop Loss บังทุน)"
        advice = (
            f"ราคาถึงเป้าแรก ({curr}{tp1:.2f}) กำไร +{pnl_pct:.2f}% แนะนำแบ่งขายออก 50% บน {app_name} "
            f"และขยับคำสั่ง Stop Loss ของหุ้นที่เหลือขึ้นมาที่ {curr}{cost:.2f} (ราคาต้นทุน) เพื่อป้องกันการขาดทุน"
        )
        return action_code, action_text, advice

    # 4. เช็ค Trailing Stop
    trail_act = SWING_CONFIG["trailing_stop_activation_pct"]
    trail_dist = SWING_CONFIG["trailing_stop_distance_pct"]
    if highest_gain_pct >= trail_act:
        trailing_stop_level = highest * (1 - (trail_dist / 100.0))
        if current_price <= trailing_stop_level and current_price > cost:
            action_code = "TRAILING_STOP"
            action_text = "🔒 ล็อกกำไร (Trailing Stop Triggered)"
            advice = (
                f"ราคาเคยทำจุดสูงสุดที่ {curr}{highest:.2f} และเริ่มย่อลงมาแตะเกณฑ์ Trailing Stop ({curr}{trailing_stop_level:.2f}) "
                f"กำไรปัจจุบันยังคงมีอยู่ +{pnl_pct:.2f}% แนะนำขายเพื่อล็อกกำไรไม่ให้หดหาย"
            )
            return action_code, action_text, advice

    # 5. ถือต่อตามแผนปกติ
    if pnl_pct >= 0:
        action_code = "HOLD_PROFIT"
        action_text = "🟢 ถือต่อรันเทรนด์ (In Profit)"
        advice = f"สถานะกำลังมีกำไร +{pnl_pct:.2f}% ราคายังอยู่ในกรอบปกติ ปล่อยให้ผลกำไรเติบโตต่อไป (Let profit run)"
    else:
        action_code = "HOLD_NORMAL"
        action_text = "⚪ ถือรอตามแผน (Under Cost)"
        advice = f"ราคาย่อตัว -{abs(pnl_pct):.2f}% แต่ยังไม่หลุดจุด Stop Loss ({curr}{sl:.2f}) ยังไม่ต้องตกใจ ให้ถือตามแผน"

    return action_code, action_text, advice

def inspect_portfolio(send_alerts: bool = True, *args, **kwargs) -> List[Dict[str, Any]]:
    """
    ตรวจสอบพอร์ตหุ้นทั้งหมด คำนวณ PnL และส่งแจ้งเตือนหากมีจังหวะต้อง Take Profit หรือ Cut Loss
    """
    market_filter = kwargs.get("market_filter", args[0] if len(args) > 0 else None)
    holdings = get_active_holdings(market_filter=market_filter)
    results = []

    for h in holdings:
        symbol = h["symbol"]
        curr_price = fetch_latest_price(symbol)
        if curr_price <= 0:
            continue

        # อัปเดตราคาสูงสุดเพื่อใช้ทำ Trailing stop
        if curr_price > (h["highest_price"] or 0):
            update_holding_highest_price(h["id"], curr_price)
            h["highest_price"] = curr_price

        action_code, action_text, advice = evaluate_holding_status(h, curr_price)
        cost = h["cost_price"]
        shares = h["shares"]
        pnl_val = (curr_price - cost) * shares
        pnl_pct = ((curr_price - cost) / cost) * 100

        res_item = {
            "id": h["id"],
            "symbol": symbol,
            "display_symbol": clean_display_symbol(symbol),
            "market_tag": get_market_tag(symbol),
            "currency": get_currency_symbol(symbol),
            "is_thai": is_thai_stock(symbol),
            "shares": shares,
            "cost_price": cost,
            "current_price": curr_price,
            "highest_price": h["highest_price"],
            "stop_loss_price": h["stop_loss_price"],
            "target_price_1": h["target_price_1"],
            "target_price_2": h["target_price_2"],
            "pnl_amount": round(pnl_val, 2),
            "pnl_pct": round(pnl_pct, 2),
            "action_code": action_code,
            "action_text": action_text,
            "advice": advice,
            "buy_date": h["buy_date"]
        }
        results.append(res_item)

        # หากมี Action สำคัญ ให้ส่งแจ้งเตือน (Telegram & LINE) ทันที (พร้อมป้องกันการส่งซ้ำทุกนาที)
        if send_alerts and action_code in ["STOP_LOSS", "TAKE_PROFIT_1", "TAKE_PROFIT_2", "TRAILING_STOP"]:
            last_alert = h.get("last_alert_code", "")
            if last_alert != action_code:
                log_alert(symbol, action_code, advice, sent_to_line=True)
                notify_portfolio_action(action_code, symbol, curr_price, cost, pnl_pct, action_text, advice)
                update_holding_alert_state(h["id"], action_code)
                print(f"[AUTO-ALERT] ยิงแจ้งเตือนทันที: {symbol} เกิดสถานะ {action_code}")

    return results

def get_portfolio_summary(holdings_evaluated: List[Dict[str, Any]]) -> Dict[str, Any]:
    """สรุปภาพรวมมูลค่าพอร์ตและสถิติ (แยกยอดหุ้นไทย ฿ และหุ้นสหรัฐฯ $)"""
    th_holdings = [h for h in holdings_evaluated if h.get("is_thai")]
    us_holdings = [h for h in holdings_evaluated if not h.get("is_thai")]

    # ยอดหุ้นไทย (บาท)
    th_cost = sum(h["cost_price"] * h["shares"] for h in th_holdings)
    th_value = sum(h["current_price"] * h["shares"] for h in th_holdings)
    th_pnl = th_value - th_cost
    th_pnl_pct = (th_pnl / th_cost * 100) if th_cost > 0 else 0.0

    # ยอดหุ้นสหรัฐฯ (ดอลลาร์)
    us_cost = sum(h["cost_price"] * h["shares"] for h in us_holdings)
    us_value = sum(h["current_price"] * h["shares"] for h in us_holdings)
    us_pnl = us_value - us_cost
    us_pnl_pct = (us_pnl / us_cost * 100) if us_cost > 0 else 0.0

    winning_count = sum(1 for h in holdings_evaluated if h["pnl_amount"] > 0)
    losing_count = sum(1 for h in holdings_evaluated if h["pnl_amount"] < 0)

    return {
        "total_cost": round(th_cost + us_cost, 2),
        "total_value": round(th_value + us_value, 2),
        "total_pnl_usd": round(us_pnl, 2),
        "total_pnl_pct": round(us_pnl_pct, 2),

        "th_cost": round(th_cost, 2),
        "th_value": round(th_value, 2),
        "th_pnl": round(th_pnl, 2),
        "th_pnl_pct": round(th_pnl_pct, 2),
        "th_positions": len(th_holdings),

        "us_cost": round(us_cost, 2),
        "us_value": round(us_value, 2),
        "us_pnl": round(us_pnl, 2),
        "us_pnl_pct": round(us_pnl_pct, 2),
        "us_positions": len(us_holdings),

        "winning_count": winning_count,
        "losing_count": losing_count,
        "total_positions": len(holdings_evaluated)
    }
