"use client";

import { useState } from "react";
import { api, setToken } from "@/lib/api";

export function TokenGate({ error, onSubmit }: { error: string | null; onSubmit: () => void }) {
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const submit = async () => {
    if (pin.trim().length !== 4 || busy) return;
    setBusy(true);
    setLocalError(null);
    try {
      const result = await api.pair(pin.trim());
      if (result.status === "ok") {
        setToken(result.token);
        onSubmit();
      } else {
        setLocalError(result.message);
        setPin("");
      }
    } catch {
      setLocalError("Không kết nối được tới EVA — kiểm tra lại mạng.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="h-dvh flex items-center justify-center px-4"
      style={{ background: "var(--bg)", backgroundImage: "var(--bg-glow)" }}
    >
      <div className="w-full max-w-sm border border-[var(--border)] bg-[var(--panel)] backdrop-blur-md rounded-lg p-6 flex flex-col gap-4">
        <div className="font-[family-name:var(--font-display)] font-bold text-lg tracking-[0.2em] text-[var(--cyan)] [text-shadow:0_0_16px_rgba(45,212,255,0.5)]">
          EVA
        </div>
        <p className="text-base text-[var(--text-dim)]">
          Nhập mã PIN 4 số hiện trên màn hình máy chủ lúc khởi động (hoặc hỏi người đã cài EVA) để mở khoá.
        </p>
        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoFocus
          maxLength={4}
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/[^0-9]/g, "").slice(0, 4))}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="••••"
          aria-label="Mã PIN 4 số"
          className="w-full rounded border border-[var(--border)] bg-[var(--panel-2)] px-3 py-3 text-[var(--text)] text-2xl tracking-[0.5em] text-center outline-none focus:border-[var(--border-strong)]"
        />
        {(localError || error) && <p className="text-sm text-[var(--red)]">{localError ?? error}</p>}
        <button
          onClick={submit}
          disabled={busy || pin.length !== 4}
          className="w-full rounded border border-[var(--border-strong)] bg-[var(--cyan-dim)] text-[var(--cyan)] text-base font-medium py-3 hover:bg-[var(--border-strong)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {busy ? "Đang kiểm tra..." : "Mở khoá"}
        </button>
      </div>
    </div>
  );
}
