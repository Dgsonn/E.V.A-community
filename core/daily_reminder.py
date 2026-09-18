import threading
import time
from datetime import datetime

CHECK_INTERVAL_SECS = 30  # kiểm tra khá thường xuyên — vì đây là lịch bác sĩ dặn, không được lỡ


class DailyReminder:
    """Nhắc cố định theo giờ trong ngày, lặp lại hàng ngày vô thời hạn — khác hẳn
    HealthMonitor/ActivityMonitor (dựa trên dữ liệu/hành vi đã quan sát được), đây chỉ đơn
    giản là báo thức theo đồng hồ. Dùng cho lịch bác sĩ yêu cầu (dậy ăn sáng, uống thuốc) nên
    thiết kế để KHÔNG bỏ lỡ dù app khởi động trễ hơn giờ hẹn: kiểm tra "đã qua giờ hẹn hôm nay
    chưa" thay vì chỉ khớp đúng chính xác 1 phút, vì lỡ đúng phút đó (app chưa chạy, máy đang
    khởi động, poll bị trễ...) coi như mất cả ngày."""

    def __init__(self, reminder_time, message, speak_callback, check_interval_secs=CHECK_INTERVAL_SECS):
        self.hour, self.minute = self._parse_time(reminder_time)
        self.message = message
        self.speak = speak_callback
        self.check_interval = check_interval_secs
        self._last_fired_date = None

    @staticmethod
    def _parse_time(reminder_time):
        h, m = str(reminder_time).strip().split(":")
        return int(h), int(m)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        print(f"[Reminder] Nhắc hàng ngày đã bật lúc {self.hour:02d}:{self.minute:02d}")

    def _loop(self):
        while True:
            try:
                self._check()
            except Exception as e:
                print(f"[Reminder] Lỗi kiểm tra nhắc nhở: {e}")
            time.sleep(self.check_interval)

    def _check(self):
        now = datetime.now()
        if self._last_fired_date == now.date():
            return  # đã nhắc hôm nay rồi

        target = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if now >= target:
            self._last_fired_date = now.date()
            print(f"[Reminder] Nhắc hàng ngày: {self.message}")
            if self.speak:
                self.speak(self.message)
