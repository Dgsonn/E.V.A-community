import ctypes
import threading
import time
from ctypes import wintypes
from datetime import datetime, timedelta

from core.database import get_db

POLL_INTERVAL_SECS = 300  # 5 phút — đủ để bắt được lúc vừa hết 1 khoảng im lặng dài
MIN_SLEEP_HOURS = 3.0   # dưới mức này không tính là "ngủ" — có thể chỉ đi ra ngoài/nghỉ giải lao
MAX_SLEEP_HOURS = 14.0  # trên mức này nghi ngờ máy tắt/không dùng vì lý do khác (đi công tác...),
                        # không log để tránh làm sai lệch thống kê giấc ngủ

# --- Phát hiện hoạt động liên tục không nghỉ: TÍN HIỆU NGƯỢC với suy đoán ngủ ở trên — máy
# HOẠT ĐỘNG LIÊN TỤC (thay vì im lặng). Không giới hạn khung giờ — áp dụng cả ngày lẫn đêm để
# nhắc nghỉ ngơi nói chung, không chỉ riêng cảnh báo thức trắng đêm. ---
BREAK_THRESHOLD_SECS = 1800     # im lặng >= 30 phút mới tính là "đã nghỉ", ngắt chuỗi hoạt động liên tục
CONTINUOUS_ACTIVITY_ALERT_HOURS = 6.0  # hoạt động liên tục >= 6 tiếng không nghỉ mới đáng nhắc
NIGHT_HOURS = (0, 6)  # khung giờ tính là "đêm" — chỉ dùng để chọn câu nói + có ghi thêm vào
                      # health_logs (giấc ngủ 0 tiếng) hay không, không dùng để giới hạn cảnh báo
ALERT_COOLDOWN = timedelta(hours=12)  # chống cảnh báo lặp lại liên tục trong cùng 1 chuỗi hoạt động


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds():
    """Số giây kể từ lần cuối có thao tác bàn phím/chuột (Windows only)."""
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return millis / 1000.0


