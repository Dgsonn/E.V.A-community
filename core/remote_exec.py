import threading
import time

PENDING_STALE_SECS = 30  # không thấy laptop hỏi thăm quá lâu -> coi như đang mất kết nối


class RemoteExecutor:
    """Cầu nối để 1 tool (mở app/link) được thực thi TRÊN LAPTOP thay vì server — dùng khi
    lệnh đến từ dashboard (source="text") trong lúc laptop_idle_agent.py đang kết nối, thay
    vì luôn chạy trên server như trước. core/tools.py gọi request() và chặn chờ kết quả;
    core/web_interface.py gọi take_pending()/report_result() từ 2 route mà laptop_idle_agent.py
    poll tới. Chỉ có đúng 1 instance dùng chung (biến `executor` cuối file)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending = None  # {"id", "action", "args"} — chỉ 1 lệnh chờ tại 1 thời điểm
        self._next_id = 0
        self._events = {}   # request id -> threading.Event
        self._results = {}  # request id -> str
        self._last_laptop_seen = None
        # Hàng đợi riêng cho lệnh "gửi rồi thôi" (vd main.py's on_proactive_alert đẩy câu
        # nhắc nhở/cảnh báo chủ động sang loa laptop) — KHÔNG dùng chung ô _pending với
        # request()/report_result() ở trên, vì loại đó cần chờ kết quả trả về (khớp theo id),
        # còn push() không cần ai xác nhận gì cả, tránh 2 luồng (AIBrain gọi tool vs
        # ReminderScheduler/HealthMonitor chủ động) giẫm lên nhau nếu trùng thời điểm.
        self._push_queue = []

    def mark_laptop_seen(self):
        self._last_laptop_seen = time.time()

    @property
    def laptop_connected(self):
        return (
            self._last_laptop_seen is not None
            and (time.time() - self._last_laptop_seen) <= PENDING_STALE_SECS
        )

    def request(self, action, args, timeout=8):
        """Gọi từ core/tools.py trên luồng worker của ai_brain — chặn tới khi laptop báo kết
        quả hoặc hết thời gian chờ. Trả None nếu hết giờ (nơi gọi tự lo fallback), không bao
        giờ raise.

        Lưu ý: AIBrain chỉ có ĐÚNG 1 luồng xử lý tuần tự (core/ai_brain.py's _process_loop) —
        trong lúc chờ ở đây, MỌI câu hỏi khác (voice/text/web_voice) đều bị chặn lại chờ theo,
        không xử lý song song được. timeout thấp (8s thay vì 15s trước đây) chỉ giảm bớt thời
        gian chặn tối đa — laptop_idle_agent.py poll mỗi 2s nên trường hợp bình thường vẫn dư
        thời gian phản hồi. Muốn xử lý song song thật sự cần tách AIBrain sang mô hình đa luồng,
        rủi ro cao hơn hẳn (self.history hiện không có khoá, xử lý đồng thời dễ làm lẫn thứ tự
        hội thoại) — chưa đáng đánh đổi cho quy mô 1 người dùng hiện tại."""
        with self._lock:
            self._next_id += 1
            req_id = self._next_id
            self._pending = {"id": req_id, "action": action, "args": args}
            event = threading.Event()
            self._events[req_id] = event

        got_result = event.wait(timeout)

        with self._lock:
            self._events.pop(req_id, None)
            if not got_result:
                # Không kịp trả lời — dọn luôn ô đang chờ nếu vẫn còn đúng lệnh này (laptop có
                # thể vẫn lấy đúng lúc timeout vừa xảy ra, lúc đó cứ để report_result tự lo).
                if self._pending and self._pending["id"] == req_id:
                    self._pending = None
                return None
            return self._results.pop(req_id, None)

    def push(self, action, args):
        """Xếp 1 lệnh 'gửi rồi thôi' (không chờ laptop báo kết quả) — dùng để đẩy thông báo/
        nhắc nhở chủ động sang laptop khi đang kết nối. Không có 'id' vì không cần
        report_result() khớp lại (xem take_pending())."""
        with self._lock:
            self._push_queue.append({"action": action, "args": args})

    def take_pending(self):
        """Gọi từ route GET /api/laptop_pending_command (laptop poll định kỳ) — ưu tiên lấy
        lệnh trong hàng đợi push() trước (không giới hạn 1 lệnh như _pending), rồi mới tới
        lệnh request()/report_result() đang chờ (nếu có)."""
        with self._lock:
            if self._push_queue:
                return self._push_queue.pop(0)
            cmd = self._pending
            self._pending = None
            return cmd

    def report_result(self, request_id, result):
        """Gọi từ route POST /api/laptop_command_result."""
        with self._lock:
            self._results[request_id] = result
            event = self._events.pop(request_id, None)
        if event:
            event.set()


executor = RemoteExecutor()
