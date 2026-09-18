import ctypes
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta

import psutil
import yaml

from core.database import get_db
from core import remote_exec

_dev_config_cache = None


def _get_dev_config():
    """Whitelist cho các tool dev-ops (git_status/git_log/tail_log_file) — đọc riêng mục 'dev'
    trong config/settings.yaml thay vì nhận config qua tham số, vì tools.py vốn không có sẵn
    đường truyền config từ main.py (execute() chỉ nhận name/args/is_owner/source). Cache lại vì
    mỗi lần gọi tool không cần đọc lại file — sửa settings.yaml thì cần khởi động lại EVA để áp
    dụng, giống các phần khác của config."""
    global _dev_config_cache
    if _dev_config_cache is None:
        try:
            with open("config/settings.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except OSError:
            cfg = {}
        _dev_config_cache = cfg.get("dev", {}) or {}
    return _dev_config_cache

MAX_TOOL_ITERATIONS = 3

_NUMBER_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)")


def extract_number(text):
    """Trích số đầu tiên trong 1 chuỗi tự do (vd '70kg' -> 70.0, '6 tiếng' -> 6.0).
    Dùng chung cho tool tóm tắt sức khoẻ và health_monitor (theo dõi chủ động)."""
    m = _NUMBER_PATTERN.search(text)
    return float(m.group(1).replace(",", ".")) if m else None


def parse_db_timestamp(ts):
    """Parse chuỗi timestamp lưu bởi datetime.now() (có hoặc không có phần vi giây)."""
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None

# CPU/RAM đo tại đây, cache lại ~1.5s — để dashboard web và tool get_system_status
# luôn báo cùng một con số, thay vì mỗi nơi tự gọi psutil riêng ra kết quả lệch nhau.
_stats_cache = {"cpu": 0.0, "ram": 0.0, "t": 0.0}


def get_live_stats():
    now = time.time()
    if now - _stats_cache["t"] > 1.5:
        _stats_cache["cpu"] = psutil.cpu_percent(interval=None)
        _stats_cache["ram"] = psutil.virtual_memory().percent
        _stats_cache["t"] = now
    return _stats_cache["cpu"], _stats_cache["ram"]

