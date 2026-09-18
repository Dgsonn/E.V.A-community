#!/usr/bin/env python3
"""Đăng ký giọng nói cho EVA (xác minh danh tính không cần camera).
Hỗ trợ nhiều người — mỗi giọng gắn với 1 tên, đăng ký thêm không xoá người đã có."""

import sys
import time
import yaml
import pyaudio
import numpy as np

from core.voice_id_engine import VoiceIDEngine

RATE = 16000
RECORD_SECS = 6


def main():
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    mic_index = config["voice"]["mic_index"]

    print("=" * 60)
    print("  ĐĂNG KÝ GIỌNG NÓI CHO EVA")
    print("=" * 60)

    name = (sys.argv[1] if len(sys.argv) > 1 else input("Tên người đăng ký (vd Sơn, Nhi): ")).strip()
    if not name:
        print("❌ Chưa nhập tên. Thử lại.")
        sys.exit(1)

    print(f"Sẽ ghi âm {RECORD_SECS} giây — nói tự nhiên, liên tục, câu gì cũng được")
    print("(vd: đọc to vài câu, giới thiệu bản thân...)")
    input("Nhấn Enter khi sẵn sàng bắt đầu ghi âm...")

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=RATE,
        input=True, input_device_index=mic_index,
        frames_per_buffer=1024,
    )

    print("Đang ghi âm...")
    frames = []
    n_chunks = int(RATE / 1024 * RECORD_SECS)
    for i in range(n_chunks):
        data = stream.read(1024, exception_on_overflow=False)
        frames.append(data)
        remaining = RECORD_SECS - int(i * 1024 / RATE)
        print(f"\r  Còn {remaining}s...  ", end="", flush=True)
    print("\nGhi âm xong.")

    stream.stop_stream()
    stream.close()
    pa.terminate()

    audio_np = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
    max_vol = np.max(np.abs(audio_np))
    if max_vol < 0.02:
        print("❌ Âm lượng quá nhỏ, có thể mic bị tắt hoặc sai thiết bị. Thử lại.")
        sys.exit(1)
    audio_np = audio_np / max_vol

    print("Đang xử lý và lưu giọng nói...")
    engine = VoiceIDEngine()
    ok = engine.enroll(audio_np, name, sample_rate=RATE)

    if ok:
        print(f"✅ Đã đăng ký giọng nói cho '{name}' — EVA giờ có thể nhận ra {name} qua giọng nói.")
    else:
        print("❌ Không xử lý được đoạn ghi âm (có thể quá ngắn hoặc quá nhiều khoảng lặng). Thử lại.")
        sys.exit(1)


if __name__ == "__main__":
    main()
