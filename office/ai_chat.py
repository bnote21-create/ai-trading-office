import re
import os
from typing import List, Dict, Any, Optional, Tuple
import config
from office.market_scout import fetch_stock_data, calculate_indicators, evaluate_swing_setup, scan_watchlist
from office.analyst import analyze_stock, get_fundamental_summary
from office.portfolio_guardian import inspect_portfolio, get_portfolio_summary

NON_STOCK_WORDS = {
    "AI", "BUY", "SELL", "EMA", "RSI", "TP", "SL", "PE", "OK", "NO", "YES", 
    "THB", "USD", "SET", "US", "TH", "ETF", "WEBULL", "APP", "STREAMING", 
    "HELP", "CHAT", "BOT", "OFFICE", "PORT", "HOLD", "CUT", "LOSS", "PROFIT",
    "THE", "AND", "FOR", "NOT", "ALL", "NEW", "DAY", "TOP", "LOW", "HIGH",
    "STOP", "TRAILING", "ORDER", "LIMIT", "MARKET", "TRADE", "TRADING", "PRICE",
    "COST", "CASH", "CALL", "PUT", "LONG", "SHORT", "RISK", "REWARD", "RATIO",
    "SHARE", "SHARES", "STOCK", "STOCKS", "DOW", "INDEX", "WHY", "HOW", "WHAT"
}

def extract_stock_symbols(text: str) -> List[str]:
    """สกัดชื่อย่อหุ้นจากข้อความของผู้ใช้ (เช่น PTT, NVDA, ARM, DELTA)"""
    tokens = re.findall(r"\b[A-Za-z]{2,6}\b", text.upper())
    found = []
    for t in tokens:
        if t not in NON_STOCK_WORDS:
            found.append(t)
    return list(dict.fromkeys(found))

def get_portfolio_snapshot_text() -> str:
    """สรุปข้อมูลพอร์ตปัจจุบันเพื่อส่งให้ AI ใช้ตอบคำถาม"""
    holdings = inspect_portfolio(send_alerts=False)
    if not holdings:
        return "สถานะพอร์ต: ขณะนี้ไม่มีหุ้นที่ถืออยู่ในพอร์ต (พอร์ตว่าง 100% เงินสดพร้อมลงทุน)"
    
    summary = get_portfolio_summary(holdings)
    lines = [f"สถานะพอร์ตปัจจุบัน (ถือหุ้นอยู่ทั้งหมด {summary['total_positions']} ตัว):"]
    if summary['th_positions'] > 0:
        lines.append(f"- 🇹🇭 หุ้นไทย: {summary['th_positions']} ตัว มูลค่า ฿{summary['th_value']:,.2f} (กำไร/ขาดทุน: {summary['th_pnl']:+,.2f} บาท หรือ {summary['th_pnl_pct']:+.2f}%)")
    if summary['us_positions'] > 0:
        lines.append(f"- 🇺🇸 หุ้นสหรัฐฯ: {summary['us_positions']} ตัว มูลค่า ${summary['us_value']:,.2f} (กำไร/ขาดทุน: ${summary['us_pnl']:+,.2f} หรือ {summary['us_pnl_pct']:+.2f}%)")
    
    lines.append("\nรายการหุ้นในพอร์ตแต่ละตัว:")
    for h in holdings:
        curr = h.get("currency", "$")
        pnl_pct = h.get("pnl_pct", 0.0)
        sign = "+" if pnl_pct >= 0 else ""
        lines.append(
            f"• {h['display_symbol']} ({h['market_tag']}): ราคาปัจจุบัน {curr}{h['current_price']:.2f} | ทุน {curr}{h['cost_price']:.2f} | PnL: {sign}{pnl_pct:.2f}% | SL: {curr}{h['stop_loss_price']:.2f} | TP1: {curr}{h['target_price_1']:.2f} | สถานะ: {h['action_text']}"
        )
    return "\n".join(lines)

def get_scout_recommendations_text() -> str:
    """ดึงหุ้นที่มีสัญญาณซื้อล่าสุดจาก Watchlist เพื่อให้ AI แนะนำ"""
    try:
        results = scan_watchlist()
        buy_list = [r for r in results if r.get("signal") == "BUY"]
        if not buy_list:
            return "ผลสแกนล่าสุด: ยังไม่มีหุ้นตัวใดใน Watchlist ที่เข้าเกณฑ์ Buy Setup ชัดเจน แนะนำให้อดทนรอจังหวะที่ได้เปรียบ (Cash is a position)"
        
        lines = [f"หุ้นที่ฝ่ายสแกน (Market Scout) พบสัญญาณเข้าซื้อ (BUY) ล่าสุด {len(buy_list)} ตัว:"]
        for b in buy_list[:5]:
            curr = b.get("currency", "$")
            lines.append(
                f"• {b['display_symbol']} ({b['market_tag']}): ราคา {curr}{b['price']:.2f} | กลยุทธ์: {b['setup']} | คะแนน: {b['score']}/100 | SL: {curr}{b['stop_loss']:.2f} | TP1: {curr}{b['target_1']:.2f} | R/R: 1:{b['rr_ratio']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"ไม่สามารถดึงข้อมูลสแกนหุ้นได้: {e}"

def test_gemini_key(api_key: str) -> Tuple[bool, str]:
    """ทดสอบการเชื่อมต่อ Gemini API Key"""
    if not api_key or len(api_key.strip()) < 20:
        return False, "กรุณากรอกรหัส API Key ให้ครบถ้วน"
    try:
        from google import genai
        client = genai.Client(api_key=api_key.strip())
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='สวัสดี ตอบสั้นๆ 1 คำว่า สำเร็จ'
        )
        if res.text:
            return True, "เชื่อมต่อ Google Gemini API สำเร็จเรียบร้อยแล้ว!"
        return False, "ไม่ได้รับข้อมูลตอบกลับจาก Gemini"
    except Exception as e:
        return False, f"เชื่อมต่อไม่สำเร็จ: {e}"