TOOL_SPECS = [
    {
        "name": "open_url",
        "description": "Mở một URL trong trình duyệt mặc định, ví dụ để mở YouTube, Google hoặc một trang web bất kỳ.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL cần mở, ví dụ https://youtube.com"},
            },
            "required": ["url"],
        },
        "requires_owner": True,
    },
    {
        "name": "get_last_login",
        "description": "Tra cứu thời điểm EVA được khởi động lần gần nhất trước phiên hiện tại.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_owner": True,
    },
    {
        "name": "open_app",
        "description": "Mở một ứng dụng đã cài trên máy Windows theo tên file thực thi, ví dụ notepad, calc, spotify.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tên lệnh/app cần mở, ví dụ 'notepad' hoặc 'calc'"},
            },
            "required": ["name"],
        },
        "requires_owner": True,
    },
    {
        "name": "get_conversation_history",
        "description": "Lấy lại các đoạn hội thoại gần đây giữa chủ nhân và EVA, dùng khi cần nhớ lại đã nói gì trước đó.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Số tin nhắn gần nhất cần lấy, mặc định 10"},
            },
            "required": [],
        },
        "requires_owner": True,
    },
    {
        "name": "save_note",
        "description": "Lưu lại một ghi chú giúp chủ nhân, ví dụ việc cần nhớ hoặc thông tin cần lưu lại.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Nội dung ghi chú cần lưu"},
            },
            "required": ["content"],
        },
        "requires_owner": True,
    },
    {
        "name": "get_notes",
        "description": "Lấy lại các ghi chú đã lưu trước đó.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Số ghi chú gần nhất cần lấy, mặc định 10"},
            },
            "required": [],
        },
        "requires_owner": True,
    },
    {
        "name": "get_system_status",
        "description": "Tra cứu tình trạng máy tính hiện tại: CPU, RAM đang dùng bao nhiêu phần trăm, và nhiệt độ GPU.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_owner": False,
    },
    {
        "name": "log_health",
        "description": "Ghi lại 1 thông tin sức khoẻ Sơn vừa báo, ví dụ giấc ngủ, cân nặng, triệu chứng, tâm trạng, uống nước, vận động, thuốc đã uống. Chỉ gọi khi Sơn báo tin sức khoẻ thật (vd 'tôi ngủ 6 tiếng', 'cân nặng 70kg', 'hôm nay đau đầu'), không gọi khi Sơn chỉ hỏi lại thông tin cũ.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Loại thông tin, ví dụ 'giấc ngủ', 'cân nặng', 'triệu chứng', 'tâm trạng', 'nước', 'vận động', 'thuốc'",
                },
                "content": {
                    "type": "string",
                    "description": "Nội dung cụ thể, ví dụ '6 tiếng', '70kg', 'đau đầu nhẹ'",
                },
            },
            "required": ["category", "content"],
        },
        "requires_owner": True,
    },
    {
        "name": "get_health_logs",
        "description": "Lấy lại lịch sử sức khoẻ đã ghi trước đó của Sơn (liệt kê thô). Dùng khi Sơn muốn xem lại từng lần đã ghi gì.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Lọc theo loại, ví dụ 'cân nặng' — để trống lấy tất cả các loại",
                },
                "limit": {"type": "integer", "description": "Số mục gần nhất cần lấy, mặc định 10"},
            },
            "required": [],
        },
        "requires_owner": True,
    },
    {
        "name": "get_health_summary",
        "description": "Tóm tắt XU HƯỚNG sức khoẻ theo 1 loại trong N ngày gần đây — tự tính trung bình và tăng/giảm nếu là số liệu (vd cân nặng, giấc ngủ). Dùng khi Sơn hỏi 'thay đổi thế nào', 'có xu hướng gì không', 'trung bình bao nhiêu' — KHÔNG dùng get_health_logs (chỉ liệt kê thô, không tính toán) cho các câu hỏi kiểu này.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Loại cần tóm tắt, ví dụ 'cân nặng', 'giấc ngủ'"},
                "days": {"type": "integer", "description": "Số ngày gần đây cần xét, mặc định 7"},
            },
            "required": ["category"],
        },
        "requires_owner": True,
    },
    {
        "name": "set_reminder",
        "description": "Đặt 1 nhắc nhở tuỳ ý, báo đúng 1 lần vào thời điểm cụ thể trong tương lai — dùng khi Sơn nói 'nhắc tôi lúc...', 'hẹn giờ ... nhắc tôi...'. PHẢI tự tính đúng remind_at dựa theo thời gian hiện tại đã được cho biết trong hệ thống (không hỏi lại Sơn bây giờ là mấy giờ).",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Nội dung cần nhắc, ví dụ 'họp với khách hàng', 'uống nước'"},
                "remind_at": {"type": "string", "description": "Thời điểm nhắc, định dạng YYYY-MM-DD HH:MM:SS"},
            },
            "required": ["message", "remind_at"],
        },
        "requires_owner": True,
    },
    {
        "name": "get_reminders",
        "description": "Xem danh sách các nhắc nhở đang chờ (chưa tới giờ báo), kèm ID để huỷ nếu cần.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "requires_owner": True,
    },
    {
        "name": "cancel_reminder",
        "description": "Huỷ 1 nhắc nhở đang chờ theo ID — dùng get_reminders trước để biết ID cần huỷ.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID nhắc nhở cần huỷ, lấy từ get_reminders"},
            },
            "required": ["id"],
        },
        "requires_owner": True,
    },
    {
        "name": "take_screenshot",
        "description": "Chụp màn hình máy tính hiện tại, lưu lại thành file ảnh.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "requires_owner": True,
    },
    {
        "name": "lock_computer",
        "description": "Khoá màn hình máy tính ngay lập tức (giống bấm Win+L).",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "requires_owner": True,
    },
    {
        "name": "shutdown_computer",
        "description": "Tắt TOÀN BỘ máy tính (không phải tắt 1 ứng dụng hay camera) sau 30 giây — chỉ gọi khi Sơn yêu cầu thật rõ ràng và chắc chắn, ví dụ 'tắt máy tính đi'.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "requires_owner": True,
    },
    {
        "name": "restart_computer",
        "description": "Khởi động lại TOÀN BỘ máy tính sau 30 giây — chỉ gọi khi Sơn yêu cầu thật rõ ràng và chắc chắn.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "requires_owner": True,
    },
    {
        "name": "cancel_shutdown",
        "description": "Huỷ lệnh tắt máy/khởi động lại đang đếm ngược (nếu Sơn vừa đổi ý hoặc lỡ tay).",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "requires_owner": True,
    },
    {
        "name": "open_folder",
        "description": "Mở nhanh 1 trong 3 thư mục: Desktop (màn hình), Downloads (tải xuống), Documents (tài liệu).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tên thư mục: 'desktop', 'downloads' hoặc 'documents'"},
            },
            "required": ["name"],
        },
        "requires_owner": True,
    },
    {
        "name": "adjust_volume",
        "description": "Tăng, giảm hoặc tắt/bật tiếng loa máy tính (server).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "'up' (tăng), 'down' (giảm), hoặc 'mute' (tắt/bật tiếng)"},
            },
            "required": ["action"],
        },
        "requires_owner": True,
    },
    {
        "name": "search_google",
        "description": "Tìm kiếm 1 từ khoá trên Google và mở kết quả trong trình duyệt.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nội dung cần tìm kiếm"},
            },
            "required": ["query"],
        },
        "requires_owner": True,
    },
    {
        "name": "search_youtube",
        "description": "Tìm kiếm hoặc phát nhạc/video trên YouTube — mở kết quả tìm kiếm để Sơn chọn video cần phát.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Từ khoá hoặc tên bài hát/video cần tìm"},
            },
            "required": ["query"],
        },
        "requires_owner": True,
    },
    {
        "name": "get_weather",
        "description": "Xem thời tiết hiện tại tại 1 thành phố cụ thể.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Tên thành phố, ví dụ 'Ho Chi Minh', 'Ha Noi'"},
            },
            "required": ["city"],
        },
        "requires_owner": False,
    },
    {
        "name": "get_disk_usage",
        "description": "Kiểm tra dung lượng ổ đĩa còn trống trên máy server.",
        "parameters": {
            "type": "object",
            "properties": {
                "drive": {"type": "string", "description": "Ổ đĩa cần kiểm tra, ví dụ 'C:' hoặc 'E:' — để trống kiểm tra ổ đang chứa EVA"},
            },
            "required": [],
        },
        "requires_owner": True,
    },
    {
        "name": "git_status",
        "description": "Xem trạng thái git (file đã sửa/chưa commit, nhánh hiện tại) của 1 dự án lập trình đã cấu hình sẵn trong settings.yaml.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Tên dự án đã cấu hình trong settings.yaml (mục dev.projects), ví dụ 'eva'"},
            },
            "required": ["project"],
        },
        "requires_owner": True,
    },
    {
        "name": "git_log",
        "description": "Xem các commit gần đây của 1 dự án lập trình đã cấu hình sẵn trong settings.yaml.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Tên dự án đã cấu hình trong settings.yaml (mục dev.projects)"},
                "limit": {"type": "integer", "description": "Số commit gần nhất cần xem, mặc định 5"},
            },
            "required": ["project"],
        },
        "requires_owner": True,
    },
    {
        "name": "tail_log_file",
        "description": "Xem các dòng cuối của 1 file log đã cấu hình sẵn trong settings.yaml — dùng để kiểm tra nhanh lỗi/hoạt động gần đây của 1 dịch vụ.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tên file log đã cấu hình trong settings.yaml (mục dev.log_files)"},
                "lines": {"type": "integer", "description": "Số dòng cuối cần xem, mặc định 20"},
            },
            "required": ["name"],
        },
        "requires_owner": True,
    },
    {
        "name": "check_service_status",
        "description": "Kiểm tra 1 dịch vụ Windows (Windows service) có đang chạy hay không theo tên service.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tên service Windows cần kiểm tra, ví dụ 'wuauserv', 'Spooler'"},
            },
            "required": ["name"],
        },
        "requires_owner": True,
    },
    {
        "name": "check_github_prs",
        "description": "Xem danh sách Pull Request đang mở trên GitHub của 1 dự án lập trình đã cấu hình sẵn trong settings.yaml.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Tên dự án đã cấu hình trong settings.yaml (mục dev.projects)"},
            },
            "required": ["project"],
        },
        "requires_owner": True,
    },
    {
        "name": "check_github_issues",
        "description": "Xem danh sách issue trên GitHub đang được gán (assign) cho chủ nhân, của 1 dự án lập trình đã cấu hình sẵn trong settings.yaml.",
        "parameters": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Tên dự án đã cấu hình trong settings.yaml (mục dev.projects)"},
            },
            "required": ["project"],
        },
        "requires_owner": True,
    },
]

