import base64
import os
import secrets
import threading
import time
from dotenv import load_dotenv, set_key
from flask import Flask, request, jsonify, send_from_directory

# Giao diện dashboard giờ là 1 app Next.js build tĩnh (xem web/), không còn viết tay HTML/JS
# ngay trong file Python nữa. Flask chỉ việc serve thư mục build ra (web/out/) — chạy
# `npm run build` trong web/ mỗi khi sửa giao diện, Flask không tự build hộ.
FRONTEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "web", "out"))
ENV_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _get_or_create_dashboard_token():
    """Server (0.0.0.0) không xác thực gì trước đây — ai vào được mạng/IP là điều khiển được
    máy luôn (mở app, tắt máy...). Token này bắt buộc mọi request /api/* phải biết trước,
    tự sinh 1 lần và ghi lại vào .env để cố định qua các lần chạy sau, laptop_idle_agent.py
    và dashboard (web/lib/api.ts) đều phải gửi kèm đúng token qua header X-Auth-Token."""
    load_dotenv(ENV_PATH)
    token = os.getenv("DASHBOARD_TOKEN")
    if token:
        return token
    token = secrets.token_urlsafe(24)
    try:
        set_key(ENV_PATH, "DASHBOARD_TOKEN", token)
    except OSError as e:
        print(f"[WEB] Không ghi được DASHBOARD_TOKEN vào .env ({e}) — token chỉ dùng cho phiên này.")
    print(f"[WEB] Đã tạo DASHBOARD_TOKEN mới: {token}")
    print("[WEB] Dán token này vào dashboard lúc mở lần đầu, và vào laptop_idle_agent.py (biến DASHBOARD_TOKEN) nếu dùng.")
    return token


def _get_or_create_dashboard_pin():
    """Mã PIN 4 số để ghép nối dashboard lần đầu (xem route /api/pair) — thay cho việc phải dán
    DASHBOARD_TOKEN dài từ log/.env, dễ đọc/gõ hơn nhiều cho người không rành công nghệ. PIN chỉ
    dùng MỘT LẦN lúc ghép nối, sau đó dashboard tự lưu lại token thật (dài) như trước — không đổi
    cơ chế xác thực cho các API còn lại, chỉ đổi cách lấy được token lần đầu."""
    load_dotenv(ENV_PATH)
    pin = os.getenv("DASHBOARD_PIN")
    if pin:
        return pin
    pin = f"{secrets.randbelow(10000):04d}"
    try:
        set_key(ENV_PATH, "DASHBOARD_PIN", pin)
    except OSError as e:
        print(f"[WEB] Không ghi được DASHBOARD_PIN vào .env ({e}) — PIN chỉ dùng cho phiên này.")
    print(f"[WEB] Mã PIN ghép nối dashboard: {pin} — đọc mã này cho người dùng để họ tự ghép nối lần đầu, không cần dán token dài.")
    return pin


def _get_or_create_family_token():
    """Token riêng, quyền hạn hẹp hơn hẳn DASHBOARD_TOKEN — chỉ dùng được cho /api/family_status
    (xem route bên dưới), không điều khiển được gì và không đọc được nội dung hội thoại. Gửi kèm
    trong link chia sẻ cho người thân (xem WebInterface.start()), không cần họ tự đăng nhập gì cả."""
    load_dotenv(ENV_PATH)
    token = os.getenv("FAMILY_TOKEN")
    if token:
        return token
    token = secrets.token_urlsafe(24)
    try:
        set_key(ENV_PATH, "FAMILY_TOKEN", token)
    except OSError as e:
        print(f"[WEB] Không ghi được FAMILY_TOKEN vào .env ({e}) — token chỉ dùng cho phiên này.")
    print(f"[WEB] Đã tạo FAMILY_TOKEN mới cho trang người thân: {token}")
    return token


