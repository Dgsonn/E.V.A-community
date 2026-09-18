export function Gauge({ value, label }: { value: number; label: string }) {
  const circumference = 238.76;
  const clamped = Math.min(100, Math.max(0, value));
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-[86px] h-[86px]">
        <svg width="86" height="86" viewBox="0 0 90 90" className="-rotate-90">
          <circle cx="45" cy="45" r="38" stroke="var(--panel-2)" strokeWidth="7" fill="none" />
          <circle
            cx="45"
            cy="45"
            r="38"
            stroke="var(--cyan)"
            strokeWidth="7"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-[stroke-dashoffset] duration-500 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center font-[family-name:var(--font-display)] text-sm text-[var(--cyan)]">
          {Math.round(value)}%
        </div>
      </div>
      <label className="text-[0.7rem] text-[var(--text-dim)]">{label}</label>
    </div>
  );
}