_REQUIRES_OWNER = {spec["name"]: spec["requires_owner"] for spec in TOOL_SPECS}


def as_ollama_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        }
        for spec in TOOL_SPECS
    ]


def as_gemini_tools():
    # import tại chỗ — chỉ cần khi thực sự gọi Gemini, tránh phụ thuộc google-genai
    # cho các nơi khác chỉ dùng tool offline (Ollama)
    from google.genai import types

    return [
        types.FunctionDeclaration(
            name=spec["name"], description=spec["description"], parameters=spec["parameters"]
        )
        for spec in TOOL_SPECS
    ]


def execute(name, args, is_owner=None, source=None):
    # bảo mật chặt: chỉ cho chạy tool nhạy cảm khi ĐÃ xác minh chắc chắn là chủ nhân qua giọng nói
    # (is_owner=True) — is_owner=None (chưa đăng ký giọng/chưa xác định được) hoặc False (giọng lạ)
    # đều bị chặn như nhau.
    if _REQUIRES_OWNER.get(name) and is_owner is not True:
        return "Từ chối: chưa xác minh được chủ nhân qua giọng nói, chạy enroll_voice.py để đăng ký."

    if name == "open_url":
        return _open_url(args.get("url", ""), source=source)
    if name == "get_last_login":
        return _get_last_login()
    if name == "open_app":
        return _open_app(args.get("name", ""), source=source)
    if name == "get_conversation_history":
        return _get_conversation_history(args.get("limit", 10))
    if name == "save_note":
        return _save_note(args.get("content", ""))
    if name == "get_notes":
        return _get_notes(args.get("limit", 10))
    if name == "get_system_status":
        return _get_system_status()
    if name == "log_health":
        return _log_health(args.get("category", ""), args.get("content", ""))
    if name == "get_health_logs":
        return _get_health_logs(args.get("category"), args.get("limit", 10))
    if name == "get_health_summary":
        return _get_health_summary(args.get("category", ""), args.get("days", 7))
    if name == "set_reminder":
        return _set_reminder(args.get("message", ""), args.get("remind_at", ""))
    if name == "get_reminders":
        return _get_reminders()
    if name == "cancel_reminder":
        return _cancel_reminder(_to_int(args.get("id"), None))
    if name == "take_screenshot":
        return _take_screenshot()
    if name == "lock_computer":
        return _lock_computer()
    if name == "shutdown_computer":
        return _shutdown_computer()
    if name == "restart_computer":
        return _restart_computer()
    if name == "cancel_shutdown":
        return _cancel_shutdown()
    if name == "open_folder":
        return _open_folder(args.get("name", ""), source=source)
    if name == "adjust_volume":
        return _adjust_volume(args.get("action", ""))
    if name == "search_google":
        return _search_google(args.get("query", ""), source=source)
    if name == "search_youtube":
        return _search_youtube(args.get("query", ""), source=source)
    if name == "get_weather":
        return _get_weather(args.get("city", ""))
    if name == "get_disk_usage":
        return _get_disk_usage(args.get("drive"))
    if name == "git_status":
        return _git_status(args.get("project", ""))
    if name == "git_log":
        return _git_log(args.get("project", ""), args.get("limit", 5))
    if name == "tail_log_file":
        return _tail_log_file(args.get("name", ""), args.get("lines", 20))
    if name == "check_service_status":
        return _check_service_status(args.get("name", ""))
    if name == "check_github_prs":
        return _check_github_prs(args.get("project", ""))
    if name == "check_github_issues":
        return _check_github_issues(args.get("project", ""))

    return f"Lỗi: không rõ tool '{name}'"


