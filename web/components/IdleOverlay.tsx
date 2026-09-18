export function IdleOverlay({ dimmed, onWake }: { dimmed: boolean; onWake: () => void }) {
  return (
    <div
      onClick={onWake}
      className={`fixed inset-0 z-50 bg-black transition-opacity duration-[1200ms] ease-in-out ${
        dimmed ? "opacity-95 pointer-events-auto" : "opacity-0 pointer-events-none"
      }`}
    />
  );
}
