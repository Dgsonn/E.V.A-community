"use client";

import { useEffect, useState } from "react";
import { api, UnauthorizedError, type FamilyStatusResponse } from "@/lib/api";

// SQLite lưu timestamp dạng "YYYY-MM-DD HH:MM:SS[.ffffff]" (xem core/database.py) — đổi khoảng
// trắng thành "T" để Date hiểu được như ISO, không cần parser riêng.
function formatAgo(raw: string | null): string {
  if (!raw) return "chưa có dữ liệu";
  const then = new Date(raw.replace(" ", "T")).getTime();
  if (Number.isNaN(then)) return raw;
  const diffMin = Math.floor((Date.now() - then) / 60000);
  if (diffMin < 1) return "vừa xong";
  if (diffMin < 60) return `${diffMin} phút trước`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} giờ trước`;
  return `${Math.floor(diffHour / 24)} ngày trước`;
}

function formatUptime(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return `${h} giờ ${m} phút`;
}

export default function FamilyPage() {
  // Đọc token từ query string bằng window.location thay vì hook useSearchParams của Next —
  // tránh phải bọc Suspense chỉ để build static export, trang này đơn giản không cần.
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [status, setStatus] = useState<FamilyStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token"));
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await api.getFamilyStatus(token);
        if (!cancelled) {
          setStatus(s);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof UnauthorizedError ? err.message : "Không kết nối được tới EVA.");
        }
      }
      if (!cancelled) setTimeout(poll, 30000);
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // undefined = chưa kịp đọc query string (chỉ trong 1 nhịp render đầu, tránh nháy nội dung sai)
  if (token === undefined) return null;

  if (!token) {
    return (
      <div className="h-dvh flex items-center justify-center px-4 text-center" style={{ background: "var(--bg)" }}>
        <p className="text-lg text-[var(--text-dim)]">
          Link không hợp lệ — xin lại link đầy đủ từ người đã cài EVA.
        </p>
      </div>
    );
  }

  return (
    <div
      className="h-dvh flex flex-col items-center px-4 py-8 gap-5 overflow-y-auto"
      style={{ background: "var(--bg)", backgroundImage: "var(--bg-glow)" }}
    >
      <div className="font-[family-name:var(--font-display)] font-bold text-xl tracking-[0.2em] text-[var(--cyan)] [text-shadow:0_0_16px_rgba(45,212,255,0.5)]">
        EVA — Tình trạng
      </div>

      {error && <p className="text-base text-[var(--red)] text-center">{error}</p>}

      {status && (
        <div className="w-full max-w-md flex flex-col gap-4">
          <div className="border border-[var(--border)] bg-[var(--panel)] backdrop-blur-md rounded-lg p-5 flex items-center gap-4">
            <div
              className={`w-4 h-4 rounded-full shrink-0 ${
                status.session_active
                  ? "bg-[var(--green)] shadow-[0_0_10px_var(--green)]"
                  : "bg-[var(--cyan-dim)]"
              }`}
            />
            <div>
              <p className="text-lg text-[var(--text)] font-medium">
                {status.session_active ? "Đang hoạt động" : "Đang chờ"}
              </p>
              <p className="text-base text-[var(--text-dim)]">Đã chạy liên tục {formatUptime(status.uptime_secs)}</p>
            </div>
          </div>

          <div className="border border-[var(--border)] bg-[var(--panel)] backdrop-blur-md rounded-lg p-5">
            <p className="text-sm text-[var(--text-dim)] mb-1">Hoạt động gần nhất</p>
            <p className="text-lg text-[var(--text)]">{formatAgo(status.last_activity)}</p>
          </div>

          {status.recent_notes.length > 0 && (
            <div className="border border-[var(--border)] bg-[var(--panel)] backdrop-blur-md rounded-lg p-5">
              <p className="text-sm text-[var(--text-dim)] mb-2">Ghi chú gần đây</p>
              <div className="flex flex-col gap-2">
                {status.recent_notes.map((note, i) => (
                  <p key={i} className="text-base text-[var(--text)]">
                    {note.content}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-[var(--text-dim)] mt-auto text-center">
        Trang chỉ xem — không điều khiển được EVA và không nghe lại được hội thoại.
      </p>
    </div>
  );
}
