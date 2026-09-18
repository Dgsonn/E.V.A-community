import subprocess
import threading
import time


class TempMonitor:
    """Theo dõi nhiệt độ GPU định kỳ qua nvidia-smi (không cần cài thêm gì, chỉ hỗ trợ GPU NVIDIA
    — CPU cần LibreHardwareMonitor riêng, chưa làm) — báo chủ động (nói qua TTS) nếu vượt ngưỡng
    cảnh báo, vì máy chạy 24/7 làm server nên cần biết sớm để tắt máy cho nguội, tránh hỏng phần
    cứng. Cùng kiểu thiết kế với DailyReminder (vòng lặp riêng, gọi speak_callback khi tới điều
    kiện), khác ở chỗ có thể báo lặp lại nhiều lần trong ngày nếu vẫn còn nóng."""

    def __init__(self, warning_c, speak_callback, check_interval_secs=120, recheck_interval_secs=600):
        self.warning_c = warning_c
        self.speak = speak_callback
        self.check_interval = check_interval_secs
        self.recheck_interval = recheck_interval_secs
        self._last_alert_time = 0
        self._is_hot = False

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        print(f"[Temp] Theo dõi nhiệt độ GPU đã bật (ngưỡng cảnh báo {self.warning_c}°C, kiểm tra mỗi {self.check_interval}s)")

    def _loop(self):
        while True:
            try:
                self._check()
            except Exception as e:
                print(f"[Temp] Lỗi kiểm tra nhiệt độ: {e}")
            time.sleep(self.check_interval)

    def _check(self):
        temp = get_gpu_temp()
        if temp is None:
            return
        now = time.time()
        if temp >= self.warning_c:
            # Cảnh báo ngay lần đầu vượt ngưỡng, sau đó lặp lại mỗi recheck_interval nếu vẫn còn
            # nóng — tránh nói liên tục mỗi lần kiểm tra khi nhiệt độ giữ nguyên trên ngưỡng.
            # Tự reset khi nguội lại dưới ngưỡng, lần sau vượt ngưỡng lại báo ngay từ đầu.
            if not self._is_hot or (now - self._last_alert_time) >= self.recheck_interval:
                self._is_hot = True
                self._last_alert_time = now
                message = f"Sơn ơi, GPU đang nóng {temp} độ C, vượt ngưỡng cảnh báo {self.warning_c} độ — nên tắt máy cho nguội bớt."
                print(f"[Temp] Cảnh báo: {message}")
                if self.speak:
                    self.speak(message)
        else:
            self._is_hot = False


def get_gpu_temp():
    """Đọc nhiệt độ GPU hiện tại (độ C) qua nvidia-smi — dùng chung bởi TempMonitor (theo dõi
    chủ động) và core/tools.py's get_system_status (tra cứu theo yêu cầu). Trả None nếu không
    đọc được (không phải máy có GPU NVIDIA, driver lỗi, hết thời gian chờ...), không bao giờ raise."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None
