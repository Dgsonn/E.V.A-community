import sys
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

import base64
import cv2
import yaml
import threading
import time
from core.ai_brain import AIBrain
from core.tts_engine import TTSEngine
from core.voice_engine import VoiceEngine
from core.database import get_db
from core.web_interface import WebInterface
from core.face_engine import FaceEngine
from core.health_monitor import HealthMonitor
from core.activity_monitor import ActivityMonitor
from core.daily_reminder import MedicationReminder
from core.reminder_scheduler import ReminderScheduler
from core.temp_monitor import TempMonitor
from core import notifier, tools
from core.voice_engine import DEFAULT_EMERGENCY_WORDS

CAMERA_ON_TRIGGERS = ["mở camera", "bật camera", "hiện camera", "hiển thị camera"]
CAMERA_OFF_TRIGGERS = ["tắt camera", "đóng camera", "ẩn camera"]

# Load cấu hình từ file YAML
with open("config/settings.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# =========================================================
# HÀM CHẠY CHÍNH (MAIN LOOP)
# =========================================================
def run():
    app_start_time = time.time()
    db = get_db()
    db.log_event("APP_START", "EVA started")

    # Khởi tạo các module
    # Camera là tính năng phụ, chỉ mở khi được yêu cầu (xem ensure_camera/release_camera) —
    # dùng để nhận diện chủ nhân, không hiển thị lên đâu cả
    # Cách EVA gọi người dùng chính — đổi qua config/settings.yaml (user.address_term),
    # dùng chung cho TTS (câu preload) và các module cảnh báo/nhắc nhở chủ động bên dưới.
    address_term = config.get("user", {}).get("address_term", "Sơn")

    cap_holder = [None]
    tts = TTSEngine(config)
    ai_brain = AIBrain(config)
    voice = VoiceEngine(config)
    face_engine = FaceEngine()

    is_owner_flag = [None]  # None = chưa xác minh, True/False = kết quả nhận diện gần nhất
    face_check_busy = [False]
    show_camera = [False]
    shutdown_event = threading.Event()

    if not face_engine.has_owner:
        print("[FACE] Chưa đăng ký khuôn mặt chủ nhân — chạy 'python enroll_face.py' để bật tính năng này")

    def ensure_camera():
        if cap_holder[0] is None:
            # DSHOW mở nhanh (~1s) thay vì MSMF mặc định (~10s+)
            cap = cv2.VideoCapture(config["camera"]["index"], cv2.CAP_DSHOW)
            if not cap.isOpened():
                print(f"[CAMERA] Không mở được camera (index={config['camera']['index']}) — "
                      "kiểm tra lại camera.index trong config/settings.yaml hoặc camera có đang cắm/dùng được không.")
            cap_holder[0] = cap
        return cap_holder[0]

    def release_camera():
        if cap_holder[0] is not None:
            cap_holder[0].release()
            cap_holder[0] = None

    def run_face_check(frame_copy):
        face_check_busy[0] = True
        try:
            is_owner_flag[0] = face_engine.is_owner(frame_copy)
        finally:
            face_check_busy[0] = False

    # Kết nối TTS -> STT để tránh mic nhận tiếng TTS (mute khi TTS phát)
    try:
        tts.register_on_start(voice.pause_listening)
        tts.register_on_end(voice.resume_listening)
        voice.on_interrupt = tts.stop  # nghe "dừng lại" trong lúc TTS đang nói -> dừng ngay
    except Exception:
        pass

    # Callback khi AI phản hồi (trả lời câu hỏi trực tiếp — ai_brain.py đã tự lưu
    # conversation_history rồi nên ở đây KHÔNG lưu lại, tránh trùng 2 lần).
    def on_ai_response(text):
        print(f"\n[EVA]: {text}") # In ra Terminal để theo dõi
        tts.speak(text)

    # Callback cho các cảnh báo/nhắc nhở CHỦ ĐỘNG (health/activity/medication/reminder/SOS) —
    # khác on_ai_response ở chỗ những nơi này gọi thẳng speak_callback, không đi qua
    # ai_brain.ask() nên phải tự lưu vào lịch sử. wait_turn=True: xếp hàng nếu EVA đang nói dở,
    # không được mất câu nhắc thuốc/cảnh báo.
    def on_proactive_alert(text):
        print(f"\n[EVA]: {text}")
        db.save_conversation("assistant", text)
        tts.speak(text, wait_turn=True)

    # Kêu cứu: gọi từ VoiceEngine (nghe "cứu tôi"... kể cả chưa đánh thức) hoặc khi gõ lệnh.
    # Trấn an ngay tại chỗ trước, gửi SMS ở luồng riêng (có thể mất vài giây, thử lại nếu lỗi
    # mạng), rồi báo lại kết quả thật — không bao giờ nói "đã báo" khi chưa gửi được.
    # Câu cố định (không sinh bằng AI) — để tạo sẵn giọng đọc lúc khởi động, phát được cả khi mất mạng.
    sos_phrases = {
        "start": f"{address_term} đừng lo, tôi đang báo cho người thân ngay.",
        "sent": f"Tôi đã nhắn cho người thân rồi, {address_term} cố gắng giữ bình tĩnh nhé.",
        "unconfigured": (f"Tôi chưa được cài số điện thoại người thân nên chưa nhắn được. "
                         f"{address_term} hãy gọi 115 hoặc gọi to cho hàng xóm nhé."),
        "failed": (f"Tôi chưa nhắn được cho người thân vì lỗi mạng. "
                   f"{address_term} hãy gọi 115 hoặc gọi to cho hàng xóm nhé."),
    }

    def trigger_sos(heard):
        db.log_event("SOS", f"Nghe thấy: {heard}")
        on_proactive_alert(sos_phrases["start"])

        def send():
            status = notifier.send_sos(heard)
            if status == "recent":
                return  # vừa gửi chưa đầy 1 phút — đã nói kết quả ở lần trước
            on_proactive_alert(sos_phrases[status])

        threading.Thread(target=send, daemon=True).start()

    safety_cfg = config.get("safety", {})
    emergency_words = [str(w).lower() for w in safety_cfg.get("emergency_words", DEFAULT_EMERGENCY_WORDS)]

    # Theo dõi sức khoẻ chủ động — tự lên tiếng khi phát hiện bất thường trong health_logs
    # (vd ngủ ít liên tục), không cần Sơn hỏi trước.
    health_monitor = HealthMonitor(db, speak_callback=on_proactive_alert, address_term=address_term)
    health_monitor.start()

    # Suy đoán giấc ngủ tự động từ hành vi dùng máy (không cần Sơn tự khai) — tự ghi vào
    # health_logs cùng category "giấc ngủ", health_monitor phía trên đọc chung dữ liệu này.
    # speak_callback dùng cho cảnh báo thức trắng đêm (tín hiệu ngược: hoạt động liên tục
    # không nghỉ, thay vì im lặng).
    # Thêm cảnh báo không thấy hoạt động (safety.inactivity): hỏi han -> không phản hồi -> SMS người thân.
    activity_monitor = ActivityMonitor(
        speak_callback=on_proactive_alert,
        address_term=address_term,
        inactivity_cfg=safety_cfg.get("inactivity", {}),
        on_ask=voice.open_session,
        notify_family=notifier.notify,
    )
    activity_monitor.start()

    # Nhắc uống thuốc theo nhiều khung giờ (health.medication_reminders) + hỏi lại tới khi xác
    # nhận "uống rồi" (health.medication_confirm). Message có thể chứa "{ten}" = address_term.
    health_cfg = config.get("health", {})
    schedules = health_cfg.get("medication_reminders") or [{
        "time": health_cfg.get("daily_reminder_time", "07:00"),
        "message": health_cfg.get("daily_reminder_message", "{ten} ơi, đã đến giờ dậy ăn sáng và uống thuốc rồi đó."),
    }]
    confirm_cfg = health_cfg.get("medication_confirm", {})
    medication = MedicationReminder(
        schedules,
        address_term=address_term,
        db=db,
        speak_callback=on_proactive_alert,
        on_ask=voice.open_session,
        notify_family=notifier.notify if confirm_cfg.get("notify_family_on_missed", True) else None,
        retry_mins=confirm_cfg.get("retry_mins", 15),
        max_asks=confirm_cfg.get("max_asks", 3),
        # Chào buổi sáng + đọc thời tiết trước lần nhắc thuốc buổi sáng (user.city)
        weather_callback=lambda: tools.weather_brief(config.get("user", {}).get("city", "")),
    )
    medication.start()

    # Tạo sẵn giọng đọc cho mọi câu an toàn cố định lúc còn mạng (Edge-TTS cần internet để tạo câu mới)
    tts.preload(list(sos_phrases.values()) + medication.fixed_phrases()
                + activity_monitor.fixed_phrases() + [ai_brain.network_error_reply])

    # Nhắc nhở tuỳ ý do người dùng tự đặt qua tool set_reminder (core/tools.py) — khác
    # daily_reminder ở trên (cố định, lặp lại mỗi ngày), đây là nhắc đúng 1 lần vào thời điểm đã hẹn.
    reminder_scheduler = ReminderScheduler(db, speak_callback=on_proactive_alert, address_term=address_term)
    reminder_scheduler.start()

    # Theo dõi nhiệt độ GPU chủ động — máy chạy 24/7 làm server, cần cảnh báo sớm nếu quá nóng
    # để kịp tắt máy cho nguội. Ngưỡng lấy từ config/settings.yaml (system.gpu_temp_warning_c).
    system_cfg = config.get("system", {})
    temp_monitor = TempMonitor(
        warning_c=system_cfg.get("gpu_temp_warning_c", 80),
        speak_callback=on_proactive_alert,
        address_term=address_term,
    )
    temp_monitor.start()

    # Callback khi nhận được giọng nói hoặc chatbot text
    def on_user_input(text, extra_callback=None, source="voice"):
        print(f"\n[SIR]: {text}")
        activity_monitor.mark_presence()

        text_lower = text.lower().strip()
        # Giọng nói đã được VoiceEngine bắt kêu cứu từ trước (kể cả chưa đánh thức) — ở đây
        # chỉ cần bắt thêm cho lệnh gõ chữ.
        if source != "voice" and any(w in text_lower for w in emergency_words):
            trigger_sos(text_lower)
            return

        # Đang chờ xác nhận uống thuốc -> "uống rồi"/"chưa" xử lý ngay, không qua AI
        med_reply = medication.handle_reply(text_lower)
        if med_reply:
            on_ai_response(med_reply)
            if extra_callback:
                extra_callback(med_reply)
            return
        if any(p in text_lower for p in CAMERA_ON_TRIGGERS):
            show_camera[0] = True
            on_ai_response(f"Đã bật camera, {address_term}.")
            if extra_callback:
                extra_callback(f"Đã bật camera, {address_term}.")
            return
        if any(p in text_lower for p in CAMERA_OFF_TRIGGERS):
            show_camera[0] = False
            on_ai_response(f"Đã tắt camera, {address_term}.")
            if extra_callback:
                extra_callback(f"Đã tắt camera, {address_term}.")
            return

        def combined(reply):
            on_ai_response(reply)
            if extra_callback:
                extra_callback(reply)

        if source == "voice":
            if voice.security_enabled:
                # ưu tiên xác minh qua giọng nói (không cần camera) — nếu chưa đăng ký/chưa xác định
                # được thì rơi về kết quả khuôn mặt (nếu camera đang bật và có xác minh)
                owner = voice.last_speaker_owner if voice.last_speaker_owner is not None else is_owner_flag[0]
            else:
                # bảo mật đang tắt (config voice.security_enabled=false) — vẫn nhận diện & hiển thị
                # đúng người đang nói (voice.last_speaker_name), nhưng không
                # chặn quyền dùng tool của bất kỳ ai.
                owner = True
        else:
            # gõ lệnh trực tiếp qua terminal — đã cần quyền truy cập máy rồi
            owner = True

        ai_brain.ask(text, callback=combined, is_owner=owner, source=source)

    voice.on_emergency = trigger_sos
    voice.on_speech_heard = activity_monitor.mark_presence
    # Câu chào khi vừa nghe thấy từ đánh thức ("dậy đi") — phát trước khi xử lý lệnh (nếu có).
    # Dùng đúng tên người vừa đánh thức (đa hồ sơ giọng nói) thay vì mặc định address_term.
    voice.on_wake = lambda name=None: on_ai_response(f"Hệ thống đã online. Tôi đã sẵn sàng phục vụ, {name or address_term}.")

    # Trạng thái tóm tắt cho trang người thân (core/web_interface.py) — chỉ những gì trang cần
    def get_status():
        return {
            "session_active": voice.session_active,
            "uptime_secs": int(time.time() - app_start_time),
        }

    # Web chỉ còn trang chỉ-xem /family cho người thân — EVA cho người cao tuổi điều khiển hoàn
    # toàn bằng giọng nói tại chỗ, không có dashboard điều khiển từ xa.
    web = WebInterface(db, get_status)
    web.start()

    # -----------------------------------------------------
    # LUỒNG NHẬP LIỆU CHATBOT (CHẠY SONG SONG)
    # -----------------------------------------------------
    def terminal_input_loop():
        print("\n" + "="*45)
        print(" CHẾ ĐỘ CHATBOT ĐÃ SẴN SÀNG")
        print(" -> Gõ lệnh trực tiếp vào đây và nhấn Enter")
        print("="*45 + "\n")
        while True:
            # Dòng này sẽ đứng đợi Sir nhập lệnh
            user_cmd = input("[NHẬP LỆNH SIR]: ")
            if user_cmd.strip():
                on_user_input(user_cmd, source="text")

    # Khởi chạy luồng Chatbot để không làm treo Camera — chỉ bật khi có terminal thật gắn vào
    # stdin (chạy tay). Khi EVA chạy nền qua Task Scheduler (không có console), input() sẽ
    # luôn ném EOFError ngay từ lần gọi đầu, làm bẩn log mỗi lần khởi động mà không ích gì.
    if sys.stdin and sys.stdin.isatty():
        threading.Thread(target=terminal_input_loop, daemon=True).start()
    else:
        print("[MAIN] Không có terminal tương tác — chỉ nhận lệnh bằng giọng nói.")

    # Bật mic ngay khi Whisper nạp xong — không còn gesture nên phải tự chờ,
    # tránh gọi activate() quá sớm lúc model chưa sẵn sàng (activate() sẽ bỏ qua âm thầm)
    def activate_voice_when_ready():
        while not voice.ready:
            time.sleep(0.5)
        voice.activate(on_user_input)
        print(f"[STT] Mic đã bật — nói '{config['eva']['wake_word']}' trước lệnh để kích hoạt.")

    threading.Thread(target=activate_voice_when_ready, daemon=True).start()

    last_face_check = 0.0
    camera_fail_count = 0

    # Không có cửa sổ hiển thị nào — giao tiếp chính bằng giọng nói.
    # Vòng lặp này chỉ còn nhiệm vụ: đọc camera (khi được bật) để xác minh chủ nhân định kỳ.
    while not shutdown_event.is_set():
        if show_camera[0]:
            cap = ensure_camera()
            ret, frame = cap.read()
            if ret:
                camera_fail_count = 0
                now = time.time()
                if face_engine.has_owner and now - last_face_check > 3.0 and not face_check_busy[0]:
                    last_face_check = now
                    threading.Thread(target=run_face_check, args=(frame.copy(),), daemon=True).start()
            else:
                # Trước đây im lặng hoàn toàn nếu camera không đọc được gì (sai index, không
                # có camera, thiết bị rớt kết nối...) — Sơn nói "bật camera" vẫn được báo "Đã
                # bật" bình thường dù chẳng có gì hoạt động cả. Giờ log 1 lần sau ~1s lỗi liên
                # tục thay vì spam mỗi khung hình.
                camera_fail_count += 1
                if camera_fail_count == 30:
                    print("[CAMERA] Không đọc được khung hình liên tục — kiểm tra lại thiết bị camera.")
            time.sleep(0.03)
        else:
            release_camera()
            camera_fail_count = 0
            time.sleep(0.1)

    # Giải phóng tài nguyên khi thoát
    voice.deactivate()
    release_camera()

    # Lưu app stop event và đóng database
    db.log_event("APP_STOP", "EVA stopped")
    db.close()

if __name__ == "__main__":
    run()
