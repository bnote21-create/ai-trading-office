import os
import logging
import requests
from typing import Optional, Dict, Tuple
from dotenv import load_dotenv
import config

logger = logging.getLogger("Notifier")

def get_telegram_config() -> Tuple[str, str]:
    """โหลดค่า Telegram Token และ Chat ID ล่าสุดจาก .env หรือ st.secrets เสมอ"""
    load_dotenv(config.BASE_DIR / ".env", override=True)
    token = config.get_config_var("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")
    chat_id = config.get_config_var("TELEGRAM_CHAT_ID", "").strip().strip('"').strip("'")
    return token, chat_id

def get_line_config() -> Tuple[str, str, str]:
    """โหลดค่า LINE Token ล่าสุดจาก .env หรือ st.secrets เสมอ"""
    load_dotenv(config.BASE_DIR / ".env", override=True)
    notify_token = config.get_config_var("LINE_NOTIFY_TOKEN", "").strip().strip('"').strip("'")
    channel_token = config.get_config_var("LINE_CHANNEL_ACCESS_TOKEN", "").strip().strip('"').strip("'")
    user_id = config.get_config_var("LINE_USER_ID", "").strip().strip('"').strip("'")
    return notify_token, channel_token, user_id

def send_telegram_message(message: str) -> Tuple[bool, str]:
    """
    ส่งข้อความแจ้งเตือนผ่าน Telegram Bot
    ส่งคืน: (สถานะความสำเร็จ: bool, ข้อความแจ้งผู้ใช้: str)
    """
    token, chat_id = get_telegram_config()
    
    if not token or not chat_id or "YOUR_TELEGRAM" in token or "YOUR_TELEGRAM" in chat_id:
        return False, "ยังไม่ได้ใส่ TELEGRAM_BOT_TOKEN หรือ TELEGRAM_CHAT_ID ในไฟล์ .env"
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message
        }
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

        if response.status_code == 200:
            print(f"[Telegram Bot] ส่งข้อความสำเร็จ: {message[:40]}...")
            return True, "ส่งข้อความเข้า Telegram สำเร็จเรียบร้อยแล้ว!"
        else:
            err_desc = res_data.get("description", response.text)
            print(f"[Telegram Bot] ส่งไม่สำเร็จ (Status {response.status_code}): {err_desc}")
            
            if "chat not found" in err_desc.lower():
                return False, "ยังไม่ได้กด Start ที่บอท! กรุณาเปิดแอป Telegram แล้วกดปุ่ม 'Start' ในแชทของบอทคุณก่อน 1 ครั้งครับ"
            
            return False, f"ส่งไม่สำเร็จ: {err_desc}"
    except Exception as e:
        print(f"[Telegram Bot Error] {e}")
        return False, f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}"

def send_line_message(message: str) -> Tuple[bool, str]:
    """ส่งข้อความแจ้งเตือนผ่าน LINE (รองรับทั้ง LINE Notify และ LINE Messaging API)"""
    notify_token, channel_token, user_id = get_line_config()
    
    # 1. ลองส่งผ่าน LINE Notify ก่อนหากมี Token
    if notify_token:
        try:
            url = "https://notify-api.line.me/api/notify"
            headers = {"Authorization": f"Bearer {notify_token}"}
            payload = {"message": f"\n{message}"}
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            if response.status_code == 200:
                print(f"[LINE Notify] ส่งข้อความสำเร็จ: {message[:40]}...")
                return True, "ส่งข้อความเข้า LINE Notify สำเร็จ!"
            else:
                return False, f"LINE Notify ไม่สำเร็จ (Status {response.status_code}): {response.text}"
        except Exception as e:
            return False, f"เกิดข้อผิดพลาดกับ LINE Notify: {e}"

    # 2. ลองส่งผ่าน LINE Messaging API หากตั้งค่าไว้
    if channel_token and user_id:
        # ตรวจสอบเบื้องต้นหากผู้ใช้นำ Channel Secret 32 ตัวอักษรมาใส่
        if len(channel_token) <= 40:
            return False, "LINE_CHANNEL_ACCESS_TOKEN ที่ใส่อยู่คือ Channel Secret (32 ตัว) กรุณากดปุ่ม Issue ในแท็บ Messaging API เพื่อรับ Token โค้ดยาวๆ ครับ"

        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {channel_token}"
            }
            payload = {
                "to": user_id,
                "messages": [{"type": "text", "text": message}]
            }
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"[LINE Bot] ส่งข้อความสำเร็จ: {message[:40]}...")
                return True, "ส่งข้อความเข้า LINE สำเร็จเรียบร้อยแล้ว!"
            else:
                res_err = response.json().get("message", response.text) if response.headers.get("content-type", "").startswith("application/json") else response.text
                return False, f"LINE ส่งไม่สำเร็จ ({res_err})"
        except Exception as e:
            return False, f"เกิดข้อผิดพลาดในการเชื่อมต่อ LINE: {e}"

    return False, "ยังไม่ได้ใส่ LINE Token ในไฟล์ .env"

