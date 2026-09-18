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
from core.daily_reminder import DailyReminder
from core.reminder_scheduler import ReminderScheduler
from core.temp_monitor import TempMonitor
from core import tools
from core.remote_exec import executor as remote_executor

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
    # dùng để nhận diện chủ nhân, không hiển thị lên đâu cả (giao diện duy nhất là dashboard web)
    cap_holder = [None]
    tts = TTSEngine()
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

    # Callback cho các cảnh báo/nhắc nhở CHỦ ĐỘNG (health/activity/daily/reminder) — khác
    # on_ai_response ở chỗ những nơi này gọi thẳng speak_callback, không đi qua ai_brain.ask()
    # nên không tự được lưu vào lịch sử ở đâu cả; trước đây cũng chỉ phát được qua loa server,
    # Sơn ở xa (laptop) sẽ không bao giờ nghe được và không có dấu vết gì để xem lại trên
    # dashboard dù có mở lại sau đó.
    def on_proactive_alert(text):
        print(f"\n[EVA]: {text}")
        db.save_conversation("assistant", text)
        tts.speak(text)
        if remote_executor.laptop_connected:
            try:
                audio_path = tts.get_audio_path(text)
                with open(audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode("ascii")
                remote_executor.push("speak", {"text": text, "audio_b64": audio_b64})
            except Exception as e:
                print(f"[Proactive] Không đẩy được thông báo sang laptop: {e}")

    # Theo dõi sức khoẻ chủ động — tự lên tiếng khi phát hiện bất thường trong health_logs
    # (vd ngủ ít liên tục), không cần Sơn hỏi trước.
    health_monitor = HealthMonitor(db, speak_callback=on_proactive_alert)
    health_monitor.start()

    # Suy đoán giấc ngủ tự động từ hành vi dùng máy (không cần Sơn tự khai) — tự ghi vào
    # health_logs cùng category "giấc ngủ", health_monitor phía trên đọc chung dữ liệu này.
    # speak_callback dùng cho cảnh báo thức trắng đêm (tín hiệu ngược: hoạt động liên tục
    # không nghỉ, thay vì im lặng).
    activity_monitor = ActivityMonitor(speak_callback=on_proactive_alert)
    activity_monitor.start()

    # Nhắc cố định hàng ngày theo lời bác sĩ dặn (dậy ăn sáng + uống thuốc) — giờ lấy từ config,
    # chỉnh trong config/settings.yaml (health.daily_reminder_time) nếu cần đổi.
    health_cfg = config.get("health", {})
    daily_reminder = DailyReminder(
        reminder_time=health_cfg.get("daily_reminder_time", "07:00"),
        message=health_cfg.get("daily_reminder_message", "Sơn ơi, đã đến giờ dậy ăn sáng và uống thuốc rồi đó."),
        speak_callback=on_proactive_alert,
    )
    daily_reminder.start()

    # Nhắc nhở tuỳ ý do Sơn tự đặt qua tool set_reminder (core/tools.py) — khác daily_reminder
    # ở trên (cố định, lặp lại mỗi ngày), đây là nhắc đúng 1 lần vào thời điểm đã hẹn.
    reminder_scheduler = ReminderScheduler(db, speak_callback=on_proactive_alert)
    reminder_scheduler.start()

    # Theo dõi nhiệt độ GPU chủ động — máy chạy 24/7 làm server, cần cảnh báo sớm nếu quá nóng
    # để kịp tắt máy cho nguội. Ngưỡng lấy từ config/settings.yaml (system.gpu_temp_warning_c).
    system_cfg = config.get("system", {})
    temp_monitor = TempMonitor(
        warning_c=system_cfg.get("gpu_temp_warning_c", 80),
        speak_callback=on_proactive_alert,
    )
    temp_monitor.start()

    # Callback khi nhận được giọng nói hoặc chatbot text
    def on_user_input(text, extra_callback=None, source="voice"):
        print(f"\n[SIR]: {text}")

        text_lower = text.lower().strip()
        if any(p in text_lower for p in CAMERA_ON_TRIGGERS):
            show_camera[0] = True
            on_ai_response("Đã bật camera, Sơn.")
            if extra_callback:
                extra_callback("Đã bật camera, Sơn.")
            return
        if any(p in text_lower for p in CAMERA_OFF_TRIGGERS):
            show_camera[0] = False
            on_ai_response("Đã tắt camera, Sơn.")
            if extra_callback:
                extra_callback("Đã tắt camera, Sơn.")
            return

        def combined(reply):
            if source == "web_voice":
                # Giọng nói ghi từ trình duyệt — Sơn nghe qua chính trình duyệt (route /api/voice
                # tự lo phần TTS riêng), KHÔNG phát lại qua loa server (tránh nói vào phòng trống
                # + tránh 2 nơi cùng ghi đè 1 file cache TTS cùng lúc).
                print(f"\n[EVA]: {reply}")
            else:
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
                # đúng người đang nói (voice.last_speaker_name/owner cho dashboard), nhưng không
                # chặn quyền dùng tool của bất kỳ ai.
                owner = True
        else:
            # gõ lệnh trực tiếp qua web/terminal — đã cần quyền truy cập máy/mạng của Sơn rồi
            owner = True

        ai_brain.ask(text, callback=combined, is_owner=owner, source=source)

    # Câu chào khi vừa nghe thấy từ đánh thức ("dậy đi") — phát trước khi xử lý lệnh (nếu có).
    # Dùng đúng tên người vừa đánh thức (đa hồ sơ giọng nói) thay vì mặc định "Sơn".
    voice.on_wake = lambda name=None: on_ai_response(f"Hệ thống đã online. Tôi đã sẵn sàng phục vụ, {name or 'Sơn'}.")

    # Trạng thái thật của hệ thống — dùng cho dashboard web (core/web_interface.py)
    # cpu/ram lấy từ tools.get_live_stats() (cache dùng chung) để khớp đúng số EVA báo cáo qua tool
    def get_status():
        cpu, ram = tools.get_live_stats()
        return {
            "cpu": cpu,
            "ram": ram,
            "online_mode": ai_brain.online_mode,
            "model": ai_brain.online_model if ai_brain.online_mode else ai_brain.model,
            "session_active": voice.session_active,
            # is_owner ở đây là nhận diện THÔ (ai đang nói, không tính chính sách bảo mật) — khác
            # với quyền THỰC TẾ dùng để cấp phép tool ở on_user_input() phía trên, nơi
            # security_enabled=False sẽ luôn cho owner=True bất kể nhận diện được ai. Gửi kèm
            # security_enabled để dashboard tự diễn giải đúng, tránh hiển thị mâu thuẫn với
            # quyền thật đang được cấp (xem web_interface.py's ownerVal).
            "is_owner": voice.last_speaker_owner if voice.last_speaker_owner is not None else is_owner_flag[0],
            "owner_name": voice.last_speaker_name,
            "security_enabled": voice.security_enabled,
            "voice_id_enrolled": voice._voice_id.has_profiles if voice._voice_id else False,
            "voice_profiles": [p["name"] for p in voice._voice_id.profiles] if voice._voice_id else [],
            "camera_on": show_camera[0],
            "uptime_secs": int(time.time() - app_start_time),
            "wake_word": config["eva"]["wake_word"],
        }

    # Thu hồi quyền điều khiển của 1 người đã đăng ký giọng nói — gọi từ dashboard web
    def revoke_voice(name):
        if voice._voice_id:
            return voice._voice_id.revoke(name)
        return False

    # laptop_idle_agent.py (chạy trên laptop) poll route này định kỳ để lấy lệnh cần thực thi
    # tại chỗ (mở app/link) — mark_laptop_seen() luôn được gọi trước để remote_exec.executor
    # biết laptop còn kết nối hay không, kể cả những lượt không có lệnh nào chờ.
    def laptop_poll():
        remote_executor.mark_laptop_seen()
        return remote_executor.take_pending()

    # Giao diện duy nhất của EVA: dashboard web (gõ lệnh từ điện thoại/máy khác cùng mạng LAN)
    web = WebInterface(
        on_user_input, db, get_status,
        on_shutdown=shutdown_event.set,
        on_revoke_voice=revoke_voice,
        on_laptop_heartbeat=activity_monitor.report_laptop_idle,
        on_laptop_poll=laptop_poll,
        on_laptop_result=remote_executor.report_result,
        on_transcribe_audio=voice.transcribe_uploaded_audio,
        on_synthesize_reply=tts.get_audio_path,
    )
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
        print("[MAIN] Không có terminal tương tác — chỉ nhận lệnh qua dashboard web.")

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

    # Không có cửa sổ hiển thị nào nữa — dashboard web là giao diện duy nhất.
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
