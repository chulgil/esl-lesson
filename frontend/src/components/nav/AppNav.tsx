"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchMe, type Me } from "@/lib/api";

/** 전역 내비게이션 (듀오링고 패턴 차용 — docs/specs/ui-design.md 내비게이션)
 *  데스크톱: 상단 고정 헤더 / 모바일: 하단 탭바 고정. 현재 위치 하이라이트.
 */

const TABS = [
  { href: "/", label: "홈", match: (p: string) => p === "/", icon: HomeIcon },
  {
    href: "/study",
    label: "학습",
    match: (p: string) => p.startsWith("/study") || p.startsWith("/friends"),
    icon: StudyIcon,
  },
  {
    href: "/library",
    label: "라이브러리",
    match: (p: string) => p.startsWith("/library"),
    icon: LibraryIcon,
  },
  {
    href: "/my",
    label: "내 콘텐츠",
    match: (p: string) => p.startsWith("/my"),
    icon: MyIcon,
  },
  {
    href: "/game",
    label: "게임",
    match: (p: string) => p.startsWith("/game"),
    icon: GameIcon,
  },
  {
    href: "/settings",
    label: "설정",
    match: (p: string) => p.startsWith("/settings"),
    icon: SettingsIcon,
  },
];

export function AppNav() {
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    fetchMe().then(setMe);
  }, []);

  const visible =
    Boolean(me) && !pathname.startsWith("/admin") && pathname !== "/login";

  // 모바일 하단 탭바 높이만큼 본문 여백 확보
  useEffect(() => {
    document.body.classList.toggle("with-bottom-nav", visible);
    return () => document.body.classList.remove("with-bottom-nav");
  }, [visible]);

  if (!visible) return null;

  return (
    <>
      {/* 데스크톱: 상단 고정 헤더 */}
      <header className="sticky top-0 z-40 hidden items-center gap-1 border-b-2 border-ink/10 bg-paper/95 px-6 py-2 backdrop-blur sm:flex">
        <Link
          href="/"
          className="mr-4 font-hand text-2xl font-bold hover:opacity-80"
        >
          <span className="hl">ESL</span>
        </Link>
        {TABS.map((tab) => {
          const active = tab.match(pathname);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-11 items-center gap-2 rounded-md px-4 font-bold transition ${
                active ? "bg-ink text-white" : "hover:bg-ink/10"
              }`}
            >
              <tab.icon />
              {tab.label}
            </Link>
          );
        })}
        <div className="ml-auto flex items-center gap-3">
          {me?.role === "admin" && (
            <Link
              href="/admin"
              className="flex min-h-11 items-center rounded-md bg-brick-yellow/50 px-4 font-bold hover:bg-brick-yellow/80"
            >
              백오피스
            </Link>
          )}
          <span className="text-sm opacity-60">{me?.name}</span>
        </div>
      </header>

      {/* 모바일: 하단 탭바 고정 */}
      <nav
        aria-label="주요 메뉴"
        className="fixed inset-x-0 bottom-0 z-40 flex border-t-2 border-ink/15 bg-white sm:hidden"
      >
        {TABS.map((tab) => {
          const active = tab.match(pathname);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-16 flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-bold ${
                active ? "text-brick-red" : "text-ink/50"
              }`}
            >
              <tab.icon />
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function HomeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...stroke} aria-hidden>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h5v-6h4v6h5V9.5" />
    </svg>
  );
}

function StudyIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...stroke} aria-hidden>
      <path d="M4 19V5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2Z" />
      <path d="M4 19a2 2 0 0 0 2 2h13" />
      <path d="M9 7h6" />
    </svg>
  );
}

function LibraryIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...stroke} aria-hidden>
      <rect x="3" y="4" width="4" height="16" rx="1" />
      <rect x="10" y="4" width="4" height="16" rx="1" />
      <path d="m17.5 4.5 3.5 15" />
    </svg>
  );
}

function MyIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...stroke} aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <path d="M12 8v8M8 12h8" />
    </svg>
  );
}

function GameIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...stroke} aria-hidden>
      <rect x="2" y="7" width="20" height="11" rx="4" />
      <path d="M7 11v4M5 13h4M15.5 12h.01M18 14h.01" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...stroke} aria-hidden>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.56-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34h.01A1.7 1.7 0 0 0 10 4.09V4a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.01a1.7 1.7 0 0 0 1.56 1.03H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51.95Z" />
    </svg>
  );
}
