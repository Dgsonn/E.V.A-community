import type { Metadata } from "next";
import { JetBrains_Mono, Inter } from "next/font/google";
import "./globals.css";

const display = JetBrains_Mono({
  variable: "--font-display",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "700"],
});

const body = Inter({
  variable: "--font-body",
  subsets: ["latin", "vietnamese"],
});

export const metadata: Metadata = {
  title: "EVA Dashboard",
  description: "Bảng điều khiển trợ lý AI EVA",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi" className={`${display.variable} ${body.variable} h-full`}>
      <body className="h-full antialiased">{children}</body>
    </html>
  );
}
