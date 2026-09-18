#!/usr/bin/env python3
"""
EVA Diagnostic Test
Kiểm tra toàn bộ hệ thống hoạt động chính xác
"""

import sys
import yaml
import time
import threading
from pathlib import Path

print("=" * 70)
print("  EVA DIAGNOSTIC TEST")
print("=" * 70)
print()

# ============ TEST 1: Configuration ============
print("[TEST 1] Configuration Loading")
print("-" * 70)
try:
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    print("✅ Config file loaded")
    print(f"   - Model: {config['ai']['model']}")
    print(f"   - Camera: {config['camera']['width']}x{config['camera']['height']}@{config['camera']['fps']}fps")
    print(f"   - Voice mic: index {config['voice']['mic_index']}")
    print(f"   - Voice model: {config['voice']['model']}")
    print(f"   - Wake word: {config['eva']['wake_word']}")
except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
print()

# ============ TEST 2: Module Imports ============
print("[TEST 2] Importing Core Modules")
print("-" * 70)
try:
    from core.ai_brain import AIBrain, SYSTEM_PROMPT
    print("✅ AIBrain imported")

    from core.tts_engine import TTSEngine
    print("✅ TTSEngine imported")

    # VoiceEngine may take longer due to whisper, skip for now
    print("⏳ VoiceEngine (skipped - will test below)")
except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
print()

# ============ TEST 3: AIBrain Initialization ============
print("[TEST 3] AIBrain Initialization")
print("-" * 70)
try:
    ai_brain = AIBrain(config)
    print("✅ AIBrain initialized successfully")
    print(f"   - Model: {ai_brain.model}")
    print(f"   - Max history: {ai_brain.max_history}")
    print(f"   - Worker thread: {'running' if ai_brain._worker.is_alive() else 'stopped'}")
    print(f"   - Queue status: {ai_brain._request_queue.empty() and 'empty' or 'has items'}")
except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
print()

# ============ TEST 4: Ollama API Connectivity ============
print("[TEST 4] Ollama API Connectivity")
print("-" * 70)
try:
    import ollama

    # Try to get model info
    response = ollama.list()
    models = [m.model for m in response.models if 'qwen' in m.model.lower()]

    if models:
        print(f"✅ Ollama server running")
        print(f"   - Available models: {models}")
    else:
        print(f"⚠️  WARNING: qwen2.5 model not found")
        print(f"   - Available models: {[m.model for m in response.models]}")

except Exception as e:
    print(f"❌ ERROR: Ollama server not responding")
    print(f"   - Make sure 'ollama serve' is running")
    print(f"   - Error: {e}")
print()

# ============ TEST 5: TTS Engine ============
print("[TEST 5] TTS Engine Initialization")
print("-" * 70)
try:
    tts_engine = TTSEngine()
    print(f"✅ TTSEngine initialized")
    print(f"   - Voice: Edge-TTS (cần internet để tạo câu mới)")

    # Check cache
    import os
    cache_files = len([f for f in os.listdir("assets/tts_cache") if f.endswith('.mp3')])
    print(f"   - Cached phrases: {cache_files}/9")

    if cache_files >= 9:
        print(f"✅ TTS cache preloaded")
    else:
        print(f"⚠️  TTS still caching... (will be ready in a few seconds)")
except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
print()

# ============ TEST 6: Voice Engine (Whisper) ============
print("[TEST 6] Voice Engine (Whisper) Initialization")
print("-" * 70)
try:
    from core.voice_engine import VoiceEngine
    voice_engine = VoiceEngine(config)
    print(f"✅ VoiceEngine imported and initialized")
    print(f"   - STT Model: Whisper {config['voice']['model']}")
    print(f"   - Language: {config['voice']['language']}")
    print(f"   - Mic index: {config['voice']['mic_index']}")
    print(f"   - VAD aggressiveness: {config['voice'].get('vad_aggressiveness', 2)}")
    print(f"   - Wake word: {config['eva']['wake_word']}")

    # Wait for Whisper to load
    print(f"\n   ⏳ Waiting for Whisper model to load (this may take 1-2 minutes)...")
    for i in range(120):
        if voice_engine.ready:
            print(f"   ✅ Whisper loaded successfully")
            break
        time.sleep(0.5)
        if i % 10 == 0 and i > 0:
            print(f"   ... {i} seconds")

    if not voice_engine.ready:
        print(f"   ⚠️  WARNING: Whisper still loading (system may be slow or not enough disk space)")
        print(f"   (You can continue - it will load in background when you run main.py)")
except Exception as e:
    print(f"⚠️  WARNING: VoiceEngine issue: {e}")
    print(f"   (This can be fixed by installing openai-whisper separately)")
    voice_engine = None
print()

# ============ TEST 7: Message Queueing ============
print("[TEST 7] Message Queueing & Threading")
print("-" * 70)
try:
    responses = []

    def test_callback(response):
        responses.append(response)

    # Queue a test message
    ai_brain.ask("Xin chào", callback=test_callback)
    print(f"✅ Message queued successfully")

    # Wait for response
    print(f"   ⏳ Waiting for Ollama response (max 10 seconds)...")
    start_time = time.time()
    while time.time() - start_time < 10 and not responses:
        time.sleep(0.2)

    if responses:
        response_text = responses[0]
        print(f"✅ Response received from Ollama")
        print(f"   - Length: {len(response_text)} characters")
        print(f"   - Preview: {response_text[:60]}...")
    else:
        print(f"⚠️  No response (Ollama server may be slow)")

except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
print()

# ============ TEST 8: System Summary ============
print("[TEST 8] System Health Check")
print("-" * 70)

checks = {
    "Configuration": True,
    "AIBrain": ai_brain._worker.is_alive(),
    "Ollama Connection": responses != [],
    "TTSEngine": tts_engine is not None,
    "VoiceEngine": voice_engine is not None and voice_engine.ready if voice_engine else None,
}

all_ok = all(v for v in checks.values() if v is not None)

for check, status in checks.items():
    if status is None:
        symbol = "⚠️ "
        result = "LOADING"
    else:
        symbol = "✅" if status else "❌"
        result = "OK" if status else "FAILED"
    print(f"{symbol} {check:20} {result}")

print()
print("=" * 70)
if all_ok:
    print("  ✅ ALL TESTS PASSED - EVA IS READY TO RUN")
else:
    print("  ⚠️  SOME TESTS FAILED - CHECK CONFIGURATION")
print("=" * 70)
print()

# ============ NEXT STEPS ============
print("NEXT STEPS:")
print("1. Make sure Ollama is still running: 'ollama serve'")
print("2. Run main.py: 'python main.py'")
print(f"3. Nói '{config['eva']['wake_word']}' trước lệnh để kích hoạt, vd: '{config['eva']['wake_word']}, mở notepad giúp tôi'")
print()