class ActivityMonitor:
    """Suy đoán giấc ngủ từ hành vi dùng máy — không cần Sơn tự khai báo. 2 tín hiệu:
      1. Thời gian máy "im lặng" (GetLastInputInfo) — bắt trường hợp máy vẫn bật cả đêm
         nhưng không ai chạm bàn phím/chuột.
      2. Khoảng cách thời gian thực giữa 2 lần poll (time.time()) — bắt trường hợp máy
         thực sự vào sleep/ngủ đông (lúc đó GetTickCount tạm dừng đếm hoặc không đáng tin cậy,
         nhưng time.time() sau khi máy tỉnh lại vẫn phản ánh đúng thời gian thực đã trôi qua).
    Ghi trực tiếp vào health_logs với category "giấc ngủ" — dùng chung hạ tầng với log thủ
    công (HealthMonitor, get_health_summary) mà không cần sửa gì thêm ở đó.

    Giới hạn thật: đây chỉ là SUY ĐOÁN từ việc không dùng máy, không phải đo giấc ngủ thật —
    Sơn rời máy đi làm việc khác, đi công tác, hay tắt máy vì lý do khác cũng bị tính nhầm là
    "ngủ". Chỉ nên coi là ước tính tham khảo, không thay thế tự báo qua giọng nói khi cần
    chính xác. Cũng chỉ bắt được khoảng ngủ xảy ra TRONG LÚC EVA đang chạy nền — nếu tắt hẳn
    app qua đêm rồi mở lại sáng hôm sau thì khoảng đó không được ghi nhận.

    Thêm 1 việc (không liên quan giấc ngủ): cảnh báo KHÔNG THẤY HOẠT ĐỘNG — quá lâu không thấy
    ai chạm máy và không nghe thấy tiếng người nói (mark_presence(), gọi từ VoiceEngine/main.py)
    -> EVA hỏi han -> không ai phản hồi -> nhắn người thân. Xem _check_inactivity()."""

    def __init__(self, poll_interval_secs=POLL_INTERVAL_SECS, speak_callback=None, address_term="Sơn",
                 inactivity_cfg=None, on_ask=None, notify_family=None):
        self.poll_interval = poll_interval_secs
        self.db = get_db()
        self.speak = speak_callback
        self.address_term = address_term
        self._last_idle_seconds = 0.0
        self._last_check_time = time.time()
        self._active_since = time.time()  # mốc bắt đầu chuỗi hoạt động liên tục hiện tại (chưa nghỉ)
        self._last_continuous_alert = None
        self._last_presence = time.time()  # coi như vừa có người lúc EVA khởi động — tránh báo động ngay

        cfg = inactivity_cfg or {}
        self._inactivity_enabled = bool(cfg.get("enabled", True))
        self._morning_deadline = self._parse_hm(cfg.get("morning_deadline", "10:00"))
        self._day_start = self._parse_hm(cfg.get("day_start", "07:00"))
        self._day_end = self._parse_hm(cfg.get("day_end", "21:00"))
        self._max_idle = timedelta(hours=float(cfg.get("max_idle_hours", 4)))
        self._response_timeout = timedelta(minutes=float(cfg.get("response_timeout_mins", 15)))
        self.on_ask = on_ask
        self.notify_family = notify_family
        self._checkin = None            # {"asked_at", "asks", "reason"} khi đang chờ phản hồi
        self._morning_done_date = None  # đã xét luật "buổi sáng" hôm nay chưa
        self._idle_alerted = False      # đã hỏi cho chuỗi im lặng ban ngày hiện tại chưa

    @staticmethod
    def _parse_hm(value):
        h, m = str(value).strip().split(":")
        return int(h), int(m)

    def mark_presence(self):
        """Có dấu hiệu người ở nhà: nghe thấy tiếng nói (không lưu nội dung) hoặc có lệnh gửi
        tới EVA. Gọi từ VoiceEngine.on_speech_heard và main.py's on_user_input."""
        self._last_presence = time.time()

    def _last_active_time(self):
        """Mốc hoạt động gần nhất: lấy cái MUỘN HƠN giữa thao tác bàn phím/chuột và tiếng người."""
        return max(time.time() - get_idle_seconds(), self._last_presence)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        if self._inactivity_enabled:
            threading.Thread(target=self._inactivity_loop, daemon=True).start()
            print(f"[Activity] Cảnh báo không thấy hoạt động đã bật (ban ngày im lặng quá {self._max_idle.total_seconds() / 3600:g} tiếng, hoặc quá {self._morning_deadline[0]:02d}:{self._morning_deadline[1]:02d} chưa thấy dậy)")
        print(f"[Activity] Suy đoán giấc ngủ tự động đã bật (poll mỗi {self.poll_interval // 60} phút)")

    def _loop(self):
        while True:
            try:
                self._check()
            except Exception as e:
                print(f"[Activity] Lỗi kiểm tra hoạt động máy: {e}")
            time.sleep(self.poll_interval)

    def _check(self):
        now = time.time()
        idle = get_idle_seconds()

        idle_hours = self._last_idle_seconds / 3600
        gap_hours = (now - self._last_check_time) / 3600

        # Vừa hết 1 khoảng im lặng dài (idle vừa rồi lớn, giờ vừa có thao tác mới -> idle nhỏ lại)
        just_woke_from_idle = idle_hours >= MIN_SLEEP_HOURS and idle < 60
        # Khoảng cách giữa 2 lần poll lớn bất thường (bình thường chỉ ~poll_interval) -> máy đã
        # sleep/ngủ đông giữa chừng, không phải do chương trình bị treo (loop vẫn tự tiếp tục)
        just_resumed_from_gap = gap_hours >= MIN_SLEEP_HOURS

        hours, reason = 0.0, ""
        if just_resumed_from_gap and gap_hours >= idle_hours:
            hours, reason = gap_hours, "khoảng máy sleep/ngủ đông"
        elif just_woke_from_idle:
            hours, reason = idle_hours, "thời gian máy không có thao tác"

        if hours and hours <= MAX_SLEEP_HOURS:
            self.db.save_health_log("giấc ngủ", f"{hours:.1f} tiếng (ước tính từ {reason})")
            print(f"[Activity] Suy đoán vừa ngủ dậy — {hours:.1f} tiếng ({reason}), đã ghi vào health_logs")

        self._check_continuous_activity(now, idle)

        self._last_idle_seconds = idle
        self._last_check_time = now

    def _check_continuous_activity(self, now, idle):
        """Tín hiệu ngược với suy đoán ngủ ở trên: máy HOẠT ĐỘNG LIÊN TỤC không nghỉ (thay vì
        im lặng) -> nhắc Sơn nghỉ ngơi. Không giới hạn khung giờ — áp dụng cả ngày lẫn đêm."""
        if idle >= BREAK_THRESHOLD_SECS:
            # vừa có 1 khoảng nghỉ thực sự (>=30 phút không thao tác) -> ngắt chuỗi, tính lại từ đây
            self._active_since = now
            return

        active_hours = (now - self._active_since) / 3600
        if active_hours >= CONTINUOUS_ACTIVITY_ALERT_HOURS:
            is_night = NIGHT_HOURS[0] <= datetime.now().hour < NIGHT_HOURS[1]
            self._fire_continuous_activity(active_hours, is_night)

    def _fire_continuous_activity(self, active_hours, is_night):
        if self._last_continuous_alert and datetime.now() - self._last_continuous_alert < ALERT_COOLDOWN:
            return
        self._last_continuous_alert = datetime.now()

        if is_night:
            # Đúng khung giờ đêm -> ghi thêm vào health_logs (category "giấc ngủ", 0 tiếng) để
            # get_health_summary/trend phản ánh đúng đêm này thay vì im lặng như không có gì.
            self.db.save_health_log(
                "giấc ngủ", f"0 tiếng - thức trắng đêm (phát hiện hoạt động liên tục {active_hours:.0f} tiếng)"
            )
            message = (
                f"{self.address_term} ơi, tôi thấy {self.address_term} dùng máy liên tục khoảng {active_hours:.0f} tiếng không nghỉ, "
                "có vẻ thức trắng đêm rồi — nên tranh thủ chợp mắt một chút nhé."
            )
        else:
            # Ban ngày -> chỉ nhắc nghỉ, không ghi nhầm vào dữ liệu giấc ngủ
            message = (
                f"{self.address_term} ơi, {self.address_term} đã làm việc liên tục khoảng {active_hours:.0f} tiếng không nghỉ rồi — "
                "đứng dậy đi lại, uống nước hoặc nghỉ mắt một chút nhé."
            )

        print(f"[Activity] Cảnh báo hoạt động liên tục: {message}")
        if self.speak:
            self.speak(message)

    # ------------------------------------------------------------------
    # Cảnh báo không thấy hoạt động -> hỏi han -> báo người thân
    # ------------------------------------------------------------------
    def _inactivity_loop(self):
        while True:
            try:
                self._check_inactivity()
            except Exception as e:
                print(f"[Activity] Lỗi kiểm tra không hoạt động: {e}")
            time.sleep(60)

    def _at(self, now, hm):
        return now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)

    def _check_inactivity(self):
        now = datetime.now()
        last_active = datetime.fromtimestamp(self._last_active_time())

        if self._checkin:
            self._follow_up_checkin(now, last_active)
            return

        # Luật 1 — buổi sáng: quá morning_deadline mà từ 4 giờ sáng chưa thấy hoạt động gì
        deadline = self._at(now, self._morning_deadline)
        if now >= deadline and self._morning_done_date != now.date():
            self._morning_done_date = now.date()
            if last_active < now.replace(hour=4, minute=0, second=0, microsecond=0):
                self._start_checkin(now, f"quá {deadline:%H:%M} sáng chưa thấy dậy")
                return

        # Luật 2 — ban ngày: im lặng liên tục quá max_idle (chỉ tính trong day_start..day_end)
        day_start = self._at(now, self._day_start)
        in_day = day_start <= now <= self._at(now, self._day_end)
        # tính im lặng từ đầu ngày trở đi — giấc ngủ đêm qua không được tính là "im lặng bất thường"
        idle_for = now - max(last_active, day_start)
        if idle_for < self._max_idle:
            self._idle_alerted = False  # đã có hoạt động lại -> chuỗi im lặng mới
        elif in_day and not self._idle_alerted:
            self._idle_alerted = True
            self._start_checkin(now, f"không thấy hoạt động từ {last_active:%H:%M}")

    def _ask_text(self):
        return (f"{self.address_term} ơi, {self.address_term} có ổn không ạ? "
                f"Nếu ổn thì nói với tôi một câu nhé.")

    def _notified_text(self):
        return f"{self.address_term} ơi, tôi đã nhắn cho người thân để họ gọi hỏi thăm."

    def fixed_phrases(self):
        """Câu EVA có thể nói — để TTSEngine.preload() tạo sẵn giọng đọc lúc còn mạng."""
        return [self._ask_text(), self._notified_text()]

    def _ask(self):
        msg = self._ask_text()
        print(f"[Activity] Hỏi han: {msg}")
        if self.speak:
            self.speak(msg)
        if self.on_ask:
            self.on_ask()

    def _start_checkin(self, now, reason):
        self._checkin = {"asked_at": now, "asks": 1, "reason": reason}
        self._ask()

    def _follow_up_checkin(self, now, last_active):
        c = self._checkin
        # Có tiếng nói/thao tác sau khi hỏi -> người dùng ổn, không làm gì thêm
        if last_active > c["asked_at"]:
            print("[Activity] Đã có phản hồi sau khi hỏi han — không báo người thân.")
            self._checkin = None
            return
        waited = now - c["asked_at"]
        if c["asks"] == 1 and waited >= self._response_timeout / 2:
            c["asks"] = 2  # hỏi thêm 1 lần giữa chừng, phòng lần đầu không nghe thấy
            self._ask()
            return
        if waited >= self._response_timeout:
            self._checkin = None
            text = (f"EVA không thấy {self.address_term} hoạt động ({c['reason']}), đã hỏi "
                    f"{c['asks']} lần nhưng không có phản hồi. Nên gọi điện kiểm tra.")
            self.db.log_event("INACTIVITY_ALERT", text)
            sent = self.notify_family(text) if self.notify_family else False
            print(f"[Activity] Không có phản hồi — {'đã' if sent else 'CHƯA'} báo người thân.")
            if sent and self.speak:
                self.speak(self._notified_text())
