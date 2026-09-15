import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediaWatch — 보도 공정성 & 보도자료 의존도 분석",
  description: "지자체 공식 보도자료 대비 복제율과 언론사별 검증·홍보 보도 실태",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
