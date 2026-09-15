import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Parallax — 보도 시차 분석",
  description:
    "같은 사건도 보는 위치에 따라 달라 보입니다. 공식 보도자료를 기준점으로 두고 " +
    "각 언론사 보도가 그로부터 얼마나 떨어져 있는지를 측정합니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
