import os
import yfinance as yf
from typing import Dict, Any, Optional
from config import (
    GEMINI_API_KEY, 
    is_thai_stock, 
    normalize_symbol, 
    clean_display_symbol, 
    get_currency_symbol, 
    get_market_tag
)
from office.market_scout import fetch_stock_data, calculate_indicators, evaluate_swing_setup

def get_fundamental_summary(symbol: str) -> Dict[str, Any]:
    """ดึงข้อมูลพื้นฐานบริษัทคร่าวๆ จาก yfinance (รองรับทั้งหุ้นไทยและสหรัฐฯ)"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        return {
            "name": info.get("shortName", clean_display_symbol(symbol)),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "pe_ratio": info.get("trailingPE", None),
            "forward_pe": info.get("forwardPE", None),
            "market_cap": info.get("marketCap", None),
            "52w_high": info.get("fiftyTwoWeekHigh", None),
            "52w_low": info.get("fiftyTwoWeekLow", None),
            "target_mean_price": info.get("targetMeanPrice", None),
            "recommendation": info.get("recommendationKey", "N/A")
        }
    except Exception:
        return {
            "name": clean_display_symbol(symbol),
            "sector": "N/A",
            "industry": "N/A",
            "pe_ratio": None,
            "forward_pe": None,
            "market_cap": None,
            "52w_high": None,
            "52w_low": None,
            "target_mean_price": None,
            "recommendation": "N/A"
        }

def analyze_with_ai(symbol: str, tech_data: Dict[str, Any], fund_data: Dict[str, Any]) -> str:
    """ใช้ Gemini AI ในการวิเคราะห์สรุปแผนการเทรดสำหรับมือใหม่ (หากมี API Key)"""
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip():
        return generate_rule_based_ai_commentary(symbol, tech_data, fund_data)

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY.strip())

        curr = get_currency_symbol(symbol)
        disp_sym = clean_display_symbol(symbol)
        market_tag = get_market_tag(symbol)
        app_name = "Streaming หรือ Webull Thailand" if is_thai_stock(symbol) else "Webull US"

        prompt = f"""
คุณเป็นหัวหน้านักวิเคราะห์เทรดดิ้ง (Chief Trading Officer) ประจำ AI Trading Office
กำลังให้คำแนะนำกับ "นักลงทุนมือใหม่ที่ไม่เคยเล่นหุ้นมาก่อน" ที่เทรด {market_tag} สไตล์ Swing Trade (ถือครองระดับหลายวันถึง 2-4 สัปดาห์) ผ่านแอป {app_name}

ข้อมูลหุ้น {disp_sym} ({fund_data.get('name')}):
- ตลาด: {market_tag}
- อุตสาหกรรม/กลุ่มธุรกิจ: {fund_data.get('sector')} / {fund_data.get('industry')}
- ราคาปัจจุบัน: {curr}{tech_data['price']:.2f} (เปลี่ยนแปลงวันนี้: {tech_data['change_pct']:+.2f}%)
- แนวโน้มหลัก: ราคา vs EMA 200 ({curr}{tech_data['ema200']}), EMA 50 ({curr}{tech_data['ema50']}), EMA 20 ({curr}{tech_data['ema20']})
- โมเมนตัม RSI: {tech_data['rsi']}
- ปริมาณการซื้อขายเทียบค่าเฉลี่ย: {tech_data['vol_ratio']}x
- กลยุทธ์ทางเทคนิคที่พบ: {tech_data['setup']}
- สัญญาณเบื้องต้น: {tech_data['signal']} (คะแนน {tech_data['score']}/100)
- จุดตัดขาดทุนคำนวณไว้: {curr}{tech_data['stop_loss']}
- เป้าหมายกำไร 1: {curr}{tech_data['target_1']} | เป้าหมาย 2: {curr}{tech_data['target_2']}
- Risk/Reward Ratio: 1:{tech_data['rr_ratio']}

กรุณาสรุปบทวิเคราะห์ภาษาไทย โดยแบ่งเป็นหัวข้อดังนี้ (ใช้ภาษาเป็นกันเอง ชัดเจน มือใหม่อ่านแล้วเข้าใจทันที):
1. 💡 สรุปความเห็นของ AI (ควรซื้อเลย / รอจังหวะย่อ / หลีกเลี่ยง)
2. 📈 ข้อดีและจุดเด่นของจังหวะนี้
3. ⚠️ ความเสี่ยงและสิ่งที่ต้องระวัง
4. 📱 ขั้นตอนการตั้งคำสั่งบนแอป {app_name} สำหรับมือใหม่ (อธิบายว่าควรตั้ง Limit Order ซื้อที่เท่าไหร่, ตั้ง Stop Loss ตรงไหน)
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}, fallback to rule-based")
        return generate_rule_based_ai_commentary(symbol, tech_data, fund_data)