class WebInterface:
    def __init__(self, on_user_input, db, get_status, on_shutdown=None, on_revoke_voice=None,
                 on_laptop_heartbeat=None, on_laptop_poll=None, on_laptop_result=None,
                 on_transcribe_audio=None, on_synthesize_reply=None, port=5000):
        self.on_user_input = on_user_input
        self.db = db
        self.get_status = get_status
        self.on_shutdown = on_shutdown
        self.on_revoke_voice = on_revoke_voice
        self.on_laptop_heartbeat = on_laptop_heartbeat
        self.on_laptop_poll = on_laptop_poll
        self.on_laptop_result = on_laptop_result
        self.on_transcribe_audio = on_transcribe_audio
        self.on_synthesize_reply = on_synthesize_reply
        self.port = port
        self.app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
        self._token = _get_or_create_dashboard_token()
        self._pin = _get_or_create_dashboard_pin()
        self._family_token = _get_or_create_family_token()
        self._pair_attempts = {}  # ip -> list[timestamp các lần nhập sai PIN gần đây]
        self._pair_lock = threading.Lock()
        if not os.path.isdir(FRONTEND_DIR):
            print(f"[WEB] Chưa build giao diện — chạy 'npm run build' trong web/ (thiếu {FRONTEND_DIR})")
        self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.before_request
        def _require_token():
            # Chỉ chặn /api/* — static file (trang, JS, CSS của dashboard) vẫn public vì tự
            # thân không lộ gì, chặn ở tầng gọi API là đủ (không có token thì không ra lệnh/
            # đọc được dữ liệu gì cả). so sánh bằng secrets.compare_digest chống timing attack.
            # /api/pair và /api/family_status tự xác thực riêng (PIN / FAMILY_TOKEN), không
            # dùng DASHBOARD_TOKEN — bỏ qua check chung ở đây cho 2 route đó.
            if request.path.startswith("/api/") and request.path not in ("/api/pair", "/api/family_status"):
                token = request.headers.get("X-Auth-Token", "")
                if not secrets.compare_digest(token, self._token):
                    return jsonify({"status": "unauthorized"}), 401

        @app.route("/")
        def index():
            # index.html tham chiếu tới các file JS/CSS đã đổi tên (hash) mỗi lần build — nhưng
            # bản thân index.html thì không, nên trình duyệt (đặc biệt Safari di động) có thể giữ
            # cache cũ của chính file này, khiến sửa giao diện xong build lại vẫn không thấy thay
            # đổi cho tới khi cache tự hết hạn. Ép luôn phải tải lại mỗi lần.
            resp = send_from_directory(FRONTEND_DIR, "index.html")
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return resp

        @app.route("/family")
        def family_page():
            # Trang riêng cho người thân (web/app/family/page.tsx) — Next.js static export với
            # trailingSlash mặc định (false) sinh ra "family.html" ở gốc out/, không phải
            # "family/index.html" — xác nhận bằng cách build thật rồi xem out/ sinh ra gì, không
            # đoán theo lý thuyết. Cùng kiểu cache-busting với "/".
            resp = send_from_directory(FRONTEND_DIR, "family.html")
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return resp

        _PAIR_MAX_ATTEMPTS = 5
        _PAIR_WINDOW_SECS = 300

        @app.route("/api/pair", methods=["POST"])
        def pair():
            # Ghép nối lần đầu bằng PIN 4 số thay vì dán DASHBOARD_TOKEN dài — đúng PIN thì trả
            # về token thật để dashboard lưu lại dùng lâu dài (xem web/components/TokenGate.tsx).
            # Giới hạn số lần thử theo IP để chặn dò PIN 4 số (chỉ 10.000 khả năng).
            ip = request.remote_addr or "unknown"
            now = time.time()
            with self._pair_lock:
                attempts = [t for t in self._pair_attempts.get(ip, []) if now - t < _PAIR_WINDOW_SECS]
                if len(attempts) >= _PAIR_MAX_ATTEMPTS:
                    self._pair_attempts[ip] = attempts
                    return jsonify({"status": "error", "message": "Nhập sai quá nhiều lần, thử lại sau vài phút."}), 429

            data = request.get_json(force=True, silent=True) or {}
            pin = str(data.get("pin", "")).strip()
            if pin and secrets.compare_digest(pin, self._pin):
                with self._pair_lock:
                    self._pair_attempts.pop(ip, None)
                return jsonify({"status": "ok", "token": self._token})

            with self._pair_lock:
                attempts.append(now)
                self._pair_attempts[ip] = attempts
            return jsonify({"status": "error", "message": "Mã PIN không đúng."}), 401

        @app.route("/api/family_status")
        def family_status():
            # Tách hẳn khỏi X-Auth-Token chính — chỉ trả dữ liệu tóm tắt, KHÔNG có nội dung hội
            # thoại, KHÔNG điều khiển được gì (không camera/shutdown/revoke...).
            token = request.headers.get("X-Family-Token", "")
            if not secrets.compare_digest(token, self._family_token):
                return jsonify({"status": "unauthorized"}), 401

            data = self.get_status()
            last_rows = self.db.get_conversation_history(limit=1)
            last_activity = str(last_rows[0][2]) if last_rows else None
            notes = self.db.get_notes(limit=5)
            return jsonify({
                "session_active": data.get("session_active", False),
                "uptime_secs": data.get("uptime_secs", 0),
                "last_activity": last_activity,
                "recent_notes": [{"content": content, "timestamp": str(ts)} for content, ts in notes],
            })

        @app.route("/api/message", methods=["POST"])
        def message():
            data = request.get_json(force=True, silent=True) or {}
            text = data.get("text", "").strip()
            if not text:
                return jsonify({"status": "empty"}), 400
            self.on_user_input(text, source="text")
            return jsonify({"status": "queued"})

        @app.route("/api/voice", methods=["POST"])
        def voice():
            # Giọng nói ghi từ trình duyệt (dashboard tự đóng gói thành WAV 16-bit/mono/16kHz
            # trước khi gửi lên, xem lib/useVoiceRecorder.ts trong web/) — khác /api/message
            # ở chỗ CHẶN chờ tới khi có câu trả lời (để trả luôn audio về cho trình duyệt phát),
            # thay vì trả ngay "queued" rồi để dashboard tự bắt sau qua /api/history.
            audio_file = request.files.get("audio")
            if not audio_file:
                return jsonify({"status": "error", "message": "Thiếu file audio"}), 400

            if not self.on_transcribe_audio:
                return jsonify({"status": "stt_not_ready", "message": "Chưa cấu hình STT"}), 503

            text = self.on_transcribe_audio(audio_file.read())
            if text is None:
                return jsonify({"status": "stt_not_ready", "message": "STT chưa nạp xong, đợi giây lát"}), 503
            if not text:
                return jsonify({"status": "empty_transcript", "message": "Không nghe rõ, thử lại"}), 400

            event = threading.Event()
            holder = {}

            def capture(reply):
                holder["reply"] = reply
                event.set()

            self.on_user_input(text, extra_callback=capture, source="web_voice")

            if not event.wait(timeout=30):
                return jsonify({
                    "status": "timeout", "transcript": text,
                    "message": "EVA chưa phản hồi kịp — có thể vẫn đang xử lý, kiểm tra lại lịch sử chat",
                }), 504

            reply = holder["reply"]
            audio_path = self.on_synthesize_reply(reply) if self.on_synthesize_reply else None
            audio_b64 = ""
            if audio_path:
                with open(audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode("ascii")

            return jsonify({"status": "ok", "transcript": text, "reply": reply, "audio_b64": audio_b64})

        @app.route("/api/history")
        def history():
            rows = self.db.get_conversation_history(limit=50)
            return jsonify([{"role": role, "text": content, "timestamp": str(ts)} for role, content, ts in rows])

        @app.route("/api/status")
        def status():
            data = self.get_status()
            notes = self.db.get_notes(limit=5)
            data["notes"] = [{"content": content, "timestamp": str(ts)} for content, ts in notes]
            return jsonify(data)

        @app.route("/api/shutdown", methods=["POST"])
        def shutdown():
            if self.on_shutdown:
                self.on_shutdown()
            return jsonify({"status": "shutting_down"})

        @app.route("/api/revoke_voice", methods=["POST"])
        def revoke_voice():
            data = request.get_json(force=True, silent=True) or {}
            name = data.get("name", "").strip()
            if not name:
                return jsonify({"status": "error", "message": "Thiếu tên"}), 400
            ok = self.on_revoke_voice(name) if self.on_revoke_voice else False
            return jsonify({"status": "ok" if ok else "not_found"})

        @app.route("/api/debug_log", methods=["POST"])
        def debug_log():
            # Route tạm để chẩn đoán lỗi ghi âm trên Safari/iOS — trình duyệt tự báo từng bước
            # (bắt đầu ghi, dừng ghi, encode xong...) về đây, in ra log server (eva.log) để xem
            # được chính xác nó dừng ở bước nào mà không cần Mac/Safari Web Inspector để debug
            # trực tiếp trên điện thoại. Có thể xoá route này sau khi hết cần dùng.
            data = request.get_json(force=True, silent=True) or {}
            print(f"[ClientDebug] {data.get('msg', '')}")
            return jsonify({"status": "ok"})

        @app.route("/api/laptop_heartbeat", methods=["POST"])
        def laptop_heartbeat():
            # Gọi định kỳ từ laptop_idle_agent.py chạy trên laptop — báo thời gian rảnh của
            # laptop về để activity_monitor gộp vào tín hiệu "Sơn có đang dùng máy" (server
            # không tự biết được điều này nếu chỉ đo input cục bộ của chính nó).
            data = request.get_json(force=True, silent=True) or {}
            idle_seconds = data.get("idle_seconds")
            if idle_seconds is None:
                return jsonify({"status": "error", "message": "Thiếu idle_seconds"}), 400
            if self.on_laptop_heartbeat:
                self.on_laptop_heartbeat(float(idle_seconds))
            return jsonify({"status": "ok"})

        @app.route("/api/laptop_pending_command")
        def laptop_pending_command():
            # laptop_idle_agent.py poll route này mỗi ~2s — gọi luôn dù không có lệnh chờ, để
            # server biết laptop vẫn đang kết nối (dùng cho remote_exec.executor.laptop_connected).
            cmd = self.on_laptop_poll() if self.on_laptop_poll else None
            return jsonify(cmd or {})

        @app.route("/api/laptop_command_result", methods=["POST"])
        def laptop_command_result():
            data = request.get_json(force=True, silent=True) or {}
            req_id = data.get("id")
            result = data.get("result", "")
            if req_id is None:
                return jsonify({"status": "error", "message": "Thiếu id"}), 400
            if self.on_laptop_result:
                self.on_laptop_result(int(req_id), result)
            return jsonify({"status": "ok"})

    def start(self):
        t = threading.Thread(
            target=lambda: self.app.run(
                host="0.0.0.0", port=self.port, debug=False, use_reloader=False, threaded=True
            ),
            daemon=True,
        )
        t.start()
        print(f"[WEB] Dashboard điều khiển từ xa: http://<IP-máy-bạn>:{self.port}")
        print(f"[WEB] Link cho người thân (chỉ xem, không điều khiển được): http://<IP-máy-bạn>:{self.port}/family?token={self._family_token}")

        # Listener HTTPS riêng (cổng khác) bằng cert Tailscale (xem `tailscale cert`) — trình
        # duyệt (Safari/Chrome) chỉ cho phép mic (getUserMedia) qua "secure context" tức HTTPS
        # thật hoặc localhost, HTTP thường qua Tailscale/LAN không đủ điều kiện. Bản HTTP ở trên
        # vẫn giữ nguyên cho các tính năng không cần mic (dashboard, chat chữ...). Cert hết hạn
        # theo chu kỳ Tailscale cấp — chạy lại `tailscale cert` để làm mới nếu HTTPS ngừng hoạt động.
        cert_path = os.path.join(os.path.dirname(__file__), "..", "assets", "tailscale.crt")
        key_path = os.path.join(os.path.dirname(__file__), "..", "assets", "tailscale.key")
        if os.path.isfile(cert_path) and os.path.isfile(key_path):
            https_port = self.port + 443
            t_https = threading.Thread(
                target=lambda: self.app.run(
                    host="0.0.0.0", port=https_port, debug=False, use_reloader=False, threaded=True,
                    ssl_context=(cert_path, key_path),
                ),
                daemon=True,
            )
            t_https.start()
            print(f"[WEB] Dashboard HTTPS (bắt buộc để dùng mic qua trình duyệt): https://desktop-5ggo7mc.tail9045bf.ts.net:{https_port}")
        else:
            print("[WEB] Chưa có cert Tailscale (assets/tailscale.crt + .key) — mic qua trình duyệt sẽ không dùng được ngoài localhost. Chạy 'tailscale cert <hostname>' để tạo.")