def _open_url(url, source=None):
    if not url:
        return "Lỗi: thiếu URL."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    # Lệnh gõ chữ hoặc nói qua trình duyệt (source="text"/"web_voice") trong lúc
    # laptop_idle_agent.py đang kết nối -> mở ngay trên laptop của Sơn thay vì server, vì lúc
    # đó gần như chắc chắn Sơn đang ở xa. Lệnh qua mic vật lý (source="voice") thì luôn ở lại
    # server như cũ.
    if source in ("text", "web_voice") and remote_exec.executor.laptop_connected:
        result = remote_exec.executor.request("open_url", {"url": url})
        if result is not None:
            return result
        # Hết giờ chờ (agent vừa mất kết nối giữa chừng) -> rơi về mở trên server, không bỏ lỡ lệnh
    webbrowser.open(url)
    return f"Đã mở {url} trên máy server."


def _get_last_login():
    timestamp = get_db().get_last_login()
    if not timestamp:
        return "Không có dữ liệu về lần đăng nhập trước đó."
    return f"Lần khởi động gần nhất trước phiên này: {timestamp}"


def _open_app(name, source=None):
    if not name:
        return "Lỗi: thiếu tên ứng dụng."
    if source in ("text", "web_voice") and remote_exec.executor.laptop_connected:
        result = remote_exec.executor.request("open_app", {"name": name})
        if result is not None:
            return result
    try:
        os.startfile(name)
        return f"Đã mở {name} trên máy server."
    except OSError as e:
        return f"Không mở được '{name}': {e}"


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_conversation_history(limit=10):
    rows = get_db().get_conversation_history(limit=_to_int(limit, 10))
    if not rows:
        return "Chưa có lịch sử hội thoại."
    return "\n".join(f"[{role}] {content}" for role, content, _ts in rows)


