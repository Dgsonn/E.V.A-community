// Tất cả route đều cùng origin (Flask serve luôn phần build tĩnh này) nên API_BASE để rỗng.
// Đặt NEXT_PUBLIC_API_BASE khi chạy `next dev` trỏ sang 1 server Flask khác (cần bật CORS).
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

const TOKEN_KEY = "eva_dashboard_token";

// Mọi /api/* trên server đều yêu cầu header X-Auth-Token (xem core/web_interface.py) — token
// lưu ở localStorage (riêng theo từng trình duyệt/máy), không gửi kèm HTML nên không lộ qua
// việc xem nguồn trang.
export function getToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token.trim());
  } catch {
    // localStorage có thể bị chặn (private mode/site data tắt) — token chỉ sống hết phiên tab này
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

export class UnauthorizedError extends Error {}

async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init.headers ?? {}), "X-Auth-Token": getToken() },
  });
  if (resp.status === 401) {
    clearToken();
    throw new UnauthorizedError("Token không hợp lệ hoặc đã hết hạn.");
  }
  return resp;
}

export type StatusResponse = {
  cpu: number;
  ram: number;
  online_mode: boolean;
  model: string;
  session_active: boolean;
  is_owner: boolean | null;
  owner_name: string | null;
  security_enabled: boolean;
  voice_id_enrolled: boolean;
  voice_profiles: string[];
  camera_on: boolean;
  uptime_secs: number;
  wake_word: string;
  notes: { content: string; timestamp: string }[];
};

export type HistoryItem = {
  role: string;
  text: string;
  timestamp: string;
};

export type VoiceResult =
  | { status: "ok"; transcript: string; reply: string; audio_b64: string }
  | { status: "timeout"; transcript: string; message: string }
  | { status: "empty_transcript" | "stt_not_ready" | "error"; message: string };

async function getJson<T>(path: string): Promise<T> {
  const resp = await authFetch(path);
  return resp.json();
}

export const api = {
  getStatus: () => getJson<StatusResponse>("/api/status"),
  getHistory: () => getJson<HistoryItem[]>("/api/history"),

  sendMessage: (text: string) =>
    authFetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),

  sendVoice: async (wavBlob: Blob): Promise<VoiceResult> => {
    const form = new FormData();
    form.append("audio", wavBlob, "voice.wav");
    const resp = await authFetch("/api/voice", { method: "POST", body: form });
    return resp.json();
  },

  // Tạm dùng để chẩn đoán lỗi ghi âm trên Safari/iOS — gửi luôn cả khi lỗi (không await/throw)
  // để không làm hỏng luồng chính đang chạy, chỉ cần biết đã tới bước nào.
  debugLog: (msg: string) => {
    try {
      void authFetch("/api/debug_log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ msg }),
      });
    } catch {
      // ignore
    }
  },

  revokeVoice: (name: string) =>
    authFetch("/api/revoke_voice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),

  shutdown: () => authFetch("/api/shutdown", { method: "POST" }),
};
