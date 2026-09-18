import pyaudio
import webrtcvad
import threading
import numpy as np
import time
import unicodedata
from collections import deque, Counter
from difflib import SequenceMatcher


class _ClapDetector:
    """Phát hiện mẫu vỗ tay/búng tay: 2 tiếng bộp ngắn (tấn nhanh, tắt nhanh) trong
    khoảng clap_window_secs — khác tiếng nói (năng lượng kéo dài) và khác tiếng ồn
    ngẫu nhiên (1 tiếng bộp đơn lẻ không đủ, tránh trúng tiếng đóng cửa/rơi đồ)."""

    ABS_MIN_PEAK = 1200.0
    BASELINE_EMA_ALPHA = 0.05
    MAX_SPIKE_RUN_FRAMES = 3  # ~90ms ở FRAME_MS=30 — lâu hơn thì coi là ồn kéo dài, không phải vỗ tay
    MIN_CLAP_GAP = 0.15  # tránh đếm dư âm của cùng 1 tiếng vỗ thành 2 lần

    def __init__(self, threshold_multiplier, window_secs):
        self._threshold_multiplier = threshold_multiplier
        self._window_secs = window_secs
        self._baseline = 300.0
        self._spike_run = 0
        self._clap_times = deque(maxlen=2)

    def feed(self, data):
        """Đưa vào 1 khung PCM int16, trả về True nếu vừa đủ 2 tiếng vỗ trong khung thời gian."""
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


