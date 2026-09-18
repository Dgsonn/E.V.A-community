"""
Script này CHẠY TRÊN LAPTOP của Sơn — KHÔNG chạy trên PC server đang chạy EVA.

EVA (main.py) giờ chạy trên 1 PC server riêng, không phải máy Sơn dùng hàng ngày, nên có
3 việc server không tự làm được nếu chỉ đứng một mình:
  1. core/activity_monitor.py không còn tự biết được Sơn có đang dùng máy hay không (nó
     chỉ đo được thao tác bàn phím/chuột của chính cái máy nó đang chạy, tức là server).
  2. Lệnh "mở notepad"/"mở link" gõ/nói qua dashboard lúc Sơn ở xa sẽ mở nhầm trên màn
     hình server thay vì trên laptop Sơn đang cầm (xem core/tools.py, core/remote_exec.py).
  3. Dashboard web chỉ nói chuyện được bằng giọng nếu Sơn tự bấm nút mỗi lần (trình duyệt
     không được phép ghi âm ngầm liên tục) — không "luôn lắng nghe" rảnh tay như server.

Script này chạy 3 vòng lặp song song để bù cả 3 việc trên:
  - Mỗi 60s: đo thời gian rảnh của laptop (cùng kỹ thuật GetLastInputInfo với
    core/activity_monitor.py's get_idle_seconds(), chỉ khác là chạy ở đây) rồi gửi về
    /api/laptop_heartbeat để activity_monitor gộp vào tín hiệu "Sơn đang dùng máy".
  - Mỗi ~2s: hỏi /api/laptop_pending_command xem server có lệnh nào cần thực thi tại chỗ
    không (mở app/link) — nếu có thì chạy ngay trên laptop rồi báo kết quả về qua
    /api/laptop_command_result.
  - Liên tục: mở mic laptop, chờ vỗ tay/búng tay 2 cái (không dùng wakeword bằng giọng vì
    sẽ phải cài thêm transformers+torch nặng nề chỉ để nhận diện — vỗ tay chỉ cần phân
    tích biên độ âm thanh, nhẹ hơn hẳn). Vỗ xong thì ghi câu lệnh tới khi im lặng, gửi lên
    /api/voice (đúng route đã xây cho tính năng giọng nói qua trình duyệt — route này
    không quan tâm WAV đến từ trình duyệt hay từ script này), rồi phát lại câu trả lời.

Cách dùng:
  1. Copy file này sang laptop (không cần copy cả repo).
  2. Cài thêm thư viện cho phần ghi âm/phát lại (phần heartbeat + nhận lệnh ở trên vẫn
     chỉ cần thư viện chuẩn, nhưng ghi âm mic thật thì cần cài thêm):
       pip install pyaudio webrtcvad-wheels numpy pygame requests
  3. Sửa SERVER_BASE bên dưới thành địa chỉ LAN/VPN thật của PC server.
  4. (Tuỳ chọn) sửa MIC_INDEX nếu laptop có nhiều mic và muốn chọn đúng cái — script sẽ in
     danh sách mic khả dụng lúc khởi động để tham khảo.
  5. Thêm vào Windows Startup (shell:startup) để tự chạy nền mỗi lần đăng nhập laptop, vd:
       pythonw laptop_idle_agent.py
"""

import base64
import ctypes
import io
import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave
import webbrowser
from collections import deque
from ctypes import wintypes

import numpy as np
import pyaudio
import pygame
import requests
import webrtcvad