def _save_note(content):
    if not content:
        return "Lỗi: thiếu nội dung ghi chú."
    ok = get_db().save_note(content)
    return "Đã lưu ghi chú." if ok else "Lỗi khi lưu ghi chú."


def _get_notes(limit=10):
    rows = get_db().get_notes(limit=_to_int(limit, 10))
    if not rows:
        return "Chưa có ghi chú nào."
    return "\n".join(f"- {content} ({ts})" for content, ts in rows)


def _log_health(category, content):
    if not category or not content:
        return "Lỗi: thiếu loại hoặc nội dung sức khoẻ."
    ok = get_db().save_health_log(category.strip(), content.strip())
    return f"Đã ghi nhận sức khoẻ ({category})." if ok else "Lỗi khi ghi nhận sức khoẻ."


def _get_health_logs(category, limit=10):
    rows = get_db().get_health_logs(category=category or None, limit=_to_int(limit, 10))
    if not rows:
        return "Chưa có dữ liệu sức khoẻ nào được ghi." + (f" (loại '{category}')" if category else "")
    return "\n".join(f"- [{cat}] {content} ({ts})" for cat, content, ts in rows)


def _get_health_summary(category, days=7):
    if not category:
        return "Lỗi: thiếu loại sức khoẻ cần tóm tắt."
    days = _to_int(days, 7)
    cutoff = datetime.now() - timedelta(days=days)

    # Lọc theo N ngày ở Python (không dùng datetime('now') của SQLite) — timestamp lưu bằng
    # datetime.now() là giờ local, còn datetime('now') mặc định trả UTC, gộp 2 cái sẽ lệch múi giờ.
    rows = get_db().get_health_logs(category=category, limit=200)
    recent = []
    for _cat, content, ts in rows:
        parsed = parse_db_timestamp(ts)
        if parsed and parsed >= cutoff:
            recent.append((content, parsed))

    if not recent:
        return f"Chưa có dữ liệu '{category}' trong {days} ngày gần đây."

    recent.sort(key=lambda x: x[1])  # cũ -> mới
    numeric = [(extract_number(content), t) for content, t in recent]
    numeric = [(v, t) for v, t in numeric if v is not None]

    lines = [f"Có {len(recent)} lần ghi '{category}' trong {days} ngày gần đây."]
    if numeric:
        values = [v for v, _t in numeric]
        avg = sum(values) / len(values)
        first_v, _ = numeric[0]
        last_v, last_t = numeric[-1]
        if last_v > first_v:
            trend = f"tăng {last_v - first_v:.1f} so với lần đầu trong khoảng"
        elif last_v < first_v:
            trend = f"giảm {first_v - last_v:.1f} so với lần đầu trong khoảng"
        else:
            trend = "không đổi so với lần đầu trong khoảng"
        lines.append(
            f"Trung bình: {avg:.1f}. Gần nhất: {last_v:.1f} ({last_t.strftime('%d/%m %H:%M')}). Xu hướng: {trend}."
        )
    else:
        lines.append("Không trích được số liệu cụ thể từ nội dung đã ghi, chỉ có mô tả dạng chữ.")
    return "\n".join(lines)


