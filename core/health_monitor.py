import threading
import time
from datetime import datetime, timedelta

from core.tools import extract_number, parse_db_timestamp

CHECK_INTERVAL_SECS = 1800  # 30 phút — không cần soi liên tục, dữ liệu đổi chậm
ALERT_COOLDOWN = timedelta(hours=12)  # tránh lặp lại cùng 1 cảnh báo nhiều lần trong ngày


class HealthMonitor:
    """Định kỳ soi health_logs, tự lên tiếng (qua speak_callback) nếu phát hiện bất thường —
    khác với chỉ ghi log thụ động (Sơn phải hỏi mới biết), đây là phần khiến log thực sự có
    tác dụng: EVA chủ động cảnh báo mà không cần được hỏi trước.

    Category lọc theo SUBSTRING (không đòi khớp tuyệt đối) vì category do AI tự đặt tên mỗi
    lần ghi log (xem core/tools.py log_health), không phải danh sách cố định — "giấc ngủ" và
    "ngủ" đều phải bắt được."""

    def __init__(self, db, speak_callback, check_interval_secs=CHECK_INTERVAL_SECS):
        self.db = db
        self.speak = speak_callback
        self.check_interval = check_interval_secs
        self._last_alert = {}  # rule_name -> datetime lần cảnh báo gần nhất

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        print(f"[Health] Theo dõi sức khoẻ chủ động đã bật (kiểm tra mỗi {self.check_interval // 60} phút)")

    def _loop(self):
        while True:
            try:
                self._check()
            except Exception as e:
                print(f"[Health] Lỗi kiểm tra sức khoẻ: {e}")
            time.sleep(self.check_interval)

    def _fire(self, rule_name, message):
        last = self._last_alert.get(rule_name)
        if last and datetime.now() - last < ALERT_COOLDOWN:
            return
        self._last_alert[rule_name] = datetime.now()
        print(f"[Health] Cảnh báo chủ động ({rule_name}): {message}")
        if self.speak:
            self.speak(message)

    def _recent_matching(self, keyword, within):
        """Lấy các log gần đây có category chứa keyword (không phân biệt hoa/thường),
        trong khoảng thời gian `within` tính từ hiện tại."""
        rows = self.db.get_health_logs(limit=50)  # đủ rộng để bắt hết log vài ngày gần nhất
        now = datetime.now()
        matched = []
        for category, content, ts in rows:
            if keyword not in category.lower():
                continue
            parsed = parse_db_timestamp(ts)
            if parsed and now - parsed <= within:
                matched.append((content, parsed))
        return matched

    def _check(self):
        self._check_sleep()
        self._check_symptom_repeat()

    def _check_sleep(self):
        """Ngủ dưới 6 tiếng từ 2 đêm trở lên trong 3 ngày gần nhất -> nhắc ngủ sớm hơn."""
        matched = self._recent_matching("ngủ", timedelta(days=3))
        values = [v for v, _t in ((extract_number(c), t) for c, t in matched) if v is not None]
        low_nights = [v for v in values if v < 6]
        if len(low_nights) >= 2:
            self._fire(
                "sleep_low",
                "Sơn ơi, mấy đêm gần đây tôi thấy Sơn ngủ dưới 6 tiếng liên tục — cố gắng đi ngủ sớm hơn nhé.",
            )

    def _check_symptom_repeat(self):
        """Báo triệu chứng từ 2 lần trở lên trong 24 giờ -> nhắc nghỉ ngơi/đi khám."""
        matched = self._recent_matching("triệu chứng", timedelta(hours=24))
        if len(matched) >= 2:
            self._fire(
                "symptom_repeat",
                "Sơn ơi, tôi thấy Sơn báo triệu chứng khó chịu vài lần trong hôm nay rồi — "
                "nếu không đỡ thì Sơn nên nghỉ ngơi hoặc đi khám nhé.",
            )
