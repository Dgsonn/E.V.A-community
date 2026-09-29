import os
import asyncio
import threading
import hashlib
import pygame
import edge_tts

VOICE = "vi-VN-HoaiMyNeural"  # đổi sang "vi-VN-NamMinhNeural" nếu muốn giọng nam
CACHE_DIR = "assets/tts_cache"


def _cache_path(text):
    h = hashlib.md5((VOICE + text).encode("utf-8")).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"{h}.mp3")


class TTSEngine:
    def __init__(self, config=None):
        pygame.mixer.init()
        os.makedirs(CACHE_DIR, exist_ok=True)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._speaking = False
        self._play_lock = asyncio.Lock()  # mỗi lúc chỉ phát 1 câu — câu wait_turn chờ ở đây
        self._on_start_callbacks = []
        self._on_end_callbacks = []

        # user.address_term/speech_rate (config/settings.yaml) — cùng nguồn cấu hình với
        # core/ai_brain.py, để câu preload cache đúng với câu EVA thực sự sẽ nói.
        user_cfg = (config or {}).get("user", {})
        self.address_term = user_cfg.get("address_term", "Sơn")
        self.rate = user_cfg.get("speech_rate", "+0%")
        self._phrases = {
            f"Hệ thống đã online. Tôi đã sẵn sàng phục vụ, {self.address_term}.",
            f"Đã chuyển sang chế độ offline, {self.address_term}.",
            f"Đã chuyển sang chế độ online, {self.address_term}.",
            f"Chưa cấu hình được internet, {self.address_term}. Vẫn ở chế độ offline.",
            f"Đã bật camera, {self.address_term}.",
            f"Đã tắt camera, {self.address_term}.",
            f"Xin lỗi, tôi chưa nghe rõ, {self.address_term} nói lại được không?",
            f"Không thể hoàn tất yêu cầu, {self.address_term}.",
            "Có lỗi, thử lại sau.",
        }

        # Edge-TTS gọi qua mạng, không cần nạp model nặng — sẵn sàng ngay
        self._ready = threading.Event()
        self._ready.set()
        print(f"[TTS] Edge-TTS sẵn sàng (giọng: {VOICE}, tốc độ: {self.rate}, cần internet để tạo câu mới)")
        asyncio.run_coroutine_threadsafe(self._preload(), self._loop)

    def preload(self, texts):
        """Tạo sẵn file giọng đọc cho các câu cố định (nhắc thuốc, hỏi han, SOS...) lúc còn mạng
        — Edge-TTS cần internet để tạo câu MỚI, nên nếu không tạo trước thì lúc mất mạng những
        câu an toàn này sẽ không phát ra được. Câu đã có trong cache thì bỏ qua."""
        self._phrases.update(texts)
        asyncio.run_coroutine_threadsafe(self._preload(), self._loop)

    async def _preload(self):
        for text in list(self._phrases):
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
        communicate = edge_tts.Communicate(text, VOICE, rate=self.rate)
        with open(path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])

    def speak(self, text, wait_turn=False):
        """wait_turn=False: đang nói thì bỏ qua câu mới (hành vi cũ cho câu trả lời thường).
        wait_turn=True: xếp hàng chờ nói xong rồi phát — dùng cho nhắc thuốc/cảnh báo/SOS,
        những câu KHÔNG được phép mất chỉ vì EVA đang nói dở câu khác."""
        if self._speaking and not wait_turn:
            return
        asyncio.run_coroutine_threadsafe(self._play(text), self._loop)

    async def _play(self, text):
        async with self._play_lock:
            await self._play_locked(text)

    async def _play_locked(self, text):
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
