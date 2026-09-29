import json
import os
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime

import yaml
from dotenv import load_dotenv

# eSMS.vn — cổng SMS phổ biến ở Việt Nam, gửi qua HTTP API, trả phí theo tin.
# Tài liệu: https://developers.esms.vn — SmsType "2" = tin CSKH qua brandname.
ESMS_URL = "https://rest.esms.vn/MainService.svc/json/SendMultipleMessage_V4_post_json/"
ESMS_SUCCESS_CODE = "100"

SEND_RETRIES = 3          # SOS mà rớt mạng 1 nhịp thì thử lại, không bỏ cuộc ngay lần đầu
RETRY_DELAY_SECS = 2
SOS_COOLDOWN_SECS = 60    # người dùng hoảng có thể kêu "cứu tôi" liên tục — chỉ gửi 1 lượt/phút
SMS_MAX_CHARS = 160       # 1 tin SMS không dấu — vượt quá bị tính thành nhiều tin

_config_cache = None
_last_sos_time = 0.0
_sos_lock = threading.Lock()


def _get_config():
    """Đọc mục 'caregiver' trong config/settings.yaml, cache lại — module này được gọi từ cả
    main.py lẫn core/tools.py (request_help) nên tự đọc config, cùng kiểu với tools.py's
    _get_dev_config(). Sửa settings.yaml cần khởi động lại EVA để áp dụng."""
    global _config_cache
    if _config_cache is None:
        try:
            with open("config/settings.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except OSError:
            cfg = {}
        _config_cache = cfg.get("caregiver", {}) or {}
    return _config_cache


def _credentials():
    # API key/secret để trong .env (bí mật, không commit); số điện thoại + brandname để trong
    # settings.yaml (đổi theo từng hộ gia đình) — cùng cách tách với FAMILY_TOKEN.
    load_dotenv()
    api_key = os.getenv("ESMS_API_KEY", "").strip()
    secret = os.getenv("ESMS_SECRET_KEY", "").strip()
    phones = [str(p).strip() for p in (_get_config().get("phones") or []) if str(p).strip()]
    return api_key, secret, phones


def get_contacts():
    """Danh bạ người thân để gọi video (caregiver.contacts trong settings.yaml)."""
    return [c for c in (_get_config().get("contacts") or []) if isinstance(c, dict)]


def is_configured():
    api_key, secret, phones = _credentials()
    return bool(api_key and secret and phones)


def _to_plain(text):
    """Bỏ dấu tiếng Việt — tin có dấu (Unicode) chỉ chứa ~70 ký tự/tin và đắt gấp đôi; tin
    cảnh báo ngắn không dấu vẫn đọc hiểu được."""
    text = text.replace("đ", "d").replace("Đ", "D").replace("—", "-").replace("–", "-")
    nfd = unicodedata.normalize("NFD", text)
    plain = "".join(c for c in nfd if not unicodedata.combining(c))
    return plain.encode("ascii", "ignore").decode("ascii")  # ký tự lạ còn sót (emoji...) làm tin bị tính Unicode


def _send_one(api_key, secret, phone, content):
    body = json.dumps({
        "ApiKey": api_key,
        "SecretKey": secret,
        "Phone": phone,
        "Content": content,
        "SmsType": "2",
        "Brandname": _get_config().get("sms_brandname", ""),
        "IsUnicode": "0",
    }).encode("utf-8")
    req = urllib.request.Request(ESMS_URL, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(1, SEND_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode("utf-8") or "{}")
            if str(result.get("CodeResult")) == ESMS_SUCCESS_CODE:
                return True
            # Mã lỗi nghiệp vụ (sai key, hết tiền, sai brandname/nội dung chưa đăng ký...) —
            # thử lại cũng vô ích.
            print(f"[Notifier] eSMS từ chối gửi tới {phone}: {result}")
            return False
        except Exception as e:
            print(f"[Notifier] Lần {attempt}/{SEND_RETRIES} không gửi được tới {phone}: {e}")
        if attempt < SEND_RETRIES:
            time.sleep(RETRY_DELAY_SECS)
    return False


def notify(message, phones=None):
    """Nhắn SMS kèm thời gian cho `phones`, mặc định là tất cả số người thân trong
    caregiver.phones. Trả True nếu ít nhất 1 số nhận được. Trả False (không raise) nếu chưa cấu hình hoặc gửi lỗi — cảnh báo
    tại chỗ (TTS) vẫn phải chạy được dù kênh này hỏng."""
    api_key, secret, default_phones = _credentials()
    phones = [str(p).strip() for p in phones if str(p).strip()] if phones else default_phones
    if not (api_key and secret and phones):
        return False
    stamp = datetime.now().strftime("%H:%M %d/%m")
    content = _to_plain(f"EVA {stamp}: {message}")[:SMS_MAX_CHARS]
    sent = [p for p in phones if _send_one(api_key, secret, p, content)]
    if sent:
        print(f"[Notifier] Đã nhắn SMS cho {len(sent)}/{len(phones)} số: {content}")
    return bool(sent)


def send_sos(reason):
    """Cảnh báo khẩn cấp. Trả về:
      "sent"         — đã gửi được
      "recent"       — vừa gửi trong SOS_COOLDOWN_SECS, không gửi lặp
      "unconfigured" — chưa cài SMS
      "failed"       — cài rồi nhưng gửi lỗi (mất mạng, hết tiền...)"""
    global _last_sos_time
    if not is_configured():
        return "unconfigured"
    with _sos_lock:
        if time.time() - _last_sos_time < SOS_COOLDOWN_SECS:
            return "recent"
        reason = (reason or "").strip() or "khong ro ly do"
        ok = notify(f"KHAN CAP - can nguoi toi giup ngay. Nghe duoc: \"{reason}\"")
        if ok:
            _last_sos_time = time.time()
        return "sent" if ok else "failed"
