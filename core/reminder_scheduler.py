import threading
import time
from datetime import datetime

from core.tools import parse_db_timestamp

CHECK_INTERVAL_SECS = 15  # nhanh hơn DailyReminder (30s) vì có thể là hẹn giờ chỉ vài phút


class ReminderScheduler:
    """Nhắc nhở tuỳ ý do Sơn tự đặt qua tool set_reminder (core/tools.py) — khác
    core/daily_reminder.py (cố định, lặp lại hàng ngày theo giờ bác sĩ dặn), đây là nhắc
    ĐÚNG 1 LẦN vào thời điểm đã hẹn rồi thôi. Lưu trong bảng reminders (core/schema.sql) nên
    vẫn còn nếu EVA khởi động lại trước khi tới giờ hẹn."""

    def __init__(self, db, speak_callback, check_interval_secs=CHECK_INTERVAL_SECS):
        self.db = db
        self.speak = speak_callback
        self.check_interval = check_interval_secs

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        print(f"[Reminder] Bộ nhắc nhở tuỳ ý đã bật (kiểm tra mỗi {self.check_interval}s)")

    def _loop(self):
        while True:
            try:
                self._check()
            except Exception as e:
                print(f"[Reminder] Lỗi kiểm tra nhắc nhở: {e}")
            time.sleep(self.check_interval)

    def _check(self):
        now = datetime.now()
        for reminder_id, message, remind_at in self.db.get_pending_reminders():
            parsed = parse_db_timestamp(remind_at)
            if parsed and now >= parsed:
                self.db.mark_reminder_fired(reminder_id)
                print(f"[Reminder] Đã tới giờ nhắc: {message}")
                if self.speak:
                    self.speak(f"Sơn ơi, tới giờ {message} rồi.")
