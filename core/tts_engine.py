import os
import asyncio
import threading
import hashlib
import pygame
import edge_tts

VOICE = "vi-VN-HoaiMyNeural"  # đổi sang "vi-VN-NamMinhNeural" nếu muốn giọng nam
CACHE_DIR = "assets/tts_cache"

PHRASES = {
    "Hệ thống đã online. Tôi đã sẵn sàng phục vụ, Sơn.",
    "Đã chuyển sang chế độ offline, Sơn.",
    "Đã chuyển sang chế độ online, Sơn.",
    "Chưa cấu hình được internet, Sơn. Vẫn ở chế độ offline.",
    "Đã bật camera, Sơn.",
    "Đã tắt camera, Sơn.",
    "Xin lỗi, tôi chưa nghe rõ, Sơn nói lại được không?",
    "Không thể hoàn tất yêu cầu, Sơn.",
    "Có lỗi, thử lại sau.",
}


def _cache_path(text):
    h = hashlib.md5((VOICE + text).encode("utf-8")).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"{h}.mp3")


class TTSEngine:
    def __init__(self):
        pygame.mixer.init()
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._speaking = False
        self._on_start_callbacks = []
        self._on_end_callbacks = []

        # Edge-TTS gọi qua mạng, không cần nạp model nặng — sẵn sàng ngay
        self._ready = threading.Event()
        self._ready.set()
        print(f"[TTS] Edge-TTS sẵn sàng (giọng: {VOICE}, cần internet để tạo câu mới)")
        asyncio.run_coroutine_threadsafe(self._preload(), self._loop)

    async def _preload(self):
        for text in PHRASES:
            path = _cache_path(text)
            if not os.path.exists(path):
                try:
                    await self._synthesize(text, path)
                except Exception as e:
                    print(f"[TTS] Lỗi tạo trước '{text[:20]}...': {e}")
        print("[TTS] Cache sẵn sàng! Phản hồi tức thì.")

    async def _synthesize(self, text, path):
        # tự đọc stream() thay vì dùng communicate.save() — save() chậm hơn hẳn (~3s so
        # với ~0.7s) trong thực tế đo được, có lẽ do xử lý thêm word-boundary bên trong.
        communicate = edge_tts.Communicate(text, VOICE)
        with open(path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])

    def get_audio_path(self, text):
        """Đảm bảo mp3 cho text đã tồn tại trong cache rồi trả về đường dẫn — KHÔNG phát qua
        pygame (khác speak()). Dùng cho phản hồi giọng nói qua trình duyệt (source="web_voice"),
        nơi Sơn cần nghe qua chính trình duyệt chứ không phải loa server."""
        path = _cache_path(text)
        if not os.path.exists(path):
            asyncio.run_coroutine_threadsafe(self._synthesize(text, path), self._loop).result()
        return path

    def speak(self, text):
        if self._speaking:
            return
        asyncio.run_coroutine_threadsafe(self._play(text), self._loop)

    async def _play(self, text):
        self._speaking = True
        for cb in self._on_start_callbacks:
            try:
                cb()
            except Exception:
                pass

        path = _cache_path(text)
        try:
            if not os.path.exists(path):
                await self._synthesize(text, path)
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[TTS] Lỗi phát âm thanh (có thể do mất mạng): {e}")
        finally:
            self._speaking = False
            for cb in self._on_end_callbacks:
                try:
                    cb()
                except Exception:
                    pass

    def stop(self):
        """Dừng ngay audio đang phát (dùng cho tính năng ngắt lời) — _play() đang chờ
        get_busy() sẽ tự thoát vòng lặp và chạy finally (reset self._speaking, gọi on_end)
        như khi phát xong bình thường."""
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def register_on_start(self, cb):
        if callable(cb):
            self._on_start_callbacks.append(cb)

    def register_on_end(self, cb):
        if callable(cb):
            self._on_end_callbacks.append(cb)