def _get_system_status():
    from core.temp_monitor import get_gpu_temp

    cpu, ram = get_live_stats()
    mem = psutil.virtual_memory()
    status = (
        f"CPU đang dùng {cpu:.0f}%, RAM đang dùng {ram:.0f}% "
        f"({mem.used // (1024 ** 3)}GB / {mem.total // (1024 ** 3)}GB)."
    )
    gpu_temp = get_gpu_temp()
    if gpu_temp is not None:
        status += f" GPU đang {gpu_temp}°C."
    return status


def _set_reminder(message, remind_at):
    if not message or not remind_at:
        return "Lỗi: thiếu nội dung hoặc thời điểm nhắc."

    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(remind_at, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return f"Lỗi: không hiểu định dạng thời gian '{remind_at}', cần dạng YYYY-MM-DD HH:MM:SS."
    if parsed <= datetime.now():
        return "Lỗi: thời điểm nhắc phải ở tương lai, không phải quá khứ/hiện tại."

    reminder_id = get_db().save_reminder(message.strip(), parsed)
    if reminder_id is None:
        return "Lỗi: không lưu được nhắc nhở."
    return f"Đã đặt nhắc nhở #{reminder_id}: '{message}' lúc {parsed.strftime('%H:%M %d/%m/%Y')}."


def _get_reminders():
    rows = get_db().get_pending_reminders()
    if not rows:
        return "Hiện không có nhắc nhở nào đang chờ."
    return "\n".join(f"#{rid}: {msg} lúc {remind_at}" for rid, msg, remind_at in rows)


def _cancel_reminder(reminder_id):
    if reminder_id is None:
        return "Lỗi: thiếu ID nhắc nhở cần huỷ — dùng get_reminders để xem ID."
    ok = get_db().cancel_reminder(reminder_id)
    return f"Đã huỷ nhắc nhở #{reminder_id}." if ok else f"Không tìm thấy nhắc nhở #{reminder_id} đang chờ."


def _take_screenshot():
    from PIL import ImageGrab

    os.makedirs("screenshots", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = f"screenshots/screenshot_{ts}.png"
    try:
        ImageGrab.grab().save(path)
    except Exception as e:
        return f"Lỗi khi chụp màn hình: {e}"
    return f"Đã chụp màn hình, lưu tại {path}."


def _lock_computer():
    try:
        ctypes.windll.user32.LockWorkStation()
        return "Đã khoá máy."
    except Exception as e:
        return f"Lỗi khi khoá máy: {e}"


_SHUTDOWN_DELAY_SECS = 30  # luôn có độ trễ để kịp huỷ nếu lỡ tay/nghe nhầm, không bao giờ tắt ngay


def _shutdown_computer():
    os.system(f"shutdown /s /t {_SHUTDOWN_DELAY_SECS}")
    return f"Sẽ tắt máy sau {_SHUTDOWN_DELAY_SECS} giây — nói 'huỷ tắt máy' ngay nếu đây là nhầm lẫn."


def _restart_computer():
    os.system(f"shutdown /r /t {_SHUTDOWN_DELAY_SECS}")
    return f"Sẽ khởi động lại máy sau {_SHUTDOWN_DELAY_SECS} giây — nói 'huỷ tắt máy' ngay nếu đây là nhầm lẫn."


def _cancel_shutdown():
    result = os.system("shutdown /a")
    return "Đã huỷ lệnh tắt/khởi động lại." if result == 0 else "Không có lệnh tắt/khởi động lại nào đang chờ."


_FOLDER_SHORTCUTS = {
    "desktop": "Desktop", "màn hình": "Desktop", "man hinh": "Desktop",
    "downloads": "Downloads", "tải xuống": "Downloads", "tai xuong": "Downloads",
    "documents": "Documents", "tài liệu": "Documents", "tai lieu": "Documents",
}


def _open_folder(name, source=None):
    folder = _FOLDER_SHORTCUTS.get((name or "").strip().lower())
    if not folder:
        return f"Lỗi: chưa hỗ trợ thư mục '{name}' — chỉ hỗ trợ Desktop/Downloads/Documents."

    # Gửi TÊN thư mục (không phải đường dẫn đầy đủ) sang laptop — đường dẫn Desktop của
    # server (vd C:\Users\DUONG TRUONG SON\Desktop) không tồn tại trên laptop vì khác tài
    # khoản Windows. Mỗi máy tự ghép với thư mục home của chính nó (xem laptop_idle_agent.py).
    if source in ("text", "web_voice") and remote_exec.executor.laptop_connected:
        result = remote_exec.executor.request("open_folder", {"folder": folder})
        if result is not None:
            return result

    path = os.path.join(os.path.expanduser("~"), folder)
    try:
        os.startfile(path)
        return f"Đã mở thư mục {folder} trên máy server."
    except OSError as e:
        return f"Không mở được thư mục '{folder}': {e}"


_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_KEYEVENTF_EXTENDEDKEY = 0x1
_KEYEVENTF_KEYUP = 0x2


def _send_media_key(vk):
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY, 0)
    ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY | _KEYEVENTF_KEYUP, 0)


