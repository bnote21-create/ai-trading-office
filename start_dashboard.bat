@echo off
chcp 65001 >nul
title AI Trading Office - Web Dashboard

:: เปลี่ยนโฟลเดอร์มายังที่ตั้งของไฟล์นี้เสมอ
cd /d "%~dp0"

echo ========================================================
echo   🏛️ กำลังเริ่มต้น AI Trading Office Web Dashboard...
echo ========================================================
echo.
echo กำลังเปิดหน้าต่างเบราว์เซอร์ที่: http://localhost:8501
echo (หากเบราว์เซอร์ไม่เด้งขึ้นมาเอง คุณสามารถเปิดเว็บแล้วพิมพ์ http://localhost:8501 ได้เลยครับ)
echo.
echo ========================================================
echo.

:: สั่งเปิด Browser อัตโนมัติหลังจากรอ 2 วินาทีเพื่อให้ Server พร้อม
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8501"

:: รัน Streamlit ผ่าน Python โดยตรงเพื่อความเสถียร
python -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false

pause
