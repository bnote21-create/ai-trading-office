import argparse
import sys
import time
import schedule
from datetime import datetime

# รองรับ UTF-8 สำหรับ Windows Console
if sys.platform.startswith("win"):
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from office.market_scout import scan_watchlist
from office.portfolio_guardian import inspect_portfolio, get_portfolio_summary
from office.notifier import notify_buy_signal, broadcast_alert

def job_check_portfolio():
    """เฝ้าตรวจพอร์ตและส่งสัญญาณขาย (Take Profit / Stop Loss) ทั้งหุ้นไทยและสหรัฐฯ"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🛡️ AI Guardian กำลังตรวจเช็คพอร์ต...")
    holdings = inspect_portfolio(send_alerts=True)
    summary = get_portfolio_summary(holdings)
    print(f"สรุปพอร์ตหุ้นไทย: มูลค่า ฿{summary['th_value']:,.2f} | PnL: ฿{summary['th_pnl']:+,.2f} ({summary['th_pnl_pct']:+.2f}%)")
    print(f"สรุปพอร์ตสหรัฐฯ: มูลค่า ${summary['us_value']:,.2f} | PnL: ${summary['us_pnl']:+,.2f} ({summary['us_pnl_pct']:+.2f}%)")

def job_scan_market():
    """สแกนหาจังหวะเข้าซื้อ Swing Trade ทั้งหุ้นไทยและสหรัฐฯ"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔭 Market Scout กำลังสแกนหาหุ้นน่าซื้อ...")
    results = scan_watchlist()
    buy_signals = [r for r in results if r["signal"] == "BUY"]
    
    if buy_signals:
        print(f"พบสัญญาณซื้อ {len(buy_signals)} ตัว!")
        for b in buy_signals:
            curr = b.get("currency", "$")
            notify_buy_signal(
                symbol=b["symbol"],
                current_price=b["price"],
                setup_name=b["setup"],
                entry_zone=f"{curr}{b['price'] * 0.995:.2f} - {curr}{b['price']:.2f}",
                stop_loss=b["stop_loss"],
                target_1=b["target_1"],
                target_2=b["target_2"],
                rr_ratio=b["rr_ratio"],
                reason=b["reason"]
            )
    else:
        print("ยังไม่พบหุ้นที่มีสัญญาณซื้อชัดเจนในรอบนี้")

def main():
    parser = argparse.ArgumentParser(description="AI Trading Office Background Runner")
    parser.add_argument("--scan", action="store_true", help="สแกนหาหุ้นน่าซื้อทันที")
    parser.add_argument("--check-portfolio", action="store_true", help="ตรวจสอบพอร์ตและเตือนจุดขายทันที")
    parser.add_argument("--daemon", action="store_true", help="รันอัตโนมัติเป็น Background Loop")
    args = parser.parse_args()

    if args.scan:
        job_scan_market()
        return

    if args.check_portfolio:
        job_check_portfolio()
        return

    if args.daemon:
        print("🚀 เริ่มการทำงาน AI Trading Office ในโหมด Background Daemon...")
        broadcast_alert("🏛️ [AI Office] เริ่มต้นระบบเฝ้าจับตาพอร์ตและตลาดสหรัฐฯ อัตโนมัติแล้วครับ")

        # ตรวจพอร์ตทุกๆ 30 นาที
        schedule.every(30).minutes.do(job_check_portfolio)
        # สแกนหาหุ้นซื้อทุกๆ 2 ชั่วโมง หรือช่วงก่อนตลาดเปิด
        schedule.every(2).hours.do(job_scan_market)

        # รันครั้งแรกทันที
        job_check_portfolio()
        job_scan_market()

        while True:
            schedule.run_pending()
            time.sleep(10)
    else:
        print("คำสั่งใช้งาน:")
        print("  python run_office.py --scan             (สแกนหุ้นน่าซื้อ)")
        print("  python run_office.py --check-portfolio  (ตรวจเช็คพอร์ตและสัญญาณขาย)")
        print("  python run_office.py --daemon           (รันทำงานอัตโนมัติตลอดเวลา)")
        print("  streamlit run app.py                    (เปิดหน้าจอ Web Dashboard)")

if __name__ == "__main__":
    main()