SERVER_BASE = "http://100.80.217.60:5000"  # IP Tailscale của server (desktop-5ggo7mc) — laptop
# phải cài Tailscale + đăng nhập ĐÚNG tài khoản Dgsonn thì mới gọi tới được, dù không cùng WiFi
# nhà (đi làm/quán cà phê/4G vẫn hoạt động). Script này chạy Python thuần không qua trình duyệt
# nên không cần HTTPS như dashboard web — HTTP thường qua Tailscale là đủ, không lộ ra Internet.
DASHBOARD_TOKEN = "DQcUlxGzbOHSlxgz2exFHWFy5MGTfXDU"  # trùng với .env trên server (DASHBOARD_TOKEN) — đổi lại nếu server tự sinh token mới
AUTH_HEADERS = {"X-Auth-Token": DASHBOARD_TOKEN}
HEARTBEAT_URL = f"{SERVER_BASE}/api/laptop_heartbeat"
PENDING_COMMAND_URL = f"{SERVER_BASE}/api/laptop_pending_command"
COMMAND_RESULT_URL = f"{SERVER_BASE}/api/laptop_command_result"
VOICE_URL = f"{SERVER_BASE}/api/voice"

HEARTBEAT_INTERVAL_SECS = 60
COMMAND_POLL_INTERVAL_SECS = 2

# --- Cấu hình ghi âm/vỗ tay — mirror mặc định bên core/voice_engine.py và config/settings.yaml ---
MIC_INDEX = None  # None = mic mặc định của hệ thống; đổi thành số nếu laptop có nhiều mic
RATE = 16000
FRAME_MS = 30  # webrtcvad chỉ chấp nhận 10/20/30ms
FRAME_SAMPLES = int(RATE * FRAME_MS / 1000)
CLAP_THRESHOLD_MULTIPLIER = 5.0
CLAP_WINDOW_SECS = 1.5
VAD_AGGRESSIVENESS = 2
SILENCE_SECS = 1.2
MIN_RECORD_SECS = 0.5
MAX_RECORD_SECS = 10


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds():
    """Số giây kể từ lần cuối có thao tác bàn phím/chuột trên CHÍNH máy này (Windows only)
    — cùng kỹ thuật với core/activity_monitor.py's get_idle_seconds()."""
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return millis / 1000.0


def _post_json(url, payload, timeout=10):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", **AUTH_HEADERS}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _get_json(url, timeout=10):
    req = urllib.request.Request(url, headers=AUTH_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def heartbeat_loop():
    print(f"[LaptopIdleAgent] Gửi idle_seconds về {HEARTBEAT_URL} mỗi {HEARTBEAT_INTERVAL_SECS}s")
    while True:
        idle = get_idle_seconds()
        try:
            _post_json(HEARTBEAT_URL, {"idle_seconds": idle})
        except (urllib.error.URLError, OSError) as e:
            # Server tạm không kết nối được (mất mạng, off VPN, server đang khởi động lại...)
            # — bỏ qua lượt này, thử lại ở vòng lặp sau, không làm chết script.
            print(f"[LaptopIdleAgent] Không gửi được heartbeat: {e}")
        time.sleep(HEARTBEAT_INTERVAL_SECS)


def _play_audio_b64(audio_b64):
    """Giải mã + phát 1 đoạn mp3 base64 qua loa laptop — dùng chung bởi lệnh 'speak' (đẩy từ
    main.py's on_proactive_alert) và có thể tái dùng sau này cho việc khác cần phát audio."""
    if not audio_b64:
        return
    pygame.mixer.init()
    audio_bytes = base64.b64decode(audio_b64)
    tmp_path = os.path.join(tempfile.gettempdir(), "eva_push.mp3")
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)
    pygame.mixer.music.load(tmp_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)