def _adjust_volume(action):
    # Luôn chỉnh âm lượng SERVER, không định tuyến sang laptop dù source là text/web_voice —
    # Sơn đã có phím âm lượng vật lý ngay trên laptop, định tuyến sang đó vô nghĩa.
    action = (action or "").strip().lower()
    try:
        if action in ("up", "tăng", "tang"):
            for _ in range(4):
                _send_media_key(_VK_VOLUME_UP)
            return "Đã tăng âm lượng trên máy server."
        if action in ("down", "giảm", "giam"):
            for _ in range(4):
                _send_media_key(_VK_VOLUME_DOWN)
            return "Đã giảm âm lượng trên máy server."
        if action in ("mute", "tắt", "tat", "câm", "cam"):
            _send_media_key(_VK_VOLUME_MUTE)
            return "Đã tắt/bật lại tiếng trên máy server."
    except Exception as e:
        return f"Lỗi khi chỉnh âm lượng: {e}"
    return "Lỗi: action phải là 'up', 'down' hoặc 'mute'."


def _search_google(query, source=None):
    if not query:
        return "Lỗi: thiếu nội dung cần tìm kiếm."
    return _open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(query), source=source)


def _search_youtube(query, source=None):
    if not query:
        return "Lỗi: thiếu nội dung cần tìm kiếm."
    return _open_url(
        "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query), source=source
    )


def _get_weather(city):
    if not city:
        return "Lỗi: thiếu tên thành phố cần xem thời tiết."
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return "Lỗi: chưa cấu hình OPENWEATHER_API_KEY trong .env — Sơn cần đăng ký key miễn phí tại openweathermap.org rồi thêm vào .env."

    import json
    import urllib.request

    url = "https://api.openweathermap.org/data/2.5/weather?" + urllib.parse.urlencode({
        "q": city, "appid": api_key, "units": "metric", "lang": "vi",
    })
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"Lỗi khi lấy thời tiết: {e}"

    if str(data.get("cod")) != "200":
        return f"Không tìm được thời tiết cho '{city}': {data.get('message', 'lỗi không rõ')}."

    desc = data["weather"][0]["description"]
    temp = data["main"]["temp"]
    feels = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    return f"Thời tiết tại {city}: {desc}, {temp:.0f}°C (cảm giác như {feels:.0f}°C), độ ẩm {humidity}%."


def _get_disk_usage(drive=None):
    target = (drive or "").strip() or os.path.splitdrive(os.path.abspath("."))[0]
    if not target.endswith("\\"):
        target += "\\"
    try:
        total, used, free = shutil.disk_usage(target)
    except OSError as e:
        return f"Lỗi: không đọc được ổ đĩa '{target}': {e}"
    gb = 1024 ** 3
    return (
        f"Ổ {target}: còn trống {free / gb:.1f}GB / tổng {total / gb:.1f}GB "
        f"({used / total * 100:.0f}% đã dùng)."
    )


def _resolve_project_path(project):
    projects = _get_dev_config().get("projects", {}) or {}
    return projects.get((project or "").strip().lower())


def _unknown_project_error(project, known):
    known_str = ", ".join(known) if known else "(chưa cấu hình dự án nào — thêm vào settings.yaml mục dev.projects)"
    return f"Lỗi: chưa cấu hình dự án '{project}'. Các dự án đã biết: {known_str}"


