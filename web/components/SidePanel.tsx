import type { StatusResponse } from "@/lib/api";
import { fmtUptime } from "@/lib/format";
import { Gauge } from "./Gauge";

const QUICK_COMMANDS = [
  { label: "Kiểm tra hệ thống", text: "kiểm tra hệ thống giúp tôi" },
  { label: "Lần đăng nhập cuối", text: "tôi đăng nhập lần cuối khi nào" },
  { label: "Xem ghi chú", text: "xem ghi chú giúp tôi" },
  { label: "Mở Notepad", text: "mở notepad giúp tôi" },
];

export function SidePanel({
  status,
  onQuickCommand,
  onRevokeVoice,
}: {
  status: StatusResponse | null;
  onQuickCommand: (text: string) => void;
  onRevokeVoice: (name: string) => void;
}) {
  const ownerLabel = !status
    ? "--"
    : !status.security_enabled
      ? (status.owner_name ? `${status.owner_name} (bảo mật tắt)` : "Không giới hạn (bảo mật tắt)")
      : status.is_owner === true
        ? status.owner_name || "Đã xác minh"
        : status.is_owner === false
          ? "Người lạ"
          : "Chưa xác minh";

  return (
    <aside className="panel-glass rounded-xl p-4 flex flex-col gap-5 overflow-y-auto shrink-0 lg:shrink">
      <div>
        <h3 className="section-label mb-3">Hệ thống</h3>
        <div className="flex gap-4 justify-center">
          <Gauge value={status?.cpu ?? 0} label="CPU" />
          <Gauge value={status?.ram ?? 0} label="RAM" />
        </div>
      </div>

      <div className="flex flex-col gap-1.5 text-sm">
        {[
          ["Chế độ AI", status ? (status.online_mode ? "Online" : "Offline") : "--"],
          ["Model", status?.model ?? "--"],
          ["Chủ nhân", ownerLabel],
          ["Camera", status ? (status.camera_on ? "Bật" : "Tắt") : "--"],
          ["Uptime", status ? fmtUptime(status.uptime_secs) : "--"],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between border-b border-[var(--border)] pb-1 text-[var(--text-dim)]">
            <span>{k}</span>
            <b className="text-[var(--text)] font-semibold">{v}</b>
          </div>
        ))}
      </div>

      <div>
        <h3 className="section-label mb-2">Người được uỷ quyền</h3>
        <div className="flex flex-col gap-1.5 text-sm">
          {!status || status.voice_profiles.length === 0 ? (
            <div className="text-[var(--text-dim)] italic text-[0.82rem]">Chưa có ai đăng ký giọng nói</div>
          ) : (
            status.voice_profiles.map((name) => (
              <div
                key={name}
                className="flex items-center justify-between gap-2 bg-[var(--panel-2)] border border-[var(--border)] rounded-md px-2.5 py-1.5"
              >
                <span>{name}</span>
                <button
                  onClick={() => onRevokeVoice(name)}
                  className="border border-[var(--border)] bg-transparent text-[var(--text-dim)] text-xs px-2 py-1 rounded cursor-pointer transition-colors hover:border-[var(--red)] hover:text-[var(--red)]"
                >
                  Thu hồi
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      <div>
        <h3 className="section-label mb-2">Lệnh nhanh</h3>
        <div className="flex flex-wrap gap-2">
          {QUICK_COMMANDS.map((c) => (
            <button
              key={c.text}
              onClick={() => onQuickCommand(c.text)}
              className="flex-1 basis-[calc(50%-4px)] px-2 py-2 rounded-md border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text)] text-[0.78rem] cursor-pointer transition-colors hover:border-[var(--cyan)] hover:text-[var(--cyan)]"
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        <h3 className="section-label mb-2">Ghi chú gần đây</h3>
        <div className="flex flex-col gap-2 text-[0.82rem] overflow-y-auto">
          {!status || status.notes.length === 0 ? (
            <div className="text-[var(--text-dim)] italic">Chưa có ghi chú nào</div>
          ) : (
            status.notes.map((n, i) => (
              <div key={i} className="bg-[var(--panel-2)] border border-[var(--border)] rounded-md px-2.5 py-2">
                {n.content}
                <span className="block font-[family-name:var(--font-display)] text-[0.65rem] text-[var(--text-dim)] mt-1">
                  {n.timestamp}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
}
