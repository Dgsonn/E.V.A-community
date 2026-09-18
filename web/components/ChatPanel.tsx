"use client";

import { useEffect, useRef, useState } from "react";
import type { HistoryItem } from "@/lib/api";
import { useVoiceRecorder } from "@/lib/useVoiceRecorder";
import { api } from "@/lib/api";

export function ChatPanel({
  history,
  onSend,
}: {
  history: HistoryItem[];
  onSend: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const [voiceStatus, setVoiceStatus] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const { isRecording, start, stop } = useVoiceRecorder();

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history]);

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    onSend(text);
  };

  const toggleRecording = async () => {
    if (isRecording) {
      // Bọc toàn bộ (kể cả stop()/encode WAV, trước đây không có try/catch) — lỗi ở bước encode
      // audio (vd định dạng ghi âm lạ trên 1 số trình duyệt/thiết bị) trước đây bị nuốt mất,
      // không hiện gì lên UI cả, trông như nút không phản hồi dù thực ra đã lỗi từ sớm.
      try {
        const wav = await stop();
        if (!wav) {
          setVoiceStatus("Không ghi được gì, thử lại.");
          return;
        }
        setVoiceStatus("Đang xử lý...");
        const data = await api.sendVoice(wav);
        if (data.status === "ok") {
          setVoiceStatus("");
          if (data.audio_b64 && audioRef.current) {
            const bytes = Uint8Array.from(atob(data.audio_b64), (c) => c.charCodeAt(0));
            const blob = new Blob([bytes], { type: "audio/mpeg" });
            audioRef.current.src = URL.createObjectURL(blob);
            audioRef.current.play();
          }
        } else {
          setVoiceStatus("message" in data ? data.message : "Có lỗi xảy ra.");
        }
      } catch (err) {
        console.error("[Voice] Lỗi ghi/gửi giọng nói:", err);
        setVoiceStatus(`Lỗi ghi âm: ${err instanceof Error ? err.message : String(err)}`);
      }
      return;
    }
    setVoiceStatus("");
    try {
      const err = await start();
      if (err) setVoiceStatus(err);
    } catch (err) {
      console.error("[Voice] Lỗi bắt đầu ghi âm:", err);
      setVoiceStatus(`Lỗi bắt đầu ghi âm: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <section className="panel-glass rounded-xl p-4 flex flex-col min-h-0 h-[65dvh] shrink-0 lg:h-auto lg:shrink">
      <h2 className="section-label mb-3">Hội thoại</h2>
      <div ref={logRef} className="flex-1 overflow-y-auto flex flex-col gap-2 text-sm pr-1 min-h-0">
        {history.map((m, i) => {
          const isUser = m.role === "user";
          return (
            <div
              key={i}
              className={`animate-msg-in max-w-[92%] rounded-lg px-3 py-2 leading-relaxed ${
                isUser
                  ? "self-end bg-[var(--cyan-dim)] text-[var(--text)]"
                  : "self-start bg-[var(--panel-2)] border border-[var(--border)] text-[var(--cyan)]"
              }`}
            >
              <span className="block font-[family-name:var(--font-display)] text-[0.62rem] text-[var(--text-dim)] mb-0.5">
                {isUser ? "SƠN" : "EVA"}
              </span>
              {m.text}
            </div>
          );
        })}
      </div>
      <div className="flex gap-2 mt-3">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Nhập lệnh cho EVA..."
          autoFocus
          className="flex-1 px-3 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text)] text-sm outline-none focus:border-[var(--cyan)] transition-colors"
        />
        <button
          onClick={send}
          className="px-4 py-2.5 rounded-lg border border-[var(--cyan)] bg-[var(--cyan-dim)] text-[var(--cyan)] font-[family-name:var(--font-display)] font-semibold text-sm cursor-pointer transition-colors hover:bg-[var(--cyan)] hover:text-[#001018]"
        >
          Gửi
        </button>
        <button
          onClick={toggleRecording}
          className={`px-3.5 py-2.5 rounded-lg border font-[family-name:var(--font-display)] text-[0.8rem] whitespace-nowrap cursor-pointer transition-colors ${
            isRecording
              ? "border-[var(--red)] text-[var(--red)]"
              : "border-[var(--border)] text-[var(--text)] hover:border-[var(--cyan)] hover:text-[var(--cyan)]"
          }`}
        >
          {isRecording ? "⏺ Đang ghi" : "🎤 Nói"}
        </button>
      </div>
      <div className="mt-1.5 text-xs text-[var(--text-dim)] min-h-[1em]">{voiceStatus}</div>
      <audio ref={audioRef} className="hidden" />
    </section>
  );
}