def generate_rule_based_ai_commentary(symbol: str, tech: Dict[str, Any], fund: Dict[str, Any]) -> str:
    """ระบบสร้างบทวิเคราะห์อัจฉริยะอัตโนมัติ (Rule-based Expert Analyst) รองรับทั้งไทยและสหรัฐฯ"""
    signal = tech["signal"]
    price = tech["price"]
    sl = tech["stop_loss"]
    tp1 = tech["target_1"]
    tp2 = tech["target_2"]
    rr = tech["rr_ratio"]
    curr = get_currency_symbol(symbol)
    disp_sym = clean_display_symbol(symbol)
    app_name = "Streaming หรือ Webull TH" if is_thai_stock(symbol) else "Webull"

    if signal == "BUY":
        summary = f"🟢 **แนะนำพิจารณาเข้าซื้อแบบแบ่งไม้ (Accumulate)** หุ้น {disp_sym} มีจังหวะ Swing Trade ที่สวยงาม ความเสี่ยงต่ำเมื่อเทียบกับโอกาสทำกำไร"
        risk_note = f"หากราคาหลุด {curr}{sl:.2f} ต้องมีวินัยในการตัดขาดทุน (Cut Loss) ทันที ไม่ควรถือถัวเฉลี่ยขาลง"
        action = f"1. เข้าแอป {app_name} ค้นหา `{disp_sym}`\n2. ตั้งคำสั่งซื้อช่วงราคา {curr}{price * 0.995:.2f} - {curr}{price:.2f}\n3. ตั้งคำสั่ง Stop Loss ล่วงหน้าที่ {curr}{sl:.2f}\n4. วางเป้าขายทำกำไรครึ่งหนึ่ง (50%) ที่ {curr}{tp1:.2f} และส่วนที่เหลือลุ้นต่อที่ {curr}{tp2:.2f}"
    elif signal == "WATCH":
        summary = f"🟡 **แนะนำให้เฝ้าจับตาดูต่อ (Watchlist)** ยังไม่ถึงจังหวะเข้าซื้อที่ดีที่สุด ควรรอให้ราคาสร้างฐานหรือย่อลงมาใกล้แนวรับ"
        risk_note = "การเข้าซื้อตอนนี้อาจมีความผันผวนสูง หรือต้องทนถือรอนาน"
        action = f"ยังไม่ต้องรีบเคาะซื้อ ให้ตั้ง Alert เตือนราคาที่ {curr}{tech['ema20']:.2f} เพื่อรอดูแรงเด้งกลับ"
    elif signal == "OVERBOUGHT":
        summary = f"🟠 **เตือน: หุ้นขึ้นมาร้อนแรงเกินไป (Overbought)** RSI สูงจัด {tech['rsi']} เสี่ยงต่อการโดนแรงเทขายทำกำไรระยะสั้น"
        risk_note = "มือใหม่มักจะติดดอยจากการไล่ซื้อหุ้นที่วิ่งขึ้นมาแรงเกินไป"
        action = f"ห้ามเคาะซื้อเด็ดขาด หากมีหุ้นในมืออยู่แล้วบน {app_name} ควรพิจารณาแบ่งขายทำกำไรบางส่วน"
    else:
        summary = f"🔴 **แนะนำหลีกเลี่ยง (Avoid)** หุ้น {disp_sym} ยังอยู่ในแนวโน้มอ่อนแอหรือขาลงใต้เส้นค่าเฉลี่ย"
        risk_note = "การเทรดหุ้นขาลงมักให้ผลตอบแทนต่ำและติดดอยได้ง่าย"
        action = "เก็บเงินสดไว้รอตัวที่มีแนวโน้มขาขึ้นชัดเจนจะปลอดภัยกว่า"

    report = f"""
### 💡 บทสรุปจาก AI Office ({get_market_tag(symbol)}):
{summary}

### 📊 รายละเอียดการวิเคราะห์:
- **กลยุทธ์ที่ตรวจพบ:** {tech['setup']}
- **อัตราส่วนผลตอบแทนต่อความเสี่ยง (R:R):** 1:{rr} (เสี่ยง 1 เพื่อลุ้นได้ {rr})
- **จุดตัดขาดทุน (Stop Loss):** {curr}{sl:.2f} (-{((price - sl)/price)*100:.1f}%)
- **เป้าหมายกำไร 1 (Take Profit 1):** {curr}{tp1:.2f} (+{((tp1 - price)/price)*100:.1f}%)
- **เป้าหมายกำไร 2 (Take Profit 2):** {curr}{tp2:.2f} (+{((tp2 - price)/price)*100:.1f}%)

### ⚠️ ความเสี่ยงที่ต้องระวัง:
{risk_note}

### 📱 แผนการตั้งคำสั่งบน {app_name}:
{action}
"""
    return report

def analyze_stock(symbol: str, market: str = "AUTO") -> Optional[Dict[str, Any]]:
    """วิเคราะห์หุ้นตัวเดียวแบบครบวงจร (รองรับทั้งหุ้นไทยและสหรัฐฯ)"""
    normalized = normalize_symbol(symbol, market)
    df = fetch_stock_data(normalized)
    if df is None:
        # หากไม่พบ ให้ลองตัวตรงข้าม
        alt = normalized.replace(".BK", "") if normalized.endswith(".BK") else f"{normalized}.BK"
        df = fetch_stock_data(alt)
        if df is not None:
            normalized = alt
        else:
            return None

    df = calculate_indicators(df)
    tech = evaluate_swing_setup(normalized, df)
    fund = get_fundamental_summary(normalized)
    ai_comment = analyze_with_ai(normalized, tech, fund)

    return {
        "symbol": normalized,
        "display_symbol": clean_display_symbol(normalized),
        "market_tag": get_market_tag(normalized),
        "currency": get_currency_symbol(normalized),
        "technical": tech,
        "fundamental": fund,
        "ai_commentary": ai_comment,
        "df": df
    }
