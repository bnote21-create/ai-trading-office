@echo off
chcp 65001 >nul
title AI Trading Office - Real-time Auto Guardian
cd /d "%~dp0"

echo ========================================================
echo   🤖 เริ่มระบบ AI Auto Guardian เฝ้าพอร์ตเรียลไทม์...
echo ========================================================
echo.
echo ระบบจะตรวจราคาหุ้นในพอร์ตอัตโนมัติทุกๆ 60 วินาที
echo เมื่อราคาแตะจุด Stop Loss หรือ Take Profit
echo ระบบจะส่งข้อความเข้า Telegram และ LINE ทันที!
echo.
echo (สามารถย่อหน้าต่างนี้ไว้เพื่อเฝ้าตลาดตลอดเวลาได้เลยครับ)
echo ========================================================
echo.

python -c "import time; from office.auto_guardian import start_guardian, get_guardian_status; from office.notifier import broadcast_alert; broadcast_alert('🤖 [AI Office] เริ่มต้นระบบเฝ้าพอร์ตเรียลไทม์อัตโนมัติแล้วครับ! (ตรวจราคาทุก 60 วินาที)'); start_guardian(60); print('Auto Guardian is active. Press Ctrl+C to stop.'); [time.sleep(1) for _ in iter(int, 1)]"

pause