def _execute_command(cmd):
    """Thực thi ngay trên laptop — open_app/open_url giống core/tools.py (chạy ở đây thay vì
    server); speak là lệnh 'đẩy rồi thôi' từ main.py's on_proactive_alert (health/activity/
    daily/reminder chủ động lên tiếng) — không có id nên không cần trả kết quả về."""
    action = cmd.get("action")
    args = cmd.get("args") or {}
    try:
        if action == "open_app":
            name = args.get("name", "")
            os.startfile(name)
            return f"Đã mở {name} trên laptop của Sơn."
        if action == "open_url":
            url = args.get("url", "")
            webbrowser.open(url)
            return f"Đã mở {url} trên laptop của Sơn."
        if action == "open_folder":
            # Chỉ nhận TÊN thư mục (vd "Desktop"), không phải đường dẫn đầy đủ — server gửi
            # tên để mỗi máy tự ghép với thư mục home của chính mình (core/tools.py's
            # _open_folder không gửi thẳng path của server vì khác tài khoản Windows).
            folder = args.get("folder", "")
            path = os.path.join(os.path.expanduser("~"), folder)
            os.startfile(path)
            return f"Đã mở thư mục {folder} trên laptop của Sơn."
        if action == "speak":
            text = args.get("text", "")
            if text:
                print(f"[LaptopIdleAgent] EVA: {text}")
            _play_audio_b64(args.get("audio_b64", ""))
            return "OK"
        return f"Lỗi: laptop không hỗ trợ lệnh '{action}'."
    except OSError as e:
        return f"Không thực thi được trên laptop: {e}"


def command_poll_loop():
    print(f"[LaptopIdleAgent] Hỏi lệnh chờ tại {PENDING_COMMAND_URL} mỗi {COMMAND_POLL_INTERVAL_SECS}s")
    while True:
        try:
            cmd = _get_json(PENDING_COMMAND_URL)
            # Lệnh "push" (vd speak) không có "id" — vẫn cần thực thi, chỉ là không báo kết
            # quả về (không ai chờ). Lệnh "request" (open_app/open_url do tool gọi) có "id",
            # cần post kết quả về để core/remote_exec.py's request() đang chặn chờ nhận được.
            if cmd and cmd.get("action"):
                result = _execute_command(cmd)
                if cmd.get("id") is not None:
                    _post_json(COMMAND_RESULT_URL, {"id": cmd["id"], "result": result})
        except (urllib.error.URLError, OSError) as e:
            print(f"[LaptopIdleAgent] Không hỏi được lệnh chờ: {e}")
        time.sleep(COMMAND_POLL_INTERVAL_SECS)


class _ClapDetector:
    """Phát hiện mẫu vỗ tay/búng tay: 2 tiếng bộp ngắn (tấn nhanh, tắt nhanh) trong khoảng
    CLAP_WINDOW_SECS — khác tiếng nói (năng lượng kéo dài) và tiếng ồn ngẫu nhiên (1 tiếng
    bộp đơn lẻ không đủ). Bản sao trực tiếp từ core/voice_engine.py's _ClapDetector — cố
    tình sao chép thay vì import, vì script này chạy độc lập trên laptop, không có sẵn
    phần còn lại của repo."""

    ABS_MIN_PEAK = 1200.0
    BASELINE_EMA_ALPHA = 0.05
    MAX_SPIKE_RUN_FRAMES = 3
    MIN_CLAP_GAP = 0.15

    def __init__(self, threshold_multiplier, window_secs):
        self._threshold_multiplier = threshold_multiplier
        self._window_secs = window_secs
        self._baseline = 300.0
        self._spike_run = 0
        self._clap_times = deque(maxlen=2)

    def feed(self, data):
        peak = float(np.max(np.abs(np.frombuffer(data, dtype=np.int16).astype(np.float32))))
        is_spike = peak > max(self.ABS_MIN_PEAK, self._baseline * self._threshold_multiplier)

        if is_spike:
            self._spike_run += 1
            return False

        if 0 < self._spike_run <= self.MAX_SPIKE_RUN_FRAMES:
            now = time.time()
            if not self._clap_times or now - self._clap_times[-1] >= self.MIN_CLAP_GAP:
                self._clap_times.append(now)
            if len(self._clap_times) == 2 and (self._clap_times[1] - self._clap_times[0]) <= self._window_secs:
                self._spike_run = 0
                return True

        self._spike_run = 0
        self._baseline = (1 - self.BASELINE_EMA_ALPHA) * self._baseline + self.BASELINE_EMA_ALPHA * peak
        return False


