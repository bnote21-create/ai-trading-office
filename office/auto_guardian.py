import sys
import time
import threading
from datetime import datetime
from typing import Dict, Any
from office.portfolio_guardian import inspect_portfolio

class AutoGuardian:
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if not hasattr(sys, "_ai_office_auto_guardian") or sys._ai_office_auto_guardian is None:
                instance = super(AutoGuardian, cls).__new__(cls)
                instance._init_guardian()
                sys._ai_office_auto_guardian = instance
            return sys._ai_office_auto_guardian

    def _init_guardian(self):
        self.is_running = False
        self.interval_seconds = 60  # ตรวจเช็คราคาทุกๆ 60 วินาที
        self.thread = None
        self.last_check_time = None
        self.check_count = 0
        self.last_log = "ยังไม่ได้เริ่มต้นระบบ"

    def _run_loop(self):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 AI Auto Guardian เริ่มเฝ้าพอร์ตเรียลไทม์อัตโนมัติ (ตรวจทุก {self.interval_seconds} วินาที)...")
        while self.is_running:
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # เรียกตรวจพอร์ตและยิง Alert อัตโนมัติเมื่อถึงจุด TP/SL
                results = inspect_portfolio(send_alerts=True)
                self.last_check_time = now_str
                self.check_count += 1
                self.last_log = f"ตรวจเช็คสำเร็จเมื่อ {now_str} (ตรวจสอบ {len(results)} รายการ)"
            except Exception as e:
                self.last_log = f"เกิดข้อผิดพลาดในการตรวจเช็ค: {e}"
                print(f"[Auto Guardian Error] {e}")

            # หลับตามช่วงเวลาที่กำหนด โดยแบ่งเป็นช่วงสั้นๆ เพื่อให้หยุดหรือเปลี่ยนความถี่ได้ทันที
            for _ in range(self.interval_seconds):
                if not self.is_running:
                    break
                time.sleep(1)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🛑 AI Auto Guardian หยุดการทำงานแล้ว")

    def start(self, interval_seconds: int = 60) -> bool:
        """เริ่มการทำงานระบบเฝ้าพอร์ตอัตโนมัติในเบื้องหลัง"""
        with self._lock:
            self.interval_seconds = max(10, interval_seconds)
            if self.is_running and self.thread and self.thread.is_alive():
                return True
            self.is_running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True, name="AutoGuardianThread")
            self.thread.start()
            return True

    def stop(self) -> bool:
        """หยุดการทำงานระบบเฝ้าพอร์ตอัตโนมัติ"""
        with self._lock:
            self.is_running = False
            return False

    def set_interval(self, interval_seconds: int):
        """ปรับเปลี่ยนความถี่ในการตรวจเช็ค"""
        with self._lock:
            self.interval_seconds = max(10, interval_seconds)

    def get_status(self) -> Dict[str, Any]:
        """ดึงสถานะการทำงานปัจจุบัน"""
        is_alive = self.thread.is_alive() if self.thread else False
        return {
            "is_running": self.is_running and is_alive,
            "interval_seconds": self.interval_seconds,
            "last_check_time": self.last_check_time,
            "check_count": self.check_count,
            "last_log": self.last_log
        }

# สร้างอ็อบเจ็กต์ Singleton ประจำระบบ
guardian = AutoGuardian()

def start_guardian(interval_seconds: int = 60) -> bool:
    return guardian.start(interval_seconds)

def stop_guardian() -> bool:
    return guardian.stop()

def set_guardian_interval(interval_seconds: int):
    guardian.set_interval(interval_seconds)

def get_guardian_status() -> Dict[str, Any]:
    return guardian.get_status()
