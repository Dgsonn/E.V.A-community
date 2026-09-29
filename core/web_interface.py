import os
import secrets
import threading
from dotenv import load_dotenv, set_key
from flask import Flask, request, jsonify, send_from_directory

# Trang người thân là 1 app Next.js build tĩnh (xem web/). Flask chỉ việc serve thư mục build ra
# (web/out/) — chạy `npm run build` trong web/ mỗi khi sửa giao diện, Flask không tự build hộ.
FRONTEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "web", "out"))
ENV_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _get_or_create_family_token():
    """Token cho trang chỉ-xem của người thân — không điều khiển được gì và không đọc được nội
    dung hội thoại. Gửi kèm trong link chia sẻ cho người thân (xem WebInterface.start()), không
    cần họ tự đăng nhập gì cả. Tự sinh 1 lần và ghi lại vào .env để cố định qua các lần chạy."""
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
    """Chỉ phục vụ trang /family cho người thân. EVA cho người cao tuổi điều khiển hoàn toàn bằng
    giọng nói tại chỗ — không có dashboard điều khiển từ xa."""

    def __init__(self, db, get_status, port=5000):
        self.db = db
        self.get_status = get_status
        self.port = port
        self.app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
        self._family_token = _get_or_create_family_token()
        if not os.path.isdir(FRONTEND_DIR):
            print(f"[WEB] Chưa build giao diện — chạy 'npm run build' trong web/ (thiếu {FRONTEND_DIR})")
        self._setup_routes()

    def _setup_routes(self):
        app = self.app

        @app.route("/family")
        def family_page():
            # Next.js static export với trailingSlash mặc định (false) sinh ra "family.html" ở
            # gốc out/, không phải "family/index.html". index.html/family.html không đổi tên theo
            # hash mỗi lần build nên trình duyệt (đặc biệt Safari di động) có thể giữ cache cũ —
            # ép luôn phải tải lại.
            resp = send_from_directory(FRONTEND_DIR, "family.html")
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return resp

        @app.route("/api/family_status")
        def family_status():
            # Chỉ trả dữ liệu tóm tắt — KHÔNG có nội dung hội thoại, KHÔNG điều khiển được gì.
            # So sánh bằng secrets.compare_digest chống timing attack.
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

    def start(self):
        t = threading.Thread(
            target=lambda: self.app.run(
                host="0.0.0.0", port=self.port, debug=False, use_reloader=False, threaded=True
            ),
            daemon=True,
        )
        t.start()
        print(f"[WEB] Link cho người thân (chỉ xem): http://<IP-máy-bạn>:{self.port}/family?token={self._family_token}")