def broadcast_alert(message: str) -> Dict[str, bool]:
    """ส่งข้อความแจ้งเตือนไปยังทุกช่องทางที่ผู้ใช้ตั้งค่าไว้ (LINE และ Telegram)"""
    tg_ok, _ = send_telegram_message(message)
    line_ok, _ = send_line_message(message)
    
    results = {
        "line": line_ok,
        "telegram": tg_ok
    }

    if not results["line"] and not results["telegram"]:
        print(f"\n📢 [OFFICE ALERT - PREVIEW]:\n{message}\n" + "-"*50)
        
    return results

# --- ฟังก์ชันตัวช่วยสร้าง Template ข้อความแจ้งเตือนสำหรับมือใหม่ ---

def notify_buy_signal(symbol: str, current_price: float, setup_name: str, 
                      entry_zone: str, stop_loss: float, target_1: float, target_2: float, 
                      rr_ratio: float, reason: str):
    """แจ้งเตือนสัญญาณเข้าซื้อสไตล์ Swing Trade (รองรับทั้งหุ้นไทยและสหรัฐฯ)"""
    curr = config.get_currency_symbol(symbol)
    disp_sym = config.clean_display_symbol(symbol)
    market_tag = config.get_market_tag(symbol)
    app_guide = "เข้าแอป Streaming หรือ Webull Thailand" if config.is_thai_stock(symbol) else "เข้าแอป Webull"

    msg = (
        f"🟢 [สัญญาณซื้อ Swing Trade] {market_tag} : {disp_sym}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ราคาปัจจุบัน: {curr}{current_price:.2f}\n"
        f"📊 กลยุทธ์: {setup_name}\n"
        f"🎯 จุดเข้าซื้อ (Entry): {entry_zone}\n"
        f"🛑 จุดตัดขาดทุน (Stop Loss): {curr}{stop_loss:.2f} (สำคัญมาก!)\n"
        f"🏁 เป้าหมายกำไร 1: {curr}{target_1:.2f}\n"
        f"🏁 เป้าหมายกำไร 2: {curr}{target_2:.2f}\n"
        f"⚖️ Risk/Reward Ratio: 1:{rr_ratio:.1f}\n"
        f"📝 เหตุผลวิเคราะห์:\n{reason}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💡 คำแนะนำสำหรับมือใหม่:\n"
        f"- {app_guide} ค้นหา {disp_sym}\n"
        f"- วางคำสั่งซื้อ Limit/Market พร้อมตั้ง Stop Loss ที่ {curr}{stop_loss:.2f}"
    )
    return broadcast_alert(msg)

def notify_portfolio_action(action_type: str, symbol: str, current_price: float, 
                            cost_price: float, pnl_pct: float, recommendation: str, advice: str):
    """แจ้งเตือนการจัดการหุ้นในพอร์ต (Take Profit / Cut Loss / Trailing Stop)"""
    curr = config.get_currency_symbol(symbol)
    disp_sym = config.clean_display_symbol(symbol)
    market_tag = config.get_market_tag(symbol)
    app_guide = "เปิดแอป Streaming หรือ Webull TH" if config.is_thai_stock(symbol) else "เปิดแอป Webull"

    emoji_map = {
        "STOP_LOSS": "🚨 [ตัดขาดทุนด่วน - Cut Loss]",
        "TAKE_PROFIT_1": "🎯 [ถึงเป้ากำไร 1 - Take Profit]",
        "TAKE_PROFIT_2": "🏆 [ถึงเป้ากำไร 2 - ล็อกกำไรก้อนใหญ่]",
        "TRAILING_STOP": "🔒 [ล็อกกำไร - Trailing Stop]",
        "WARNING": "⚠️ [เตือนความเสี่ยงในพอร์ต]"
    }
    header = emoji_map.get(action_type, "📢 [แจ้งเตือนพอร์ตหุ้น]")
    
    pnl_sign = "+" if pnl_pct >= 0 else ""
    msg = (
        f"{header} {market_tag} : {disp_sym}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ราคาปัจจุบัน: {curr}{current_price:.2f}\n"
        f"💵 ต้นทุนของคุณ: {curr}{cost_price:.2f}\n"
        f"📈 กำไร/ขาดทุน: {pnl_sign}{pnl_pct:.2f}%\n"
        f"⚡ คำแนะนำ: {recommendation}\n"
        f"📝 รายละเอียด:\n{advice}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📱 {app_guide} เพื่อปรับออเดอร์ตามคำแนะนำทันที"
    )
    return broadcast_alert(msg)
