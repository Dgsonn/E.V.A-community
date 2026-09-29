"use client";

import { useEffect, useState } from "react";

// Vài mức cố định thay vì tự do kéo thả — đơn giản hơn cho người dùng chính, đủ dùng cho nhu cầu
// "chữ to hơn chút" tới "chữ rất to". Lưu ở localStorage nên mỗi trình duyệt/thiết bị nhớ riêng.
const SCALE_STEPS = [0.9, 1, 1.15, 1.35];
const SCALE_KEY = "eva_text_scale";
const CONTRAST_KEY = "eva_high_contrast";

export function AccessibilityMenu() {
  const [scaleIndex, setScaleIndex] = useState(1);
  const [highContrast, setHighContrast] = useState(false);

  // Đọc lựa chọn đã lưu (nếu có) sau khi mount — tránh mismatch giữa server-render và trình
  // duyệt vì localStorage chỉ tồn tại phía client.
  useEffect(() => {
    try {
      const savedScale = Number(localStorage.getItem(SCALE_KEY));
      const idx = SCALE_STEPS.indexOf(savedScale);
      if (idx !== -1) setScaleIndex(idx);
      setHighContrast(localStorage.getItem(CONTRAST_KEY) === "1");
    } catch {
      // localStorage có thể bị chặn — dùng mặc định, không sao cả
    }
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--text-scale", String(SCALE_STEPS[scaleIndex]));
    try {
      localStorage.setItem(SCALE_KEY, String(SCALE_STEPS[scaleIndex]));
    } catch {
      // ignore
    }
  }, [scaleIndex]);

  useEffect(() => {
    if (highContrast) {
      document.documentElement.setAttribute("data-contrast", "high");
    } else {
      document.documentElement.removeAttribute("data-contrast");
    }
    try {
      localStorage.setItem(CONTRAST_KEY, highContrast ? "1" : "0");
    } catch {
      // ignore
    }
  }, [highContrast]);

  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={() => setScaleIndex((i) => Math.max(0, i - 1))}
        disabled={scaleIndex === 0}
        title="Chữ nhỏ hơn"
        aria-label="Chữ nhỏ hơn"
        className="w-8 h-8 rounded border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-dim)] text-xs flex items-center justify-center hover:border-[var(--border-strong)] disabled:opacity-40 cursor-pointer"
      >
        A-
      </button>
      <button
        onClick={() => setScaleIndex((i) => Math.min(SCALE_STEPS.length - 1, i + 1))}
        disabled={scaleIndex === SCALE_STEPS.length - 1}
        title="Chữ lớn hơn"
        aria-label="Chữ lớn hơn"
        className="w-8 h-8 rounded border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-dim)] text-sm flex items-center justify-center hover:border-[var(--border-strong)] disabled:opacity-40 cursor-pointer"
      >
        A+
      </button>
      <button
        onClick={() => setHighContrast((v) => !v)}
        title="Tương phản cao"
        aria-label="Tương phản cao"
        aria-pressed={highContrast}
        className={`w-8 h-8 rounded border text-xs flex items-center justify-center cursor-pointer ${
          highContrast
            ? "border-[var(--cyan)] bg-[var(--cyan-dim)] text-[var(--cyan)]"
            : "border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-dim)] hover:border-[var(--border-strong)]"
        }`}
      >
        ◐
      </button>
    </div>
  );
}
