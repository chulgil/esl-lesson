import type { Metadata, Viewport } from "next";
import { Gaegu, IBM_Plex_Sans_KR } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/nav/AppNav";
import { ChatWidget } from "@/components/chat/ChatWidget";
import { InviteToaster } from "@/components/game/InviteToaster";
import { HenyangPeek } from "@/components/theme/HenyangPeek";

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

const TITLE = "ESL Lessonaza — 유튜브로 배우는 영어";
const DESCRIPTION =
  "유튜브 스크립트에서 단어·숙어·패턴·문장을 추출해 망각곡선으로 복습하는 영어 학습 서비스";

// 모바일 키보드가 열리면 레이아웃 뷰포트를 줄여(resizes-content) 채팅 입력줄이
// 키보드 위로 따라오게 한다 (2026-07-28 모바일 채팅 UX). 확대 자체를 막는
// maximum-scale=1 은 접근성 훼손이라 쓰지 않는다 — iOS 자동 줌은 입력창
// 16px 폰트로 해결 (chat 입력줄 text-base).
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  interactiveWidget: "resizes-content",
};

export const metadata: Metadata = {
  metadataBase: new URL("https://esl.lessonaza.app"),
  title: TITLE,
  description: DESCRIPTION,
  manifest: "/manifest.json",
  icons: { icon: "/icon-192.png", apple: "/icon-192.png" },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: "/",
    siteName: "ESL Lessonaza",
    locale: "ko_KR",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: TITLE }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: ["/og.png"],
  },
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
            __html: `try{var t=localStorage.getItem("app.theme");if(t==="candy"||t==="lego"||t==="note"||t==="cat"||t==="excel")document.documentElement.setAttribute("data-theme",t)}catch(e){}`,
          }}
        />
        <AppNav />
        <InviteToaster />
        <ChatWidget />
        <HenyangPeek />
        {children}
      </body>
    </html>
  );
}
