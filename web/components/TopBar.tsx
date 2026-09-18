"use client";

import { useEffect, useState } from "react";

export function TopBar({
  cpu,
  ram,
  sessionActive,
  onShutdown,
}: {
  cpu: number;
  ram: number;
  sessionActive: boolean;
  onShutdown: () => void;
}) {
  const [clock, setClock] = useState("--:--:--");

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString("vi-VN", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="flex flex-wrap items-center gap-3 sm:gap-6 px-4 sm:px-5 py-3 border-b border-[var(--border)] bg-[var(--panel)] backdrop-blur-md shrink-0">
      <div className="font-[family-name:var(--font-display)] font-bold text-lg tracking-[0.2em] text-[var(--cyan)] [text-shadow:0_0_16px_rgba(45,212,255,0.5)]">
        EVA
      </div>
      <div className="font-[family-name:var(--font-display)] text-sm text-[var(--text)] tabular-nums min-w-[92px]">
        {clock}
      </div>
      <div className="flex-1" />
      <div className="hidden sm:flex items-center gap-4 font-[family-name:var(--font-display)] text-[0.8rem] text-[var(--text-dim)]">
        <span>
          CPU <b className="text-[var(--cyan)]">{Math.round(cpu)}%</b>
        </span>
        <span>
          RAM <b className="text-[var(--cyan)]">{Math.round(ram)}%</b>
        </span>
      </div>
      <div
        className={`w-2.5 h-2.5 rounded-full transition-all ${
          sessionActive ? "bg-[var(--green)] shadow-[0_0_10px_var(--green)]" : "bg-[var(--cyan-dim)]"
        }`}
        title="Trạng thái phiên"
      />
      <button
        onClick={onShutdown}
        title="Tắt hệ thống"
        className="w-8 h-8 rounded-full border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-dim)] flex items-center justify-center transition-colors hover:border-[var(--red)] hover:text-[var(--red)] cursor-pointer"
      >
        ⏻
      </button>
    </header>
  );
}
