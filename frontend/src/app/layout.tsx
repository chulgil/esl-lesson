import type { Metadata } from "next";
import { Gaegu, IBM_Plex_Sans_KR } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/nav/AppNav";

const gaegu = Gaegu({
  variable: "--font-gaegu",
  weight: ["400", "700"],
  subsets: ["latin"],
});

const body = IBM_Plex_Sans_KR({
  variable: "--font-body",
  weight: ["400", "500", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ESL Lessonaza — 유튜브로 배우는 영어",
  description:
    "유튜브 스크립트에서 단어·숙어·패턴·문장을 추출해 망각곡선으로 복습하는 영어 학습 서비스",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className={`${gaegu.variable} ${body.variable} antialiased`}>
        {/* 전역 테마 부트 — 페인트 전에 data-theme 적용 (FOUC 방지) */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("app.theme");if(t==="candy"||t==="lego"||t==="note")document.documentElement.setAttribute("data-theme",t)}catch(e){}`,
          }}
        />
        <AppNav />
        {children}
      </body>
    </html>
  );
}
