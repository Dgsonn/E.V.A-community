"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { ChatPanel } from "@/components/ChatPanel";
import { CoreEmblem } from "@/components/CoreEmblem";
import { SidePanel } from "@/components/SidePanel";
import { IdleOverlay } from "@/components/IdleOverlay";
import { TokenGate } from "@/components/TokenGate";
import { api, getToken, UnauthorizedError, type HistoryItem, type StatusResponse } from "@/lib/api";

const IDLE_TIMEOUT_MS = 3 * 60 * 1000;

export default function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [idle, setIdle] = useState(false);
  const [shutdownDone, setShutdownDone] = useState(false);
  // Lạc quan: coi như đã xác thực nếu trình duyệt đã lưu token từ trước — sai thì lần poll
  // đầu tiên sẽ nhận 401 và tự chuyển về màn hình nhập token (xem authFetch trong lib/api.ts).
  const [authed, setAuthed] = useState(() => !!getToken());
  const [authError, setAuthError] = useState<string | null>(null);

  const lastActivityRef = useRef(0);
  const wasSessionActiveRef = useRef(false);
  const lastHistorySignatureRef = useRef("");

  const wake = useCallback(() => {
    lastActivityRef.current = Date.now();
    setIdle(false);
  }, []);

  // Tự tối màn hình khi rảnh lâu, sáng lại ngay khi có hoạt động hoặc EVA được đánh thức
  useEffect(() => {
    lastActivityRef.current = Date.now();
    const checkIdle = () => {
      if (Date.now() - lastActivityRef.current > IDLE_TIMEOUT_MS) setIdle(true);
    };
    const id = setInterval(checkIdle, 5000);
    window.addEventListener("click", wake);
    window.addEventListener("touchstart", wake);
    return () => {
      clearInterval(id);
      window.removeEventListener("click", wake);
      window.removeEventListener("touchstart", wake);
    };
  }, [wake]);

  // Token sai/hết hạn -> authFetch tự xoá khỏi localStorage và ném UnauthorizedError — bắt
  // ở đây để quay về màn hình nhập token thay vì lặp lại lỗi 401 mỗi vòng poll.
  const handleUnauthorized = useCallback((err: unknown) => {
    if (err instanceof UnauthorizedError) {
      setAuthed(false);
      setAuthError(err.message);
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    if (!authed) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await api.getStatus();
        if (cancelled) return;
        setStatus(s);
        if (s.session_active && !wasSessionActiveRef.current) wake();
        wasSessionActiveRef.current = s.session_active;
      } catch (err) {
        if (handleUnauthorized(err)) return;
        // Server tạm không phản hồi — giữ nguyên dữ liệu cũ, thử lại ở lượt sau
      }
      if (!cancelled) setTimeout(poll, 3000);
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [wake, authed, handleUnauthorized]);

  useEffect(() => {
    if (!authed) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const items = await api.getHistory();
        if (cancelled) return;
        // /api/history luôn trả tối đa 50 tin — so độ dài không đủ để biết có tin mới hay
        // chưa (khi đã đầy 50, độ dài không đổi dù nội dung xoay vòng). So thêm timestamp
        // của tin cuối để phát hiện đúng thay đổi.
        const last = items[items.length - 1];
        const signature = `${items.length}|${last ? last.timestamp : ""}`;
        if (signature !== lastHistorySignatureRef.current) {
          lastHistorySignatureRef.current = signature;
          setHistory(items);
          wake();
        }
      } catch (err) {
        if (handleUnauthorized(err)) return;
        // bỏ qua, thử lại ở lượt sau
      }
      if (!cancelled) setTimeout(poll, 1000);
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [wake, authed, handleUnauthorized]);

  const sendText = (text: string) => {
    if (!text) return;
    api.sendMessage(text).catch(handleUnauthorized);
  };

  const revokeVoice = (name: string) => {
    if (!window.confirm(`Thu hồi quyền điều khiển của "${name}"?`)) return;
    api.revokeVoice(name).catch(handleUnauthorized);
  };

  const shutdown = () => {
    if (!window.confirm("Tắt hệ thống EVA?")) return;
    api.shutdown().catch(handleUnauthorized);
    setShutdownDone(true);
  };

  if (!authed) {
    return (
      <TokenGate
        error={authError}
        onSubmit={() => {
          setAuthError(null);
          setAuthed(true);
        }}
      />
    );
  }

  if (shutdownDone) {
    return (
      <div className="h-dvh flex items-center justify-center font-[family-name:var(--font-display)] text-[var(--text-dim)] text-lg bg-[var(--bg)]">
        Đã tắt hệ thống.
      </div>
    );
  }

  return (
    <div
      className="h-dvh flex flex-col overflow-hidden"
      style={{ background: "var(--bg)", backgroundImage: "var(--bg-glow)" }}
    >
      <IdleOverlay dimmed={idle} onWake={wake} />
      <TopBar
        cpu={status?.cpu ?? 0}
        ram={status?.ram ?? 0}
        sessionActive={status?.session_active ?? false}
        onShutdown={shutdown}
      />
      <div className="flex-1 min-h-0 flex flex-col lg:grid lg:grid-cols-[1.1fr_1fr_1.1fr] gap-3.5 p-3.5 overflow-y-auto lg:overflow-hidden">
        <ChatPanel history={history} onSend={sendText} />
        <CoreEmblem sessionActive={status?.session_active ?? false} wakeWord={status?.wake_word ?? "..."} />
        <SidePanel status={status} onQuickCommand={sendText} onRevokeVoice={revokeVoice} />
      </div>
    </div>
  );
}
