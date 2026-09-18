import os
import json
import numpy as np

PROFILES_PATH = os.path.join("assets", "voice_profiles.json")
_LEGACY_OWNER_PATH = os.path.join("assets", "owner_voice.json")  # định dạng cũ (1 chủ nhân, không tên) — tự chuyển sang định dạng mới
MATCH_THRESHOLD = 0.60  # cosine similarity — càng cao càng chặt, giảm nếu hay từ chối nhầm người đã đăng ký
# (điểm thực đo được của chủ nhân dao động quanh 0.67-0.74 giữa các lần nói khác nhau — 0.75 quá chặt)


class VoiceIDEngine:
    """Xác minh người nói qua đặc trưng giọng nói (voice embedding), không cần camera.
    Hỗ trợ nhiều người (vd chủ nhân + người thân) — mỗi giọng gắn với 1 tên, tất cả
    những ai đã đăng ký đều được coi là có toàn quyền như nhau, chỉ khác tên hiển thị."""

    def __init__(self):
        from resemblyzer import VoiceEncoder
        self._encoder = VoiceEncoder(device="cpu")
        self.profiles = self._load_profiles()  # list of {"name": str, "embedding": np.ndarray}
        self._warmup()

    def _warmup(self):
        # lần gọi đầu của resemblyzer rất chậm (biên dịch JIT) — "mồi" trước lúc khởi động
        # để lần xác minh thật đầu tiên không bị chậm bất thường.
        from resemblyzer import preprocess_wav
        # nhiễu nhẹ thay vì im lặng tuyệt đối — tránh chia-cho-0 khi resemblyzer đo độ ồn (dBFS)
        silence = (np.random.randn(16000) * 0.01).astype(np.float32)
        wav = preprocess_wav(silence, source_sr=16000)
        self._encoder.embed_utterance(wav)

    def _load_profiles(self):
        if os.path.exists(PROFILES_PATH):
            with open(PROFILES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [{"name": p["name"], "embedding": np.array(p["embedding"])} for p in data.get("profiles", [])]

        # tương thích ngược với file cũ trước khi hỗ trợ nhiều người
        if os.path.exists(_LEGACY_OWNER_PATH):
            with open(_LEGACY_OWNER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = [{"name": "Sơn", "embedding": np.array(data["embedding"])}]
            self._save_profiles(profiles)
            return profiles

        return []

    def _save_profiles(self, profiles):
        os.makedirs(os.path.dirname(PROFILES_PATH), exist_ok=True)
        with open(PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {"profiles": [{"name": p["name"], "embedding": p["embedding"].tolist()} for p in profiles]},
                f, ensure_ascii=False,
            )

    @property
    def has_profiles(self):
        return len(self.profiles) > 0

    def _embed(self, audio_np, sample_rate=16000):
        from resemblyzer import preprocess_wav
        try:
            wav = preprocess_wav(audio_np, source_sr=sample_rate)
            if len(wav) < sample_rate * 0.5:  # quá ngắn (dưới 0.5s sau khi lọc im lặng) — không đủ tin cậy
                return None
            return self._encoder.embed_utterance(wav)
        except Exception:
            return None

    def enroll(self, audio_np, name, sample_rate=16000):
        """Đăng ký (hoặc ghi đè lại) giọng của 1 người theo tên. Trả về True nếu thành công."""
        embedding = self._embed(audio_np, sample_rate)
        if embedding is None:
            return False

        name = name.strip()
        self.profiles = [p for p in self.profiles if p["name"].lower() != name.lower()]
        self.profiles.append({"name": name, "embedding": embedding})
        self._save_profiles(self.profiles)
        return True

    def revoke(self, name):
        """Xoá quyền của 1 người đã đăng ký theo tên. Trả về True nếu tìm thấy và xoá."""
        before = len(self.profiles)
        self.profiles = [p for p in self.profiles if p["name"].lower() != name.strip().lower()]
        if len(self.profiles) == before:
            return False
        self._save_profiles(self.profiles)
        return True

    def identify(self, audio_np, sample_rate=16000):
        """So khớp đoạn audio với tất cả giọng đã đăng ký.
        Trả về (tên, True) nếu khớp người nào đó vượt ngưỡng,
        (None, False) nếu không khớp ai trong số đã đăng ký,
        (None, None) nếu chưa có ai đăng ký hoặc audio quá ngắn để xác minh."""
        if not self.has_profiles:
            return None, None

        embedding = self._embed(audio_np, sample_rate)
        if embedding is None:
            return None, None

        best_name, best_score = None, -1.0
        for profile in self.profiles:
            score = float(np.dot(embedding, profile["embedding"]))
            if score > best_score:
                best_name, best_score = profile["name"], score

        print(f"[VoiceID] Khớp nhất: {best_name} ({best_score:.3f}, ngưỡng cần: {MATCH_THRESHOLD})")
        if best_score >= MATCH_THRESHOLD:
            return best_name, True
        return None, False