class VoiceEngine:
    def __init__(self, config):
        self.config            = config
        self._mic_index        = config["voice"]["mic_index"]
        self._lang             = config["voice"]["language"]
        self._model_name       = config["voice"]["model"] # Lấy từ settings
        self._vad               = webrtcvad.Vad(int(config["voice"].get("vad_aggressiveness", 2)))
        self._mic_gain          = float(config["voice"].get("mic_gain", 1.0))
        self.security_enabled  = bool(config["voice"].get("security_enabled", False))
        self._clap_wake_enabled          = bool(config["voice"].get("clap_wake_enabled", True))
        self._clap_threshold_multiplier  = float(config["voice"].get("clap_threshold_multiplier", 5.0))
        self._clap_window_secs           = float(config["voice"].get("clap_window_secs", 1.5))
        self._wake_words        = self._build_word_list(config, "wake_word", "dậy đi", "wake_word_aliases")
        self._sleep_words       = self._build_word_list(config, "sleep_word", "tạm biệt", "sleep_word_aliases")
        self._interrupt_words   = self._build_word_list(config, "interrupt_word", "dừng lại", "interrupt_word_aliases")

        self._model            = None
        self._wake_model       = None
        self._voice_id         = None  # nạp nền, có thể chưa sẵn sàng ở câu nói đầu tiên
        self.last_speaker_owner = None  # kết quả xác minh giọng nói của câu gần nhất: True/False/None
        self.last_speaker_name  = None  # tên người vừa nói nếu khớp hồ sơ đã đăng ký (vd "Sơn"/"Nhi"), None nếu không khớp ai
        self._active           = False
        self._paused           = False
        self._session_active   = False  # đã "dậy" chưa — trong phiên thì không cần lặp lại từ đánh thức
        self._last_transcript  = None
        self._last_transcript_time = 0
        self._last_error       = False
        self._pa               = pyaudio.PyAudio()
        self._lock             = threading.Lock()
        # self._lock giữ state cờ (active/paused...), hold time ngắn — không dùng để bọc
        # inference (vài giây) vì sẽ chặn activate()/deactivate()/pause_listening() quá lâu.
        # Lock riêng này chỉ để tránh 2 luồng (mic + request web) gọi self._model cùng lúc.
        self._model_lock        = threading.Lock()
        self.on_listening      = None
        self.on_wake           = None  # gọi khi vừa đánh thức, trước cả khi có lệnh — dùng để phát câu chào mở đầu
        self.on_interrupt      = None  # gọi khi nghe từ ngắt lời trong lúc TTS đang phát — dùng để dừng TTS ngay
        # device will be determined when loading model (lazy import)
        self.device = "cpu"
        
        # In danh sách mic để dễ debug
        self._print_mic_list()

        # Nạp model
        threading.Thread(target=self._load_model, daemon=True).start()

    def _build_word_list(self, config, key, default, aliases_key):
        eva_cfg = config.get("eva", {})
        primary = str(eva_cfg.get(key, default)).strip().lower()
        aliases = [str(a).strip().lower() for a in eva_cfg.get(aliases_key, [])]
        words = [primary] + [a for a in aliases if a and a != primary]
        return words

    def _print_mic_list(self):
        print("[STT] Danh sách microphone khả dụng:")
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                marker = " <-- ĐANG DÙNG" if i == self._mic_index else ""
                print(f"  [{i}] {info['name']}{marker}")

    def _load_model(self):
        """Cơ chế nạp model thông minh: Tìm Offline trước, Online sau"""
        try:
            # lazy import transformers/torch để tránh crash lúc import module nếu chưa cài
            try:
                from transformers import pipeline
                import torch
            except Exception as ie:
                print(f"[STT] transformers/Torch import failed: {ie}")
                print("[STT] Voice input disabled. Install 'transformers' and 'torch' in the venv.")
                return

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            device_idx = 0 if self.device == "cuda" else -1
            # fp16 trên GPU giảm ~1 nửa VRAM so với fp32 mặc định, chất lượng nhận dạng
            # không đổi đáng kể — quan trọng vì Ollama (qwen2.5 7B) đã chiếm ~4GB/6GB VRAM
            # của RTX 3050, gần như không còn dư nếu STT vẫn nạp fp32.
            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32

            # Model nhẹ dùng lúc chờ (chưa "dậy đi") — luôn chạy CPU dù có GPU hay không.
            # Đây là model chỉ cần nhận ra từ đánh thức trong lúc rảnh (phần lớn thời gian
            # hệ thống ở trạng thái này), không cần tốc độ GPU — để GPU rảnh hẳn cho Ollama
            # thay vì giữ VRAM suốt cả lúc không làm việc gì.
            wake_model_id = "vinai/PhoWhisper-small"
            print(f"[STT] Đang nạp {wake_model_id} (model nhẹ, luôn chạy CPU để dành VRAM cho Ollama)...")
            self._wake_model = pipeline("automatic-speech-recognition", model=wake_model_id, device=-1)

            # Model đầy đủ chỉ dùng sau khi đã "dậy đi" — lúc thực sự xử lý lệnh, nên vẫn
            # đáng để chạy GPU (fp16) cho nhanh.
            model_id = f"vinai/PhoWhisper-{self._model_name}"
            print(f"[STT] Đang nạp {model_id} (model đầy đủ, dùng lúc làm việc, {torch_dtype})...")
            self._model = pipeline(
                "automatic-speech-recognition", model=model_id, device=device_idx, dtype=torch_dtype
            )

            print(f"[STT] EVA Voice Engine đã sẵn sàng! (Device: {self.device}, chờ: {wake_model_id} [CPU], làm việc: {model_id})")
        except Exception as e:
            print(f"[STT Error] Không thể nạp PhoWhisper: {e}")

        # Voice ID (xác minh chủ nhân qua giọng nói) — nạp riêng, lỗi ở đây không nên làm hỏng STT
        try:
            from core.voice_id_engine import VoiceIDEngine
            print("[STT] Đang nạp Voice ID (xác minh giọng nói)...")
            self._voice_id = VoiceIDEngine()
            if self._voice_id.has_profiles:
                names = ", ".join(p["name"] for p in self._voice_id.profiles)
                status = f"đã đăng ký: {names}"
            else:
                status = "CHƯA đăng ký — chạy enroll_voice.py để bật xác minh"
            print(f"[STT] Voice ID sẵn sàng ({status})")
        except Exception as e:
            print(f"[STT] Không nạp được Voice ID: {e}")
            self._voice_id = None

    @property
    def ready(self):
        return self._model is not None and self._wake_model is not None

    @property
    def session_active(self):
        return self._session_active

    def activate(self, callback):
        print(f"[DEBUG] Yêu cầu kích hoạt. Ready={self.ready}, Active={self._active}")
        with self._lock:
            if not self.ready:
                print("[STT] Cảnh báo: Whisper chưa nạp xong, hãy đợi giây lát...")
                return
            if self._active: return
            self._active = True
        
        if self.on_listening and not self._paused: self.on_listening(True)
        print("[STT] Chế độ lắng nghe: ON")
        threading.Thread(target=self._continuous_loop, args=(callback,), daemon=True).start()

    def deactivate(self):
        with self._lock: self._active = False
        if self.on_listening: self.on_listening(False)
        print("[STT] Chế độ lắng nghe: OFF")

    def pause_listening(self):
        with self._lock:
            self._paused = True
        if self.on_listening:
            self.on_listening(False)
        print("[STT] Tạm dừng lắng nghe (pause)")

    def resume_listening(self):
        with self._lock:
            self._paused = False
        if self.on_listening and self._active:
            self.on_listening(True)
        print("[STT] Tiếp tục lắng nghe (resume)")

    def _continuous_loop(self, callback):
        time.sleep(0.5)
        while True:
            with self._lock:
                if not self._active: break
                if self._paused:
                    time.sleep(0.1)
                    continue
            text = self._record_once()
            if text:
                callback(text)
                time.sleep(0.2)
            elif self._last_error:
                # Mic lỗi (vd sai mic_index, thiết bị đang bận) — chờ trước khi thử lại
                # để tránh spam log / CPU khi lỗi lặp lại liên tục.
                time.sleep(1.0)

    def _apply_gain(self, data):
        """Khuếch đại tín hiệu mic trước khi đưa vào VAD/Whisper — giọng nhỏ dễ bị
        webrtcvad coi là im lặng nếu biên độ gốc quá thấp."""
        if self._mic_gain == 1.0:
            return data
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) * self._mic_gain
        samples = np.clip(samples, -32768, 32767).astype(np.int16)
        return samples.tobytes()

    def _record_once(self):
        """
        Quy trình 2 giai đoạn dùng webrtcvad (chuẩn phát hiện giọng nói của Google,
        thay cho ngưỡng năng lượng thô trước đây):
          1. Chờ giọng nói: loop đến khi webrtcvad phát hiện frame có tiếng nói
          2. Thu âm đến khi webrtcvad báo im lặng liên tục đủ lâu
        """
        RATE           = 16000
        FRAME_MS       = 30  # webrtcvad chỉ chấp nhận 10/20/30ms
        FRAME_SAMPLES  = int(RATE * FRAME_MS / 1000)
        silence_secs   = float(self.config["voice"].get("silence_secs", 1.2))
        silence_limit  = int(silence_secs * 1000 / FRAME_MS)
        min_record_secs = float(self.config["voice"].get("min_record_secs", 0.5))
        min_frames     = int(min_record_secs * 1000 / FRAME_MS)
        max_record_sec = 10  # tối đa 10 giây một lần
        voice_confirm_frames = int(self.config["voice"].get("voice_confirm_frames", 3))

        self._last_error = False
        stream = None
        try:
            stream = self._pa.open(
                format=pyaudio.paInt16, channels=1, rate=RATE,
                input=True, input_device_index=self._mic_index,
                frames_per_buffer=FRAME_SAMPLES
            )

            # --- Giai đoạn 1: Chờ giọng nói (tối đa 30s, thoát nếu deactivate) ---
            # Cần voice_confirm_frames khung liên tiếp đều là tiếng nói mới xác nhận —
            # 1 khung đơn lẻ (30ms) quá dễ trúng tiếng ồn nền/quạt máy/tiếng lách cách,
            # khiến VAD ghi nhầm rồi Whisper "ảo giác" ra câu từ nhiễu đó.
            # preroll giữ luôn vài khung trước điểm xác nhận (kể cả khung VAD chưa chắc là giọng nói) —
            # tránh cắt mất phụ âm đầu của từ đầu tiên (vd "d" trong "dậy") lúc âm lượng còn nhỏ.
            PREROLL_FRAMES = voice_confirm_frames + 2
            preroll = deque(maxlen=PREROLL_FRAMES)
            voice_detected = False
            pending = deque(maxlen=voice_confirm_frames)
            # Vỗ tay/búng tay là cách đánh thức thay thế cho wakeword — chỉ có ý nghĩa lúc
            # đang chờ (chưa dậy), không xác minh được danh tính nên tắt hẳn khi bật bảo mật
            # giọng nói (giống lý do wakeword cũng bị chặn nếu giọng lạ khi security_enabled).
            clap_detector = None
            if self._clap_wake_enabled and not self._session_active and not self.security_enabled:
                clap_detector = _ClapDetector(self._clap_threshold_multiplier, self._clap_window_secs)
            # Không còn thoát sớm khi self._paused (TTS đang phát) — vẫn tiếp tục lắng nghe
            # trong lúc EVA nói, để bắt được lệnh ngắt lời (xem _handle_transcript). Chỉ thoát
            # hẳn khi self._active tắt (deactivate thật sự).
            for _ in range(int(30000 / FRAME_MS)):
                with self._lock:
                    if not self._active:
                        stream.stop_stream(); stream.close()
                        return None
                data = self._apply_gain(stream.read(FRAME_SAMPLES, exception_on_overflow=False))
                preroll.append(data)
                # Không xét vỗ tay lúc TTS đang phát (self._paused) — tránh trúng tiếng
                # bộp/phụ âm bật hơi trong chính giọng nói của EVA.
                if clap_detector is not None and not self._paused and clap_detector.feed(data):
                    stream.stop_stream(); stream.close()
                    return self._trigger_clap_wake()
                if self._vad.is_speech(data, RATE):
                    pending.append(data)
                    if len(pending) >= voice_confirm_frames:
                        voice_detected = True
                        lead_in = list(preroll)[:-len(pending)] if len(preroll) > len(pending) else []
                        frames = lead_in + list(pending)
                        break
                else:
                    pending.clear()

            if not voice_detected:
                stream.stop_stream(); stream.close()
                return None

            # Trạng thái TTS lúc BẮT ĐẦU ghi — dùng để phát hiện nếu nó đổi giữa chừng (TTS
            # bắt đầu hoặc kết thúc ngay lúc đang thu dở), lúc đó huỷ bản ghi vì dễ lẫn tiếng
            # EVA vào đầu/cuối câu. Nếu TTS đã đang phát từ trước khi bắt đầu ghi (trường hợp
            # ngắt lời) thì giữ nguyên self._paused suốt và không bị huỷ.
            paused_at_start = self._paused

            # --- Giai đoạn 2: Thu âm cho đến khi im lặng ---
            silent_frames = 0
            for _ in range(int(max_record_sec * 1000 / FRAME_MS)):
                with self._lock:
                    if not self._active or self._paused != paused_at_start:
                        stream.stop_stream(); stream.close()
                        return None
                data = self._apply_gain(stream.read(FRAME_SAMPLES, exception_on_overflow=False))
                frames.append(data)
                if self._vad.is_speech(data, RATE):
                    silent_frames = 0
                else:
                    silent_frames += 1
                    if silent_frames >= silence_limit:
                        break

            stream.stop_stream()
            stream.close()

            if len(frames) < min_frames:
                return None

            # --- Chuyển sang float32 cho Whisper ---
            audio_np = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
            max_vol  = np.max(np.abs(audio_np))
            print(f"[STT debug] đã ghi {len(frames)} khung ({len(frames) * FRAME_MS}ms), biên độ lớn nhất: {max_vol:.3f}")

            # Chỉ normalize nếu tín hiệu đủ mạnh — tránh khuếch đại tiếng ồn
            if max_vol < 0.05:
                print("[STT debug] Bỏ qua vì biên độ quá thấp (< 0.05) — có thể chỉ là nhiễu nền")
                return None
            audio_np = audio_np / max_vol

            # --- Xác minh giọng nói (voice ID) trên chính đoạn audio vừa ghi — không tốn thêm chi phí ---
            if self._voice_id and self._voice_id.has_profiles:
                self.last_speaker_name, self.last_speaker_owner = self._voice_id.identify(audio_np, RATE)
            else:
                self.last_speaker_owner = None
                self.last_speaker_name = None

            # --- Transcribe --- (model nhẹ lúc chờ, model đầy đủ khi đã "dậy đi")
            active_model = self._model if self._session_active else self._wake_model
            with self._model_lock:
                result = active_model({"array": audio_np, "sampling_rate": RATE})
            text       = result.get("text", "").strip()
            text_clean = text.lower().replace(".", "").replace(",", "").strip()

            # --- Blacklist chống ảo giác ---
            # không đưa từ tạm biệt/wake/sleep word vào đây — chúng là lệnh thật, không phải ảo giác cần lọc
            blacklist = [
                "bây giờ", "cảm ơn", "thank you", "chào các bạn",
                "hãy subscribe", "subscribe", "đăng ký kênh", "cảm ơn các bạn đã xem",
                "xin chào", "xin chào các bạn",
            ]
            if any(item in text_clean for item in blacklist):
                print(f"[STT debug] Bỏ qua vì trùng blacklist: '{text_clean}'")
                return None

            # --- Anti-repeat ---
            now = time.time()
            if self._last_transcript and (now - self._last_transcript_time) < 3.0:
                if text_clean == self._last_transcript:
                    return None

            # --- Anti-repetition trong 1 câu (vd "quá mệt quá mệt quá mệt...") ---
            # kiểm tra từ xuất hiện nhiều nhất trong câu, không chỉ riêng từ đầu tiên —
            # PhoWhisper đôi khi lặp vô hạn một cụm từ giữa câu khi tín hiệu không rõ.
            words = text_clean.split()
            if len(words) > 40:
                print(f"[STT debug] Bỏ qua vì câu quá dài bất thường ({len(words)} từ) — có thể bị lặp vô hạn")
                return None
            if words and len(words) > 2:
                most_common_count = Counter(words).most_common(1)[0][1]
                if (most_common_count / len(words)) > 0.4:
                    print(f"[STT debug] Bỏ qua vì có từ lặp lại quá nhiều trong câu")
                    return None

            if len(text_clean) <= 2:
                return None

            print(f"[STT] {text_clean}")
            self._last_transcript      = text_clean
            self._last_transcript_time = now

            return self._handle_transcript(text_clean)

        except Exception as e:
            print(f"[STT Error] {e}")
            self._last_error = True
            # Đóng stream nếu đã mở được — thiếu bước này thì mỗi lần lỗi (mic rút dây, thiết
            # bị đang bận...) sẽ rò rỉ 1 handle âm thanh, lặp lại liên tục do _continuous_loop
            # tự thử lại mỗi giây khi self._last_error bật.
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            return None

    def transcribe_uploaded_audio(self, wav_bytes):
        """Nhận file WAV (16-bit PCM, mono, 16kHz — đúng định dạng frontend dashboard tự đóng
        gói trước khi upload, xem core/web_interface.py route /api/voice) rồi chuyển thành chữ.
        Dùng cho giọng nói ghi từ trình duyệt (source="web_voice") — khác _record_once ở chỗ
        không qua VAD/wakeword, coi như đã là lệnh thật (giống cách source="text" bỏ qua
        wakeword), luôn dùng model đầy đủ (self._model) chứ không dùng model nhẹ lúc chờ.
        Trả về: None nếu STT chưa nạp xong, "" nếu chỉ là im lặng/nhiễu, hoặc câu đã nhận dạng."""
        if self._model is None:
            return None

        import wave
        import io

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            raw = wf.readframes(wf.getnframes())

        audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        max_vol = np.max(np.abs(audio_np)) if audio_np.size else 0.0
        if max_vol < 0.05:
            return ""
        audio_np = audio_np / max_vol

        with self._model_lock:
            # return_timestamps=True bắt buộc phải có khi audio dài hơn 30s (Whisper tự chuyển
            # sang chế độ "long-form generation" và raise ValueError nếu thiếu cờ này) — giọng
            # ghi từ trình duyệt (khác mic vật lý ở _record_once) không có giới hạn 10s nên có
            # thể dài hơn 30s tuỳ Sơn ghi bao lâu. Không ảnh hưởng audio ngắn, chỉ thêm timestamp
            # từng đoạn vào kết quả (không dùng tới, "text" vẫn là câu đầy đủ như cũ).
            result = self._model({"array": audio_np, "sampling_rate": 16000}, return_timestamps=True)
        return result.get("text", "").strip()

    def _trigger_clap_wake(self):
        """Đánh thức bằng vỗ tay/búng tay — tương đương nhánh đánh thức thành công bằng
        wakeword trong _handle_transcript, nhưng không có thông tin người nói (không
        qua voice ID) nên last_speaker_name/owner để None."""
        self._session_active = True
        self.last_speaker_name = None
        self.last_speaker_owner = None
        print("[STT] Đã đánh thức bằng vỗ tay/búng tay — đang lắng nghe lệnh, duy trì đến khi nghe từ tạm biệt.")
        if self.on_wake:
            try:
                self.on_wake(None)
            except Exception:
                pass
        return None

    def _strip_diacritics(self, s):
        nfd = unicodedata.normalize("NFD", s)
        return "".join(c for c in nfd if not unicodedata.combining(c))

    def _handle_transcript(self, text_clean):
        """Máy trạng thái 2 chế độ:
        - Chờ (mặc định): chỉ phản ứng với từ đánh thức (vd 'dậy đi'), phần còn lại của câu
          (nếu có) được dùng luôn làm lệnh đầu tiên.
        - Đang hoạt động (sau khi đánh thức): mọi câu nói tiếp theo được coi là lệnh trực tiếp,
          không cần lặp lại từ đánh thức, duy trì vô thời hạn — chỉ quay về chế độ chờ khi nghe
          từ tạm biệt (vd 'tạm biệt')."""
        # Ngắt lời: chỉ xét khi EVA đang thực sự nói (self._paused do TTS bật lên, xem
        # main.py: tts.register_on_start(voice.pause_listening)). Không tính là lệnh mới,
        # không đổi trạng thái phiên — chỉ dừng TTS rồi để vòng lắng nghe tiếp tục bình thường.
        if self._paused and self._matches(text_clean, self._interrupt_words):
            print("[STT] Đã nghe lệnh ngắt lời — dừng TTS.")
            if self.on_interrupt:
                try:
                    self.on_interrupt()
                except Exception:
                    pass
            return None

        if self._session_active:
            if self._matches(text_clean, self._sleep_words):
                self._session_active = False
                print("[STT] Đã nghe từ tạm biệt — quay lại chế độ chờ.")
                return None
            return text_clean

        command = self._extract_command(text_clean, self._wake_words)
        if command is None:
            print(f"[STT] Bỏ qua (không nghe thấy từ đánh thức '{self._wake_words[0]}')")
            return None

        # bảo mật ngay từ bước đánh thức (chỉ áp dụng khi security_enabled=True trong settings.yaml) —
        # nếu đã có người đăng ký giọng thì giọng lạ nói đúng từ đánh thức cũng không được kích hoạt
        # phiên, coi như không nghe thấy gì. Khi tắt, vẫn nhận diện tên người nói (last_speaker_name)
        # để hiển thị/xưng hô, chỉ là không chặn ai cả.
        if self.security_enabled and self._voice_id and self._voice_id.has_profiles and self.last_speaker_owner is not True:
            print("[STT] Giọng nói không khớp ai đã đăng ký — bỏ qua yêu cầu đánh thức.")
            return None

        self._session_active = True
        print(f"[STT] Đã đánh thức bởi '{self.last_speaker_name or '?'}'— đang lắng nghe lệnh, duy trì đến khi nghe từ tạm biệt.")
        if self.on_wake:
            try:
                self.on_wake(self.last_speaker_name)
            except Exception:
                pass
        return command if command else None

    def _matches(self, text_clean, word_list):
        for word in word_list:
            if word in text_clean:
                return True
        return self._fuzzy_match(text_clean, word_list[0]) is not None

    def _extract_command(self, text_clean, word_list):
        """Chỉ xử lý câu có chứa 1 trong word_list, cắt bỏ phần đó khỏi câu lệnh.
        Trả về "" nếu khớp nhưng không còn gì phía sau, None nếu không khớp."""
        for word in word_list:
            idx = text_clean.find(word)
            if idx == -1:
                continue
            return text_clean[idx + len(word):].strip(" ,.")
        return self._fuzzy_match(text_clean, word_list[0])

    def _fuzzy_match(self, text_clean, target_word):
        """Whisper có thể phiên âm sai từ khoá dù là từ tiếng Việt thật — so khớp mờ
        1-3 từ đầu (bỏ dấu) thay vì đòi khớp chính xác tuyệt đối."""
        words = text_clean.split()
        target = self._strip_diacritics(target_word)
        for n in (1, 2, 3):
            if len(words) < n:
                break
            candidate = self._strip_diacritics("".join(words[:n]))
            if SequenceMatcher(None, candidate, target).ratio() >= 0.6:
                return " ".join(words[n:]).strip(" ,.")
        return None