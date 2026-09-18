"use client";

import { useState } from "react";
import { setToken } from "@/lib/api";

export function TokenGate({ error, onSubmit }: { error: string | null; onSubmit: () => void }) {
  const [value, setValue] = useState("");

  const submit = () => {
    if (!value.trim()) return;
    setToken(value);
    onSubmit();
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
        <p className="text-sm text-[var(--text-dim)]">
          Nhập DASHBOARD_TOKEN để điều khiển hệ thống — xem log lúc server khởi động hoặc file .env trên server.
        </p>
        <input
          type="password"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Dashboard token"
          className="w-full rounded border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2 text-[var(--text)] text-sm outline-none focus:border-[var(--border-strong)]"
        />
        {error && <p className="text-sm text-[var(--red)]">{error}</p>}
        <button
          onClick={submit}
          className="w-full rounded border border-[var(--border-strong)] bg-[var(--cyan-dim)] text-[var(--cyan)] text-sm font-medium py-2 hover:bg-[var(--border-strong)] transition-colors"
        >
          Xác nhận
        </button>
      </div>
    </div>
  );
}
