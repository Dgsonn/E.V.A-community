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
      2. Khoảng cách thời gian thực giữa 2 lần poll (time.time()) — bắt trường hợp máy/laptop
         thực sự vào sleep/ngủ đông (lúc đó GetTickCount tạm dừng đếm hoặc không đáng tin cậy,
         nhưng time.time() sau khi máy tỉnh lại vẫn phản ánh đúng thời gian thực đã trôi qua).
    Ghi trực tiếp vào health_logs với category "giấc ngủ" — dùng chung hạ tầng với log thủ
    công (HealthMonitor, get_health_summary) mà không cần sửa gì thêm ở đó.

    Giới hạn thật: đây chỉ là SUY ĐOÁN từ việc không dùng máy, không phải đo giấc ngủ thật —
    Sơn rời máy đi làm việc khác, đi công tác, hay tắt máy vì lý do khác cũng bị tính nhầm là
    "ngủ". Chỉ nên coi là ước tính tham khảo, không thay thế tự báo qua giọng nói khi cần
    chính xác. Cũng chỉ bắt được khoảng ngủ xảy ra TRONG LÚC EVA đang chạy nền — nếu tắt hẳn
    app qua đêm rồi mở lại sáng hôm sau thì khoảng đó không được ghi nhận.

    Từ khi EVA chuyển sang chạy trên PC server riêng (không phải máy Sơn dùng hàng ngày),
    GetLastInputInfo cục bộ không còn phản ánh đúng việc Sơn có đang dùng máy hay không —
    server hầu như luôn "im lặng" dù Sơn đang làm việc bận rộn trên laptop. report_laptop_idle()
    nhận báo cáo định kỳ từ laptop_idle_agent.py chạy trên laptop, _effective_idle_seconds()
    gộp cả 2 nguồn (lấy giá trị nhỏ hơn = có hoạt động ở bất kỳ đâu đều tính) — nếu chưa có
    báo cáo nào (agent chưa chạy/mất mạng) thì tự rơi về đúng hành vi cũ (chỉ tính server)."""

    def __init__(self, poll_interval_secs=POLL_INTERVAL_SECS, speak_callback=None):
        self.poll_interval = poll_interval_secs
        self.db = get_db()
        self.speak = speak_callback
        self._last_idle_seconds = 0.0
        self._last_check_time = time.time()
        self._active_since = time.time()  # mốc bắt đầu chuỗi hoạt động liên tục hiện tại (chưa nghỉ)
        self._last_continuous_alert = None
        self._laptop_idle_seconds = None
        self._last_heartbeat_time = None
        self._heartbeat_stale_secs = poll_interval_secs * 2  # quá lâu không có báo cáo -> coi như agent không chạy

    def report_laptop_idle(self, idle_seconds):
        """Gọi từ core/web_interface.py mỗi khi laptop_idle_agent.py (chạy trên laptop) gửi
        heartbeat về — lưu lại để _effective_idle_seconds() gộp vào tín hiệu của server."""
        self._laptop_idle_seconds = float(idle_seconds)
        self._last_heartbeat_time = time.time()

    def _effective_idle_seconds(self):
        """Idle của server, gộp thêm idle của laptop (nếu có báo cáo gần đây) — lấy giá trị
        NHỎ HƠN vì chỉ cần 1 trong 2 máy có hoạt động là coi như Sơn đang dùng."""
        local_idle = get_idle_seconds()
        if (
            self._last_heartbeat_time is not None
            and (time.time() - self._last_heartbeat_time) <= self._heartbeat_stale_secs
        ):
            return min(local_idle, self._laptop_idle_seconds)
        return local_idle

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
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
        idle = self._effective_idle_seconds()

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
                f"Sơn ơi, tôi thấy Sơn dùng máy liên tục khoảng {active_hours:.0f} tiếng không nghỉ, "
                "có vẻ thức trắng đêm rồi — nên tranh thủ chợp mắt một chút nhé."
            )
        else:
            # Ban ngày -> chỉ nhắc nghỉ, không ghi nhầm vào dữ liệu giấc ngủ
            message = (
                f"Sơn ơi, Sơn đã làm việc liên tục khoảng {active_hours:.0f} tiếng không nghỉ rồi — "
                "đứng dậy đi lại, uống nước hoặc nghỉ mắt một chút nhé."
            )

        print(f"[Activity] Cảnh báo hoạt động liên tục: {message}")
        if self.speak:
            self.speak(message)