def _record_command(stream, vad):
    """Ghi tới khi im lặng đủ lâu — adapt từ stage 2 của core/voice_engine.py's _record_once,
    bớt phần wake-word/session vì ở đây mỗi lượt vỗ tay là 1 lệnh riêng biệt."""
    silence_limit = int(SILENCE_SECS * 1000 / FRAME_MS)
    min_frames = int(MIN_RECORD_SECS * 1000 / FRAME_MS)
    max_frames = int(MAX_RECORD_SECS * 1000 / FRAME_MS)
    frames = []
    silent_frames = 0
    voice_started = False
    for _ in range(max_frames):
        data = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
        if vad.is_speech(data, RATE):
            voice_started = True
            silent_frames = 0
            frames.append(data)
        elif voice_started:
            frames.append(data)
            silent_frames += 1
            if silent_frames >= silence_limit:
                break
        # else: chưa bắt đầu nói thật, bỏ qua khung im lặng đầu (đệm sau tiếng vỗ tay)
    if len(frames) < min_frames:
        return None
    return frames


def _frames_to_wav_bytes(frames):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


def _send_voice_and_play(wav_bytes):
    try:
        resp = requests.post(
            VOICE_URL, files={"audio": ("voice.wav", wav_bytes, "audio/wav")}, headers=AUTH_HEADERS, timeout=40
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[LaptopIdleAgent] Gửi giọng nói lên server lỗi: {e}")
        return

    if data.get("status") != "ok":
        print(f"[LaptopIdleAgent] EVA: {data.get('message', data.get('status'))}")
        return

    print(f"[LaptopIdleAgent] Sơn: {data.get('transcript')}")
    print(f"[LaptopIdleAgent] EVA: {data.get('reply')}")

    audio_b64 = data.get("audio_b64")
    if not audio_b64:
        return
    audio_bytes = base64.b64decode(audio_b64)
    tmp_path = os.path.join(tempfile.gettempdir(), "eva_reply.mp3")
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)
    pygame.mixer.music.load(tmp_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)


def _print_mic_list(pa):
    print("[LaptopIdleAgent] Danh sách microphone khả dụng:")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            marker = " <-- ĐANG DÙNG" if i == MIC_INDEX else ""
            print(f"  [{i}] {info['name']}{marker}")


def voice_loop():
    pa = pyaudio.PyAudio()
    _print_mic_list(pa)
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    pygame.mixer.init()
    print("[LaptopIdleAgent] Voice: sẵn sàng — vỗ tay/búng tay 2 cái để bắt đầu nói với EVA.")

    while True:
        try:
            stream = pa.open(
                format=pyaudio.paInt16, channels=1, rate=RATE,
                input=True, input_device_index=MIC_INDEX, frames_per_buffer=FRAME_SAMPLES,
            )
            clap_detector = _ClapDetector(CLAP_THRESHOLD_MULTIPLIER, CLAP_WINDOW_SECS)

            # Chờ vỗ tay 2 cái
            while True:
                data = stream.read(FRAME_SAMPLES, exception_on_overflow=False)
                if clap_detector.feed(data):
                    break

            print("[LaptopIdleAgent] Đã nghe vỗ tay — đang ghi lệnh, nói luôn...")
            frames = _record_command(stream, vad)
            stream.stop_stream()
            stream.close()

            if not frames:
                print("[LaptopIdleAgent] Không ghi được gì rõ ràng, quay lại chờ vỗ tay.")
                continue

            _send_voice_and_play(_frames_to_wav_bytes(frames))
        except Exception as e:
            print(f"[LaptopIdleAgent] Lỗi voice loop: {e} — thử lại sau 3s")
            time.sleep(3)


def main():
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=command_poll_loop, daemon=True).start()
    threading.Thread(target=voice_loop, daemon=True).start()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