def save_gemini_api_key(new_key: str) -> Tuple[bool, str]:
    """บันทึก Gemini API Key ลงไฟล์ .env และอัปเดตระบบ"""
    ok, msg = test_gemini_key(new_key)
    if not ok:
        return False, msg

    try:
        clean_key = new_key.strip()
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "GEMINI_API_KEY=" in content:
                content = re.sub(r'GEMINI_API_KEY=.*', f'GEMINI_API_KEY="{clean_key}"', content)
            else:
                content = f'GEMINI_API_KEY="{clean_key}"\n' + content
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        config.GEMINI_API_KEY = clean_key
        return True, "บันทึกและเชื่อมต่อ Gemini API Key สำเร็จ! ระบบพร้อมใช้งาน AI อัจฉริยะเต็มพิกัดแล้วครับ"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการบันทึกไฟล์ .env: {e}"

def generate_ai_chat_reply(user_message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    สร้างคำตอบจาก AI Office Consultant
    - ตรวจจับบริบทคำถามและประวัติการสนทนา
    - ตรวจจับชื่อหุ้น ดึงราคาและอินดิเคเตอร์สด
    - เชื่อมต่อ Gemini API หรือ Built-in AI Expert Advisor Engine
    """
    msg_clean = user_message.strip()

    # 1. รวบรวมบริบทข้อมูลตลาดสดตามความเกี่ยวข้องของคำถาม
    is_asking_portfolio = any(k in msg_clean for k in ["พอร์ตของฉัน", "ตรวจพอร์ต", "หุ้นที่ถืออยู่", "หุ้นในพอร์ต", "สรุปพอร์ต", "พอร์ตตอนนี้"])
    is_asking_recommendation = any(k in msg_clean for k in ["ตัวไหนน่าซื้อ", "แนะนำหุ้น", "สแกน", "ซื้ออะไรดี", "มีหุ้นอะไรน่าสนใจ", "หุ้นเด่น", "หุ้นน่าสนใจวันนี้"])
    symbols = extract_stock_symbols(msg_clean)

    context_data = []
    if is_asking_portfolio:
        context_data.append(get_portfolio_snapshot_text())
    if is_asking_recommendation:
        context_data.append(get_scout_recommendations_text())

    stocks_analyzed = []
    if symbols:
        for sym in symbols[:3]:
            res = analyze_stock(sym)
            if res:
                stocks_analyzed.append(res)
                tech = res["technical"]
                fund = res["fundamental"]
                curr = res["currency"]
                context_data.append(
                    f"ข้อมูลวิเคราะห์หุ้น {res['display_symbol']} ({res['market_tag']}):\n"
                    f"- บริษัท: {fund.get('name')}\n"
                    f"- ราคาล่าสุด: {curr}{tech['price']:.2f} (วันนี้ {tech['change_pct']:+.2f}%)\n"
                    f"- เส้นเฉลี่ย EMA 20: {curr}{tech['ema20']:.2f} | EMA 50: {curr}{tech['ema50']:.2f} | EMA 200: {curr}{tech['ema200']:.2f}\n"
                    f"- RSI (14): {tech['rsi']} | วอลุ่ม: {tech['vol_ratio']}x\n"
                    f"- สัญญาณ: {tech['signal']} (คะแนน {tech['score']}/100) | กลยุทธ์: {tech['setup']}\n"
                    f"- Stop Loss: {curr}{tech['stop_loss']:.2f} | TP1: {curr}{tech['target_1']:.2f} | TP2: {curr}{tech['target_2']:.2f}\n"
                    f"- Risk/Reward Ratio: 1:{tech['rr_ratio']}\n"
                    f"- เหตุผล: {tech['reason']}"
                )

    # 2. ลองส่งคำถามให้ Gemini LLM หากมี Key ที่ถูกต้อง
    if config.GEMINI_API_KEY and len(config.GEMINI_API_KEY.strip()) > 30 and config.GEMINI_API_KEY.strip().startswith("AIzaSy"):
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY.strip())
            
            history_summary = ""
            if chat_history and len(chat_history) > 1:
                recent_turns = chat_history[-5:-1]
                history_summary = "บทสนทนาก่อนหน้านี้:\n"
                for h in recent_turns:
                    role_label = "ผู้ใช้" if h["role"] == "user" else "AI Advisor"
                    history_summary += f"{role_label}: {h['content'][:300]}\n"

            system_instruction = (
                "คุณคือ 'Chief AI Advisor' หัวหน้าที่ปรึกษาการลงทุนประจำ AI Trading Office 🏛️ "
                "ให้คำปรึกษาการลงทุนสไตล์ Swing Trade (ถือครองรอบระดับหลายวันถึง 2-4 สัปดาห์) "
                "สำหรับนักลงทุนมือใหม่ที่เทรดหุ้นไทย (ผ่าน Streaming / Webull Thailand) และหุ้นสหรัฐฯ (ผ่าน Webull US)\n\n"
                "หลักการตอบคำถาม:\n"
                "1. ตอบภาษาไทยอย่างเป็นกันเอง มั่นใจ สุภาพ และให้เหตุผลที่ลึกซึ้ง ครอบคลุม ชัดเจนแบบมืออาชีพ\n"
                "2. หากผู้ใช้ถามเรื่อง Risk/Reward (R/R) ให้อธิบายความสัมพันธ์ระหว่าง Win Rate กับ R/R ทางคณิตศาสตร์อย่างชัดเจน\n"
                "3. หากผู้ใช้ถามเรื่องหุ้น ให้วางแผนเทรดครบ 4 องค์ประกอบ: จุดเข้า (Entry), จุดตัดขาดทุน (Stop Loss), เป้ากำไร (Take Profit), และ Risk/Reward Ratio\n"
                "4. แนะนำขั้นตอนการตั้งคำสั่งบนแอป Webull / Streaming สำหรับมือใหม่เสมอ"
            )

            prompt_parts = [system_instruction]
            if history_summary:
                prompt_parts.append(history_summary)
            if context_data:
                prompt_parts.append("=== ข้อมูลตลาดสดจาก AI Office ===\n" + "\n\n".join(context_data) + "\n==========================")
            prompt_parts.append(f"คำถามของผู้ใช้: {msg_clean}")

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents="\n\n".join(prompt_parts)
            )
            if response.text and response.text.strip():
                return response.text
        except Exception as e:
            print(f"[Gemini Notice] {e} -> switching to Built-in AI Expert Advisor Engine")

    # 3. Built-in AI Expert Advisor Engine ที่ชาญฉลาดและครอบคลุมทุกมิติ
    return generate_comprehensive_expert_response(
        user_msg=msg_clean, 
        chat_history=chat_history,
        is_asking_portfolio=is_asking_portfolio, 
        is_asking_recommendation=is_asking_recommendation, 
        stocks_analyzed=stocks_analyzed
    )

def generate_comprehensive_expert_response(
    user_msg: str, 
    chat_history: Optional[List[Dict[str, str]]],
    is_asking_portfolio: bool, 
    is_asking_recommendation: bool, 
    stocks_analyzed: List[Dict[str, Any]]
) -> str:
    """สมองกล AI Expert ประจำสำนักงาน: วิเคราะห์เจาะลึกทุกคำถามการเทรดอย่างครอบคลุม"""
    msg = user_msg.strip()
    msg_lower = msg.lower()

    # =========================================================================
    # หมวด 1: การประเมิน Risk/Reward Ratio (R/R), ความคุ้มค่าในการเทรด, Win Rate
    # (ครอบคลุมข้อความเช่น "R/R: 1:1.5 อย่างงี้ก็ไม่น่าซื้อสิ", "1:1.5 คุ้มมั้ย", "R/R ต่ำ")
    # =========================================================================
    is_rr_query = bool(re.search(r'(R/?R|RISK\s*/?\s*REWARD|1\s*:\s*[0-9\.]+|คุ้มมั้ย|ไม่น่าซื้อ|ความคุ้มค่า|อัตราส่วน)', msg, re.IGNORECASE))
    if is_rr_query and any(k in msg_lower for k in ["1:", "r/r", "rr", "risk", "reward", "ไม่น่าซื้อ", "คุ้ม"]):
        # สกัดตัวเลข R/R ถ้ามี เช่น 1.5, 2, 1
        rr_match = re.search(r'1\s*:\s*([0-9\.]+)', msg)
        rr_num = float(rr_match.group(1)) if rr_match else 1.5

        return (
            f"### 💡 วิเคราะห์เจาะลึก: Risk/Reward Ratio 1:{rr_num:.1f} ควรซื้อหรือไม่?\n\n"
            f"**คำตอบสั้นๆ: คุณมองเกมขาดและมีวินัยที่ถูกต้องมากครับ! 👏 สำหรับสไตล์ Swing Trade อัตรา R/R 1:{rr_num:.1f} ถือว่า 'ไม่น่าเข้าซื้อ' จริงๆ ครับ**\n\n"
            "---\n\n"
            "#### 1. เหตุผลทางคณิตศาสตร์: Win Rate vs Risk/Reward (R/R)\n"
            "ในโลกการเทรด อัตราการชนะที่ทำให้พอร์ตไม่ขาดทุน (Breakeven Win Rate) คำนวณจาก:\n"
            "$$\\text{Win Rate ขั้นต่ำที่ต้องชนะ} = \\frac{\\text{ความเสี่ยง (Risk)}}{\\text{ความเสี่ยง (Risk)} + \\text{ผลตอบแทน (Reward)}}$$\n\n"
            f"• **ที่ R/R 1:{rr_num:.1f}**: คุณต้องเทรดชนะอย่างน้อย **{100.0 / (1.0 + rr_num):.1f}%** ของจำนวนครั้งทั้งหมด ถึงจะแค่ 'เท่าทุน'!\n"
            "• **ที่ R/R 1:2.0**: คุณต้องการ Win Rate เพียง **33.3%** (ทายถูกแค่ 1 ใน 3 ครั้ง พอร์ตก็ไม่ขาดทุนแล้ว)\n"
            "• **ที่ R/R 1:3.0**: คุณต้องการ Win Rate เพียง **25.0%** (ทายถูกแค่ 1 ใน 4 ครั้ง แต่พอร์ตยังเติบโตได้)\n\n"
            "---\n\n"
            "#### 2. ทำไม R/R ต่ำกว่า 1:2.0 ถึงไม่เหมาะกับมือใหม่?\n"
            "1. **ต้นทุนแฝง (Slippage & Commission):** การส่งคำสั่งจริงอาจไม่ได้ราคาเป๊ะ และมีค่าธรรมเนียม ทำให้อัตรากำไรจริงหดหายต่ำกว่า 1.5 เท่า\n"
            "2. **ไม่มีพื้นที่รองรับความผิดพลาด (Margin of Error):** หากตลาดแกว่งตัวผันผวนแล้วคุณผิดพลาดติดกัน 2 ครั้ง คุณต้องชนะถึง 3-4 ครั้งเพื่อดึงทุนกลับมา\n"
            "3. **ความกดดันทางอารมณ์:** ยิ่ง R/R ต่ำ คุณจะยิ่งกลัวแพ้ เพราะแพ้ครั้งเดียวอาจกลืนกำไรของรอบที่แล้วไปเกือบหมด\n\n"
            "---\n\n"
            "#### 3. กรณีเดียวที่ R/R 1:1.5 พอจะใช้ได้:\n"
            "คือระบบที่มี **Win Rate สูงลิ่วระดับ 70% ขึ้นไป** เช่น หุ้นบลูชิพขนาดใหญ่ (Large Cap) ที่ลงมาแตะแนวรับใหญ่ EMA 200 ในช่วงตลาด Sideway\n\n"
            "---\n\n"
            "#### 🎯 สรุปคำแนะนำจาก Chief AI Advisor:\n"
            "> **'Cash is a Position' (การถือเงินสดรอ คือหนึ่งในตำแหน่งที่ดีที่สุด)**\n"
            "> การเลือก **'ไม่เข้าซื้อ (Pass)'** ในหุ้นที่ R/R ต่ำกว่า 1:2.0 ถือเป็นสัญญาณของเทรดเดอร์ที่มีวินัยสูงมากครับ ไม่ต้องรีบร้อน ตลาดมีหุ้นให้เลือกเทรดทุกวัน อดทนรอจังหวะที่ได้เปรียบ 1:2 ถึง 1:3 พอร์ตของคุณจะเติบโตอย่างมั่นคงและยั่งยืนกว่ามากครับ! 🚀"
        )

    # =========================================================================
    # หมวด 2: หุ้นรายตัวที่ถูกตรวจจับในข้อความ
    # =========================================================================
    if stocks_analyzed:
        parts = []
        for s in stocks_analyzed:
            sym = s["display_symbol"]
            m_tag = s["market_tag"]
            curr = s["currency"]
            tech = s["technical"]
            fund = s["fundamental"]
            app_name = "Streaming หรือ Webull TH" if s.get("is_thai") else "Webull US"

            parts.append(f"### 📊 บทวิเคราะห์เจาะลึกหุ้น **{sym}** ({m_tag})")
            parts.append(f"🏢 **บริษัท:** {fund.get('name', sym)} | **กลุ่มธุรกิจ:** {fund.get('sector', 'N/A')} ({fund.get('industry', 'N/A')})")
            parts.append(f"💰 **ราคาล่าสุด:** {curr}{tech['price']:.2f} ({tech['change_pct']:+.2f}%) | **RSI (14):** {tech['rsi']} | **วอลุ่มเทียบค่าเฉลี่ย:** {tech['vol_ratio']}x")
            parts.append(f"📈 **เส้นเฉลี่ย:** EMA 20: {curr}{tech['ema20']:.2f} | EMA 50: {curr}{tech['ema50']:.2f} | EMA 200: {curr}{tech['ema200']:.2f}")
            parts.append("---")
            
            if tech["signal"] == "BUY":
                parts.append(f"💡 **ความเห็นของ AI:** 🟢 **จังหวะน่าเข้าซื้อ (Buy Setup: {tech['setup']})**")
                parts.append(f"คะแนนความพร้อม **{tech['score']}/100** โครงสร้างราคายังยืนเหนือแนวโน้มสำคัญและมีแรงซื้อสนับสนุน")
                parts.append(f"\n📋 **แผนการเทรดสไตล์ Swing Trade:**")
                parts.append(f"- 🎯 **จุดเข้าซื้อ (Entry Zone):** บริเวณราคา {curr}{tech['price']:.2f}")
                parts.append(f"- 🛑 **จุดตัดขาดทุน (Stop Loss):** {curr}{tech['stop_loss']:.2f} (สำคัญที่สุด! หากหลุดจุดนี้ให้ขายทันที)")
                parts.append(f"- 🏁 **เป้าหมายกำไร 1 (TP1):** {curr}{tech['target_1']:.2f} (เมื่อถึงเป้าแรก แนะนำแบ่งขาย 50% และเลื่อน Stop Loss มาบังทุน)")
                parts.append(f"- 🏁 **เป้าหมายกำไร 2 (TP2):** {curr}{tech['target_2']:.2f} (ขายทำกำไรทั้งหมด)")
                parts.append(f"- ⚖️ **Risk/Reward Ratio:** 1:{tech['rr_ratio']} (อัตราส่วน {'สวยงาม คุ้มเสี่ยง' if tech['rr_ratio'] >= 2.0 else 'ค่อนข้างกระชับ'})")
                parts.append(f"\n📱 **คำแนะนำสำหรับมือใหม่บนแอป {app_name}:**")
                parts.append(f"1. ค้นหา `{sym}` กดปุ่ม **Trade**")
                parts.append(f"2. เลือก **Limit Order** ที่ราคา {curr}{tech['price']:.2f}")
                parts.append(f"3. เปิดแถบ **Take Profit / Stop Loss** ล่วงหน้า ใส่ Stop Price ที่ {curr}{tech['stop_loss']:.2f} และ TP ที่ {curr}{tech['target_1']:.2f} เพื่อให้ระบบดูแลพอร์ตอัตโนมัติ")
            elif tech["signal"] == "SELL":
                parts.append(f"💡 **ความเห็นของ AI:** 🔴 **ส่งสัญญาณขายหรือระมัดระวัง (Sell Setup: {tech['setup']})**")
                parts.append(f"กราฟเริ่มหลุดแนวรับหรือสัญญาณโมเมนตัมอ่อนแรงลง")
                parts.append(f"- **หากมีหุ้นอยู่:** แนะนำพิจารณาแบ่งขายล็อกกำไร หรือตั้ง Stop Loss ที่ {curr}{tech['stop_loss']:.2f} เพื่อป้องกันเงินทุน")
                parts.append(f"- **หากยังไม่มีของ:** **อย่าเพิ่งรีบรับมีด!** รอให้ราคาสร้างฐานหรือย่อตัวลงมาใกล้แนวรับ EMA ก่อนครับ")
            else:
                parts.append(f"💡 **ความเห็นของ AI:** ⚪ **รอจังหวะที่ได้เปรียบ (Wait & See: {tech['setup']})**")
                parts.append(f"ราคาขณะนี้ยังอยู่ในช่วงพักตัว/ไซด์เวย์ คะแนนความพร้อมอยู่ที่ {tech['score']}/100")
                parts.append(f"- แนวรับที่น่าจับตา: บริเวณเส้น EMA 20 ({curr}{tech['ema20']:.2f}) หรือ EMA 50 ({curr}{tech['ema50']:.2f})")
                parts.append(f"- คำแนะนำ: รอให้ราคาย่อลงมาทดสอบแนวรับแล้วมีแท่งเทียนกลับตัว จึงค่อยพิจารณาเปิดออเดอร์ครับ")
            parts.append("\n" + "="*45 + "\n")
        return "\n".join(parts)

    # =========================================================================
    # หมวด 2.5: Money Management, Position Sizing, ควรซื้อกี่ตัว / แบ่งเงินยังไง
    # =========================================================================
    if any(k in msg_lower for k in ["กี่ตัว", "แบ่งเงิน", "position size", "money management", "จัดพอร์ต", "ซื้อเท่าไหร่"]):
        return (
            "💼 **สูตรบริหารเงินหน้าตัก (Money Management & Position Sizing):**\n\n"
            "**1. ควรมีหุ้นกี่ตัวในพอร์ต?**\n"
            "- สำหรับมือใหม่และผู้เทรด Swing Trade แนะนำถือ **3 - 5 ตัว** ไม่เกินนี้\n"
            "- ถ้าน้อยกว่า 3 ตัว: ความเสี่ยงจะกระจุกตัวเกินไป\n"
            "- ถ้ามากกว่า 5 ตัว: จะดูแลไม่ทั่วถึงและติดตามสถานะได้ยาก\n\n"
            "**2. สัดส่วนเงินต่อหุ้น 1 ตัว (Position Size):**\n"
            "- แบ่งเงินลงทุนเป็นก้อน ก้อนละประมาณ **15% - 20% ของพอร์ต** ต่อหุ้น 1 ตัว\n"
            "- มีเงินสดสำรองติดพอร์ตไว้เสมออย่างน้อย 10% - 20% เพื่อรอจังหวะตลาดปรับฐาน\n\n"
            "**3. กฎความเสี่ยง 1-2% (Risk per Trade):**\n"
            "- หากการเทรดครั้งนั้นชน Stop Loss เงินที่เสียไปไม่ควรเกิน **1% - 2% ของมูลค่าพอร์ตรวม**\n"
            "- เช่น พอร์ต $10,000 การขาดทุนใน 1 ไม้ไม่ควรเกิน $100 - $200 ครับ"
        )

    # =========================================================================
    # หมวด 3: ตรวจสุขภาพพอร์ต
    # =========================================================================
    if is_asking_portfolio:
        holdings = inspect_portfolio(send_alerts=False)
        if not holdings:
            return (
                "🛡️ **รายงานตรวจสุขภาพพอร์ตของคุณ:**\n\n"
                "ขณะนี้ในพอร์ตของคุณ **ยังไม่มีหุ้นที่ถืออยู่** ครับ (พอร์ตเป็นเงินสด 100%)\n\n"
                "✨ **ข้อดี:** คุณมีสภาพคล่องเต็มมือพร้อมเข้าซื้อเมื่อเกิดโอกาสที่ได้เปรียบสูง\n"
                "👉 แนะนำให้ไปที่แท็บ **'🔭 3. แมวมองสแกนหุ้น'** เพื่อดูหุ้นที่เกิดสัญญาณซื้อในวันนี้ หรือพิมพ์ชื่อหุ้นที่สนใจมาปรึกษาผมได้เลยครับ"
            )
        
        summary = get_portfolio_summary(holdings)
        lines = [
            f"🛡️ **รายงานตรวจสุขภาพพอร์ตประจำวัน (ถืออยู่ {summary['total_positions']} ตัว):**\n"
        ]
        if summary['th_positions'] > 0:
            lines.append(f"• 🇹🇭 **พอร์ตหุ้นไทย:** มูลค่ารวม ฿{summary['th_value']:,.2f} | กำไร/ขาดทุน: {summary['th_pnl']:+,.2f} บาท ({summary['th_pnl_pct']:+.2f}%)")
        if summary['us_positions'] > 0:
            lines.append(f"• 🇺🇸 **พอร์ตหุ้นสหรัฐฯ:** มูลค่ารวม ${summary['us_value']:,.2f} | กำไร/ขาดทุน: ${summary['us_pnl']:+,.2f} ({summary['us_pnl_pct']:+.2f}%)")
        
        lines.append(f"• สถานะโดยรวม: 🟢 มีกำไร {summary['winning_count']} ตัว | 🔴 ขาดทุน {summary['losing_count']} ตัว\n")
        lines.append("**คำแนะนำในการบริหารพอร์ต:**")
        
        has_alert = False
        for h in holdings:
            action = h.get("action_code", "HOLD_NORMAL")
            disp = h.get("display_symbol", h.get("symbol"))
            curr = h.get("currency", "$")
            if action in ["STOP_LOSS", "TAKE_PROFIT_1", "TAKE_PROFIT_2", "TRAILING_STOP"]:
                has_alert = True
                lines.append(f"⚠️ **{disp}**: {h.get('action_text')} -> {h.get('advice')}")
        
        if not has_alert:
            lines.append("✅ หุ้นทุกตัวในพอร์ตยังเคลื่อนไหวในกรอบปกติ ไม่มีตัวใดหลุด Stop Loss หรือถึงเป้าทำกำไร ให้ถือครองตามแผนต่อไป (Let profit run)")
        
        return "\n".join(lines)

    # =========================================================================
    # หมวด 4: สแกนหาหุ้นน่าซื้อ
    # =========================================================================
    if is_asking_recommendation:
        scout_txt = get_scout_recommendations_text()
        return (
            "🔭 **รายงานสแกนหาจังหวะซื้อ (AI Swing Trade Scout):**\n\n"
            f"{scout_txt}\n\n"
            "💡 **กลยุทธ์การคัดเลือกหุ้นสำหรับมือใหม่:**\n"
            "1. **เน้น R/R สูง:** เลือกเฉพาะตัวที่มี Risk/Reward Ratio ตั้งแต่ 1:2.0 ขึ้นไป\n"
            "2. **กระจายความเสี่ยง:** อย่าลงเงินในหุ้นตัวเดียวเกิน 15-20% ของพอร์ต\n"
            "3. **มีวินัย Stop Loss:** ตั้ง Stop Loss ทันทีที่ส่งคำสั่งซื้อ ห้ามถัวเฉลี่ยหุ้นขาลงเด็ดขาดครับ"
        )

    # =========================================================================
    # หมวด 5: ความรู้เรื่อง Stop Loss / Cut Loss / ขาดทุนเท่าไหร่ควรขาย
    # =========================================================================
    if any(k in msg_lower for k in ["stop loss", "cut loss", "คัท", "ตัดขาดทุน", "ขาดทุนเท่าไหร่"]):
        return (
            "🛑 **หลักการตั้งจุดตัดขาดทุน (Stop Loss) สไตล์มืออาชีพ:**\n\n"
            "**1. กฎทอง 3 ข้อของ Stop Loss:**\n"
            "- **ห้ามขาดทุนเกิน -5% ถึง -7% ต่อไม้:** สำหรับการเทรด Swing Trade การจำกัดการขาดทุนไว้ที่ -5% จะช่วยให้คุณฟื้นตัวกลับมาได้ง่ายมาก\n"
            "- **ความจริงทางคณิตศาสตร์ของการขาดทุน:**\n"
            "  • ขาดทุน -5% -> ต้องทำกำไร +5.3% เพื่อเท่าทุน (ง่ายมาก)\n"
            "  • ขาดทุน -10% -> ต้องทำกำไร +11.1% เพื่อเท่าทุน\n"
            "  • ขาดทุน -20% -> ต้องทำกำไร +25.0% เพื่อเท่าทุน\n"
            "  • ขาดทุน -50% -> ต้องทำกำไรถึง **+100% (เท่าตัว)** ถึงจะได้ทุนคืน!\n\n"
            "**2. วิธีหาจุดวาง Stop Loss:**\n"
            "- วางไว้ **ใต้แนวรับสำคัญ (Swing Low ล่าสุด)** เล็กน้อย\n"
            "- หรือวางไว้ **ใต้เส้นค่าเฉลี่ย EMA 20 / EMA 50** ที่ราคาเพิ่งเด้งขึ้นมา\n\n"
            "**3. สรุปคำแนะนำ:**\n"
            "> 'Cut Loss เจ็บนิดเดียว แต่รักษาเงินต้นไว้สร้างชีวิตใหม่ได้เสมอ' ทุกครั้งที่เปิดออเดอร์ ให้ตั้ง Stop Loss ไว้ในระบบทันที ไม่ต้องรอลุ้นหน้าจอครับ! 🛡️"
        )

    # =========================================================================
    # หมวด 6: Trailing Stop / ล็อกกำไร
    # =========================================================================
    if any(k in msg_lower for k in ["trailing", "เทรลลิ่ง", "ล็อกกำไร", "กำไรแล้วย่อ"]):
        return (
            "🔒 **Trailing Stop คืออะไร และทำงานอย่างไร?**\n\n"
            "**Trailing Stop** คือระบบ 'เลื่อนจุด Stop Loss ตามราคาสูงสุดที่หุ้นวิ่งขึ้นไป' เพื่อล็อกผลกำไรไม่ให้กลายเป็นขาดทุน:\n\n"
            "• **การทำงานตัวอย่าง:**\n"
            "  1. คุณซื้อหุ้นที่ $100 ตั้ง Stop Loss ไว้ที่ $95\n"
            "  2. ราคาหุ้นพุ่งขึ้นไปถึง $115 (กำไร +15%)\n"
            "  3. ระบบ Trailing Stop จะขยับจุดขายขึ้นมาล็อกไว้ที่ $110 (เช่น ต่ำกว่าจุดสูงสุด 4-5%)\n"
            "  4. ถ้าราคาพุ่งต่อไปที่ $120 จุดล็อกกำไรจะขยับตามไปที่ $115 โดยอัตโนมัติ\n"
            "  5. เมื่อราคาย่อตัวลงมาแตะ $115 ระบบจะส่งคำสั่งขายเพื่อล็อกกำไรเข้ากระเป๋าทันที!\n\n"
            "💡 **ข้อดี:** ช่วยให้คุณ 'Let Profits Run' ปล่อยให้กำไรวิ่งไปได้ไกลที่สุด โดยไม่ต้องกังวลว่ากำไรจะหดหายเมื่อตลาดกลับทิศครับ"
        )

    # =========================================================================
    # หมวด 7: Money Management, Position Sizing, ควรซื้อกี่ตัว / แบ่งเงินยังไง
    # =========================================================================
    if any(k in msg_lower for k in ["กี่ตัว", "แบ่งเงิน", "position size", "money management", "จัดพอร์ต", "ซื้อเท่าไหร่"]):
        return (
            "💼 **สูตรบริหารเงินหน้าตัก (Money Management & Position Sizing):**\n\n"
            "**1. ควรมีหุ้นกี่ตัวในพอร์ต?**\n"
            "- สำหรับมือใหม่และผู้เทรด Swing Trade แนะนำถือ **3 - 5 ตัว** ไม่เกินนี้\n"
            "- ถ้าน้อยกว่า 3 ตัว: ความเสี่ยงจะกระจุกตัวเกินไป\n"
            "- ถ้ามากกว่า 5 ตัว: จะดูแลไม่ทั่วถึงและติดตามสถานะได้ยาก\n\n"
            "**2. สัดส่วนเงินต่อหุ้น 1 ตัว (Position Size):**\n"
            "- แบ่งเงินลงทุนเป็นก้อน ก้อนละประมาณ **15% - 20% ของพอร์ต** ต่อหุ้น 1 ตัว\n"
            "- มีเงินสดสำรองติดพอร์ตไว้เสมออย่างน้อย 10% - 20% เพื่อรอจังหวะตลาดปรับฐาน\n\n"
            "**3. กฎความเสี่ยง 1-2% (Risk per Trade):**\n"
            "- หากการเทรดครั้งนั้นชน Stop Loss เงินที่เสียไปไม่ควรเกิน **1% - 2% ของมูลค่าพอร์ตรวม**\n"
            "- เช่น พอร์ต $10,000 การขาดทุนใน 1 ไม้ไม่ควรเกิน $100 - $200 ครับ"
        )

    # =========================================================================
    # หมวด 8: อินดิเคเตอร์ EMA, RSI, Volume, Breakout
    # =========================================================================
    if any(k in msg_lower for k in ["ema", "rsi", "indicator", "อินดิเคเตอร์", "เส้นค่าเฉลี่ย", "วอลุ่ม", "volume"]):
        return (
            "📊 **เจาะลึกอินดิเคเตอร์สำคัญของ AI Trading Office:**\n\n"
            "**1. เส้น Exponential Moving Average (EMA):**\n"
            "- **EMA 20 (เส้นฟ้า):** ทิศทางระยะสั้น (1 เดือน) หุ้นแกร่งมักย่อแตะ EMA 20 แล้วเด้งกลับ\n"
            "- **EMA 50 (เส้นส้ม):** ทิศทางระยะกลาง (2-3 เดือน) เป็นแนวรับหลักของรอบการสวิงเทรด\n"
            "- **EMA 200 (เส้นม่วง):** เส้นแบ่งระหว่าง 'ขาขึ้น' กับ 'ขาลง' ถ้าราคาอยู่เหนือ EMA 200 ถือเป็นตลาดกระทิง (Bull Market)\n\n"
            "**2. RSI (Relative Strength Index 14):**\n"
            "- **ต่ำกว่า 30 (Oversold):** มีแรงขายมากเกินไป ใกล้ถึงจุดดีดตัวกลับ\n"
            "- **40 - 50:** จุดรับยอดนิยมของหุ้นขาขึ้นที่กำลังพักตัว (Pullback)\n"
            "- **สูงกว่า 70 (Overbought):** มีแรงซื้อมากเกินไป ระวังการย่อตัวพักฐาน ไม่ควรไล่ราคาซื้อ\n\n"
            "**3. Volume Spike (วอลุ่มผิดปกติ):**\n"
            "- วันที่ราคาเบรกเอาท์ทะลุแนวต้าน ควรมีวอลุ่มสูงกว่าค่าเฉลี่ย 1.5x - 2.0x ขึ้นไป เพื่อยืนยันว่าสถาบันหรือเจ้ามือร่วมดันราคาจริงครับ"
        )

    # =========================================================================
    # หมวด 9: คำแนะนำการใช้งาน Webull สำหรับตลาดสหรัฐฯ
    # =========================================================================
    if any(k in msg_lower for k in ["webull", "สหรัฐ", "us stock", "ตลาดอเมริกา", "เวลาเปิด"]):
        return (
            "📱 **เทคนิคการเทรดหุ้นสหรัฐฯ บนแอป Webull สำหรับมือใหม่:**\n\n"
            "**1. เวลาเปิดตลาด (ตามเวลาประเทศไทย):**\n"
            "- ตลาดเปิดจริง (Regular Hours): **20:30 น. - 03:00 น.** (ฤดูร้อน) หรือ 21:30 น. - 04:00 น. (ฤดูหนาว)\n"
            "- มี Pre-market ให้เทรดก่อนตั้งแต่ 15:00 น. และ After-hours ถึง 07:00 น.\n\n"
            "**2. วิธีตั้งออเดอร์แล้วเข้านอนได้เลย (ไม่ต้องเฝ้าดึก):**\n"
            "1. เข้าแอป Webull ค้นหาหุ้นที่ต้องการ เช่น `NVDA`, `ARM`\n"
            "2. กด **Trade** -> เลือก **Limit** (ใส่ราคาที่ต้องการซื้อตามที่ AI แนะนำ)\n"
            "3. เลื่อนลงมาเปิดสวิตช์ **Take Profit / Stop Loss (TP/SL)**\n"
            "4. ใส่ราคา Stop Loss และราคา Target 1 ที่ AI วางแผนให้\n"
            "5. เลือก Time-in-Force เป็น **GTC (Good 'Til Canceled)** เพื่อให้คำสั่งอยู่รอจนกว่าราคาจะถึง\n"
            "6. กด Buy -> จากนั้นปิดแอปเข้านอนได้เลย ระบบของ Webull จะดูแลความเสี่ยงให้คุณเอง 100% ครับ!"
        )

    # =========================================================================
    # หมวด 10: คำตอบสำหรับการสนทนาทั่วไป / ขอบคุณ / ตอบรับ
    # =========================================================================
    if any(k in msg_lower for k in ["ขอบคุณ", "แต๊ง", "ok", "โอเค", "เข้าใจ", "เยี่ยม", "ดีมาก", "สุดยอด"]):
        return (
            "ยินดีมากๆ ครับ! 😊 การลงทุนที่มีวินัย วางแผนจุด Stop Loss และเลือกเฉพาะจังหวะที่ Risk/Reward ได้เปรียบ จะทำให้คุณเทรดได้อย่างมีความสุขและไม่เครียดครับ\n\n"
            "หากคุณมีข้อสงสัยเรื่องหุ้นตัวไหน หรืออยากให้ผมช่วยตรวจกราฟและวางแผนเทรดตัวใด สามารถพิมพ์ชื่อหุ้นมาคุยกันได้ตลอดเวลาเลยนะครับ! 🏛️✨"
        )

    # คำตอบวิเคราะห์เริ่มต้น
    return (
        "สวัสดีครับ! ผมคือ **Chief AI Advisor** ที่ปรึกษาการลงทุนประจำ AI Trading Office 🏛️\n\n"
        "ผมพร้อมร่วมวางแผนและให้คำปรึกษาแก่คุณในทุกมิติของการเทรด:\n"
        "• 📊 **วิเคราะห์หุ้นรายตัว:** พิมพ์ชื่อหุ้น เช่น `PTT`, `DELTA`, `NVDA`, `ARM` เพื่อดูจุดเข้าซื้อ, Stop Loss, เป้ากำไร และ Risk/Reward\n"
        "• ⚖️ **วิเคราะห์อัตราส่วน Risk/Reward:** ปรึกษาเรื่องความคุ้มค่าและ Win Rate ของไม้ที่สนใจ\n"
        "• 🛡️ **ตรวจสุขภาพพอร์ต:** พิมพ์ว่า `ตรวจพอร์ต` เพื่อให้ AI เช็คสัญญาณขายของหุ้นที่คุณถืออยู่\n"
        "• 🔭 **สแกนหาหุ้นน่าซื้อ:** พิมพ์ว่า `แนะนำหุ้นวันนี้` เพื่อดูหุ้นที่กราฟสวยและทรงพลัง\n"
        "• 📱 **แนะนำวิธีส่งคำสั่งบน Webull & Streaming:** ถามวิธีตั้ง Stop Loss หรือ Limit Order ได้ตลอดเวลา\n\n"
        "ลองพิมพ์คำถามหรือชื่อหุ้นที่คุณกำลังสนใจมาได้เลยครับ!"
    )
