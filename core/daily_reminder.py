import threading
import time
from datetime import datetime, timedelta

CHECK_INTERVAL_SECS = 30   # kiểm tra khá thường xuyên — vì đây là lịch bác sĩ dặn, không được lỡ
CATCH_UP_WINDOW = timedelta(hours=2)  # EVA khởi động trễ trong 2 tiếng sau giờ hẹn vẫn nhắc bù;
                                      # trễ hơn thì bỏ qua (nhắc thuốc sáng lúc 8 giờ tối là sai)
HEALTH_CATEGORY = "uống thuốc"
MORNING_END_HOUR = 11  # lần nhắc trước 11h sáng được mở đầu bằng lời chào buổi sáng + thời tiết

# Câu trả lời ngắn khi EVA vừa hỏi "uống thuốc chưa" — khớp nguyên câu để "tôi mệt rồi" không
# bị hiểu nhầm là "đã uống".
YES_EXACT = {"rồi", "rồi ạ", "rồi nhé", "có", "có ạ", "vâng", "vâng ạ", "ừ", "ừ rồi", "dạ", "dạ rồi"}
YES_PHRASES = ("uống rồi", "đã uống", "uống xong", "xong rồi", "vừa uống")
NO_PHRASES = ("chưa",)


class MedicationReminder:
    """Nhắc uống thuốc theo nhiều khung giờ cố định mỗi ngày (lịch bác sĩ dặn), rồi HỎI LẠI cho
    tới khi người dùng xác nhận đã uống:
      1. Tới giờ -> nhắc + hỏi "uống xong thì nói với tôi nhé", mở phiên nghe (không cần "dậy đi").
      2. Nghe "uống rồi" -> ghi health_logs "Đã uống".  Nghe "chưa" -> hẹn hỏi lại sau.
      3. Im lặng quá retry_mins -> hỏi lại; hỏi đủ max_asks lần vẫn không xác nhận -> ghi
         "Bỏ lỡ" và (tuỳ cấu hình) nhắn SMS cho người thân.
    Khác HealthMonitor/ActivityMonitor (dựa trên dữ liệu/hành vi), đây là báo thức theo đồng hồ."""

    def __init__(self, schedules, address_term, db, speak_callback, on_ask=None, notify_family=None,
                 retry_mins=15, max_asks=3, weather_callback=None, check_interval_secs=CHECK_INTERVAL_SECS):
        self.schedules = [(self._parse_time(s["time"]), s["message"]) for s in schedules]
        self.address_term = address_term
        self.db = db
        self.speak = speak_callback
        self.on_ask = on_ask                  # gọi sau mỗi lần hỏi — main.py mở phiên nghe
        self.notify_family = notify_family    # None = không báo người thân khi bỏ lỡ
        self.retry = timedelta(minutes=retry_mins)
        self.max_asks = max_asks
        # Lần nhắc buổi sáng (trước MORNING_END_HOUR) được mở đầu bằng lời chào + thời tiết.
        # weather_callback() trả 1 câu thời tiết hoặc None (mất mạng/chưa cài) — khi đó chỉ chào.
        self.weather_callback = weather_callback
        self.check_interval = check_interval_secs
        self._fired = {}    # "HH:MM" -> ngày đã nhắc gần nhất
        self._pending = {}  # "HH:MM" -> {"asks": int, "last_ask": datetime}
        self._lock = threading.Lock()

    @staticmethod
    def _parse_time(value):
        h, m = str(value).strip().split(":")
        return int(h), int(m)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
        slots = ", ".join(f"{h:02d}:{m:02d}" for (h, m), _ in self.schedules)
        print(f"[Medication] Nhắc uống thuốc đã bật lúc {slots} (hỏi lại mỗi {int(self.retry.total_seconds() // 60)} phút, tối đa {self.max_asks} lần)")

    @property
    def has_pending(self):
        return bool(self._pending)

    def _loop(self):
        while True:
            try:
                self._check()
            except Exception as e:
                print(f"[Medication] Lỗi kiểm tra nhắc thuốc: {e}")
            time.sleep(self.check_interval)

    def _say(self, text):
        print(f"[Medication] {text}")
        if self.speak:
            self.speak(text)
        if self.on_ask:
            self.on_ask()

    def _check(self):
        now = datetime.now()
        for (h, m), message in self.schedules:
            slot = f"{h:02d}:{m:02d}"
            if self._fired.get(slot) == now.date():
                continue
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now < target:
                continue
            self._fired[slot] = now.date()
            if now - target > CATCH_UP_WINDOW:
                continue  # khởi động quá trễ so với giờ hẹn — không nhắc bù
            with self._lock:
                self._pending[slot] = {"asks": 1, "last_ask": now}
            if h < MORNING_END_HOUR:
                self._greet()
            self._say(self._first_ask(message))

        with self._lock:
            due = [(slot, p) for slot, p in self._pending.items() if now - p["last_ask"] >= self.retry]
        for slot, p in due:
            if p["asks"] >= self.max_asks:
                self._mark_missed(slot)
            else:
                with self._lock:
                    p["asks"] += 1
                    p["last_ask"] = now
                self._say(self._re_ask(slot))

    def _greet(self):
        # Nói tách riêng khỏi câu nhắc thuốc: câu chào cố định đã được tạo sẵn giọng đọc (phát
        # được cả khi mất mạng), còn câu thời tiết đổi mỗi ngày nên chỉ có khi có mạng.
        weather = None
        if self.weather_callback:
            try:
                weather = self.weather_callback()
            except Exception as e:
                print(f"[Medication] Không lấy được thời tiết: {e}")
        greeting = self._greeting_text()
        if self.speak:
            print(f"[Medication] {greeting} {weather or ''}")
            self.speak(greeting)
            if weather:
                self.speak(weather)

    def _greeting_text(self):
        return f"Chào buổi sáng {self.address_term}."

    def _mark_missed(self, slot):
        with self._lock:
            p = self._pending.pop(slot, None)
        if not p:
            return
        self.db.save_health_log(HEALTH_CATEGORY, f"Bỏ lỡ — buổi {slot} (không xác nhận sau {p['asks']} lần nhắc)")
        print(f"[Medication] Không xác nhận uống thuốc buổi {slot} sau {p['asks']} lần nhắc")
        if self.notify_family:
            self.notify_family(f"{self.address_term} chưa xác nhận uống thuốc buổi {slot} (EVA đã nhắc {p['asks']} lần).")

    def fixed_phrases(self):
        """Mọi câu EVA có thể nói — để TTSEngine.preload() tạo sẵn giọng đọc lúc còn mạng."""
        mins = int(self.retry.total_seconds() // 60)
        out = [self._greeting_text(),
               f"Vậy {self.address_term} uống ngay nhé, {mins} phút nữa tôi hỏi lại.",
               f"Tốt quá, tôi ghi lại là {self.address_term} đã uống thuốc rồi nhé."]
        for (h, m), message in self.schedules:
            slot = f"{h:02d}:{m:02d}"
            out.append(self._first_ask(message))
            out.append(self._re_ask(slot))
        return out

    def _first_ask(self, message):
        return f"{message.format(ten=self.address_term)} {self.address_term} uống xong thì nói “uống rồi” với tôi nhé."

    def _re_ask(self, slot):
        return f"{self.address_term} ơi, {self.address_term} đã uống thuốc buổi {slot} chưa ạ?"

    def handle_reply(self, text):
        """Gọi từ main.py với mọi câu người dùng nói khi đang chờ xác nhận. Trả về câu EVA nên
        nói lại nếu câu này là câu trả lời về thuốc, None nếu không liên quan (để AI xử lý)."""
        if not self._pending:
            return None
        t = text.lower().strip(" .,!?")
        if any(p in t for p in NO_PHRASES):
            with self._lock:
                for p in self._pending.values():
                    p["last_ask"] = datetime.now()
            mins = int(self.retry.total_seconds() // 60)
            return f"Vậy {self.address_term} uống ngay nhé, {mins} phút nữa tôi hỏi lại."
        if t in YES_EXACT or any(p in t for p in YES_PHRASES):
            with self._lock:
                slots, self._pending = list(self._pending), {}
            stamp = datetime.now().strftime("%H:%M")
            for slot in slots:
                self.db.save_health_log(HEALTH_CATEGORY, f"Đã uống — buổi {slot} (xác nhận lúc {stamp})")
            return f"Tốt quá, tôi ghi lại là {self.address_term} đã uống thuốc rồi nhé."
        return None