def _run_git(path, args, timeout=10):
    try:
        return subprocess.run(
            ["git", *args], cwd=path, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def _git_status(project):
    path = _resolve_project_path(project)
    if not path:
        return _unknown_project_error(project, _get_dev_config().get("projects", {}).keys())
    result = _run_git(path, ["status", "--short", "--branch"])
    if result is None:
        return "Lỗi: không chạy được git (chưa cài git hoặc hết thời gian chờ)."
    if result.returncode != 0:
        return f"Lỗi git status: {result.stderr.strip()}"
    output = result.stdout.strip()
    return output if output else "Không có thay đổi nào chưa commit."


def _git_log(project, limit=5):
    path = _resolve_project_path(project)
    if not path:
        return _unknown_project_error(project, _get_dev_config().get("projects", {}).keys())
    limit = max(1, min(_to_int(limit, 5), 50))
    result = _run_git(path, ["log", f"-{limit}", "--oneline"])
    if result is None:
        return "Lỗi: không chạy được git (chưa cài git hoặc hết thời gian chờ)."
    if result.returncode != 0:
        return f"Lỗi git log: {result.stderr.strip()}"
    return result.stdout.strip() or "Chưa có commit nào."


def _tail_log_file(name, lines=20):
    log_files = _get_dev_config().get("log_files", {}) or {}
    path = log_files.get((name or "").strip().lower())
    if not path:
        known = ", ".join(log_files.keys()) or "(chưa cấu hình file log nào — thêm vào settings.yaml mục dev.log_files)"
        return f"Lỗi: chưa cấu hình file log '{name}'. Các file đã biết: {known}"
    lines = max(1, min(_to_int(lines, 20), 200))
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            # Chỉ đọc tối đa 1MB cuối file — đủ cho vài trăm dòng thông thường, tránh nạp cả
            # file log nhiều GB vào RAM chỉ để lấy vài chục dòng cuối.
            chunk = min(size, 1024 * 1024)
            f.seek(size - chunk)
            data = f.read().decode("utf-8", errors="replace")
    except OSError as e:
        return f"Lỗi khi đọc file log '{name}': {e}"
    tail = data.splitlines()[-lines:]
    return "\n".join(tail) if tail else "(file trống)"


def _check_service_status(name):
    name = (name or "").strip()
    if not name:
        return "Lỗi: thiếu tên service cần kiểm tra."
    try:
        svc = psutil.win_service_get(name)
        info = svc.as_dict()
    except psutil.NoSuchProcess:
        return f"Không tìm thấy service '{name}' trên máy."
    except AttributeError:
        return "Lỗi: kiểm tra service chỉ hỗ trợ trên Windows."
    except Exception as e:
        return f"Lỗi khi kiểm tra service '{name}': {e}"
    status = info.get("status", "không rõ")
    pid = info.get("pid")
    return f"Service '{name}': {status}" + (f" (PID {pid})" if pid else "")


def _run_gh(path, args, timeout=15):
    try:
        return subprocess.run(
            ["gh", *args], cwd=path, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def _check_github_prs(project):
    path = _resolve_project_path(project)
    if not path:
        return _unknown_project_error(project, _get_dev_config().get("projects", {}).keys())
    result = _run_gh(path, ["pr", "list", "--state", "open"])
    if result is None:
        return "Lỗi: không chạy được gh (chưa cài GitHub CLI hoặc hết thời gian chờ)."
    if result.returncode != 0:
        return f"Lỗi khi xem PR: {result.stderr.strip()}"
    output = result.stdout.strip()
    return output if output else "Không có pull request nào đang mở."


def _check_github_issues(project):
    path = _resolve_project_path(project)
    if not path:
        return _unknown_project_error(project, _get_dev_config().get("projects", {}).keys())
    result = _run_gh(path, ["issue", "list", "--assignee", "@me", "--state", "open"])
    if result is None:
        return "Lỗi: không chạy được gh (chưa cài GitHub CLI hoặc hết thời gian chờ)."
    if result.returncode != 0:
        return f"Lỗi khi xem issue: {result.stderr.strip()}"
    output = result.stdout.strip()
    return output if output else "Không có issue nào đang gán cho bạn."
