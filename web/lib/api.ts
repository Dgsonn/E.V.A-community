// Tất cả route đều cùng origin (Flask serve luôn phần build tĩnh này) nên API_BASE để rỗng.
// Đặt NEXT_PUBLIC_API_BASE khi chạy `next dev` trỏ sang 1 server Flask khác (cần bật CORS).
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export class UnauthorizedError extends Error {}

export type FamilyStatusResponse = {
  session_active: boolean;
  uptime_secs: number;
  last_activity: string | null;
  recent_notes: { content: string; timestamp: string }[];
};

export const api = {
  // Trang /family (web/app/family/page.tsx) xác thực bằng FAMILY_TOKEN gửi kèm trong link.
  getFamilyStatus: async (token: string): Promise<FamilyStatusResponse> => {
    const resp = await fetch(`${API_BASE}/api/family_status`, {
      headers: { "X-Family-Token": token },
    });
    if (!resp.ok) throw new UnauthorizedError("Link không hợp lệ hoặc đã hết hạn.");
    return resp.json();
  },
};
