import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional
from config import get_currency_symbol, clean_display_symbol, get_market_tag

def create_stock_chart(df: pd.DataFrame, symbol: str, 
                       cost_price: Optional[float] = None, 
                       stop_loss: Optional[float] = None, 
                       target_1: Optional[float] = None, 
                       target_2: Optional[float] = None) -> go.Figure:
    """สร้างกราฟแท่งเทียน Candlestick สไตล์ TradingView พร้อมเส้นเทคนิคัล (รองรับทั้งหุ้นไทยและสหรัฐฯ)"""
    curr = get_currency_symbol(symbol)
    disp = clean_display_symbol(symbol)
    tag = get_market_tag(symbol)

    # ดึงข้อมูล 90 วันล่าสุดเพื่อให้เห็นชัดเจน
    plot_df = df.tail(90).copy()

    # สร้างกราฟ 2 ชั้น: ชั้นบนคือกราฟราคา + EMA, ชั้นล่างคือ RSI และ Volume
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08, 
        row_heights=[0.75, 0.25]
    )

    # 1. แท่งเทียน Candlestick
    fig.add_trace(
        go.Candlestick(
            x=plot_df.index,
            open=plot_df['Open'],
            high=plot_df['High'],
            low=plot_df['Low'],
            close=plot_df['Close'],
            name="Price",
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        ),
        row=1, col=1
    )

    # 2. เส้นค่าเฉลี่ย EMA
    if "EMA_20" in plot_df.columns:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["EMA_20"], mode='lines', line=dict(color='#ff9800', width=1.5), name='EMA 20 (สั้น)'), row=1, col=1)
    if "EMA_50" in plot_df.columns:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["EMA_50"], mode='lines', line=dict(color='#2196f3', width=1.5), name='EMA 50 (สวิง)'), row=1, col=1)
    if "EMA_200" in plot_df.columns:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["EMA_200"], mode='lines', line=dict(color='#9c27b0', width=2), name='EMA 200 (เทรนด์ใหญ่)'), row=1, col=1)

    # 3. ระดับราคาสำคัญ (Cost, Stop Loss, Targets) หากระบุ
    if cost_price:
        fig.add_hline(y=cost_price, line_dash="dash", line_color="#00e676", annotation_text=f"ต้นทุน {curr}{cost_price:.2f}", row=1, col=1)
    if stop_loss:
        fig.add_hline(y=stop_loss, line_dash="dot", line_color="#ff1744", annotation_text=f"Stop Loss {curr}{stop_loss:.2f}", row=1, col=1)
    if target_1:
        fig.add_hline(y=target_1, line_dash="dash", line_color="#ffea00", annotation_text=f"เป้ากำไร 1 {curr}{target_1:.2f}", row=1, col=1)
    if target_2:
        fig.add_hline(y=target_2, line_dash="dash", line_color="#00b0ff", annotation_text=f"เป้ากำไร 2 {curr}{target_2:.2f}", row=1, col=1)

    # 4. กราฟ RSI ด้านล่าง
    if "RSI" in plot_df.columns:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["RSI"], mode='lines', line=dict(color='#e040fb', width=1.5), name='RSI 14'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    fig.update_layout(
        title=f"📈 กราฟเทคนิคัล {tag} : {disp} (Daily Swing Setup)",
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=520,
        margin=dict(l=40, r=40, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

