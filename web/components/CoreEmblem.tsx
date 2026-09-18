export function CoreEmblem({ sessionActive, wakeWord }: { sessionActive: boolean; wakeWord: string }) {
  return (
    <section className="panel-glass rounded-xl p-6 hidden lg:flex flex-col items-center justify-center text-center shrink-0">
      <div className="relative w-[200px] h-[200px] sm:w-[220px] sm:h-[220px] flex items-center justify-center">
        <div className="absolute inset-0 rounded-full border border-[var(--cyan-dim)]" />
        <div className="absolute w-[170px] h-[170px] sm:w-[184px] sm:h-[184px] rounded-full border border-dashed border-[var(--border-strong)] animate-spin-slow" />
        <div className="absolute w-[130px] h-[130px] sm:w-[140px] sm:h-[140px] rounded-full border border-[var(--cyan)] opacity-50 animate-spin-slow-reverse" />
        <div
          className={`w-[86px] h-[86px] sm:w-[92px] sm:h-[92px] rounded-full ${
            sessionActive ? "animate-pulse-glow" : ""
          }`}
          style={{
            background:
              "radial-gradient(circle, var(--cyan) 0%, rgba(45,212,255,0.15) 70%, transparent 100%)",
          }}
        />
      </div>
      <div className="mt-5 font-[family-name:var(--font-display)] text-xl tracking-[0.15em] text-[var(--cyan)]">
        EVA
      </div>
      <div
        className={`mt-1 font-[family-name:var(--font-display)] text-xs tracking-wider ${
          sessionActive ? "text-[var(--green)]" : "text-[var(--text-dim)]"
        }`}
      >
        {sessionActive ? "ĐANG HOẠT ĐỘNG" : "CHẾ ĐỘ CHỜ"}
      </div>
      <div className="mt-4 text-sm text-[var(--text-dim)]">
        Nói <b className="text-[var(--cyan)]">&quot;{wakeWord}&quot;</b> để đánh thức
      </div>
    </section>
  );
}
