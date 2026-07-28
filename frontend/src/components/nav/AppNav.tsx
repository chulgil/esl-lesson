"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChatNavButton } from "@/components/chat/ChatNavButton";
import { fetchMe, type Me } from "@/lib/api";
import { useAppTheme } from "@/lib/theme";

/** 전역 내비게이션 (듀오링고 패턴 차용 — docs/specs/ui-design.md 내비게이션)
 *  데스크톱: 상단 고정 헤더 / 모바일: 하단 탭바 고정. 현재 위치 하이라이트.
 *  데스크톱 헤더는 접기 지원 (2026-07-28 요청) — 접으면 테마별 손잡이
 *  (종이 테마 = 책갈피 리본, 오피스 = 리본 탭)만 남고, 마우스를 대면
 *  살짝 펼쳐지고(피크) 손잡이를 클릭하면 고정 해제된다.
 */

const NAV_COLLAPSE_KEY = "app.nav-collapsed";

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
  const theme = useAppTheme();
  const [me, setMe] = useState<Me | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [peek, setPeek] = useState(false);
  // 접기 버튼과 손잡이가 같은 자리라, 접는 순간 커서 아래 손잡이의 hover 가
  // 즉시 피크를 되살린다 — 접기 직후 잠깐 피크 억제
  const suppressPeekUntil = useRef(0);

  useEffect(() => {
    fetchMe().then(setMe);
    try {
      setCollapsed(localStorage.getItem(NAV_COLLAPSE_KEY) === "true");
    } catch {
      // 프라이빗 모드 등 — 기본(펼침) 유지
    }
  }, []);

  function persistCollapsed(next: boolean) {
    setCollapsed(next);
    setPeek(false);
    if (next) suppressPeekUntil.current = Date.now() + 700;
    try {
      localStorage.setItem(NAV_COLLAPSE_KEY, String(next));
    } catch {
      // 저장 실패해도 화면 적용은 진행
    }
  }

  function tryPeek() {
    if (Date.now() >= suppressPeekUntil.current) setPeek(true);
  }

  const visible =
    Boolean(me) && !pathname.startsWith("/admin") && pathname !== "/login";

  // 모바일 하단 탭바 높이만큼 본문 여백 확보 + 데스크톱 헤더 접힘을
  // 채팅 nav-safe CSS(.h-dvh-nav-safe/.dock-right-nav-safe)에 전파
  useEffect(() => {
    document.body.classList.toggle("with-bottom-nav", visible);
    document.body.classList.toggle("nav-collapsed", visible && collapsed);
    return () => {
      document.body.classList.remove("with-bottom-nav");
      document.body.classList.remove("nav-collapsed");
    };
  }, [visible, collapsed]);

  if (!visible) return null;

  const headerInFlow = !collapsed;
  const showHeader = !collapsed || peek;

  return (
    <>
      {/* 데스크톱: 상단 고정 헤더 — 접힘 시 피크(hover) 동안만 오버레이로 표시 */}
      {showHeader && (
        <header
          onMouseLeave={() => setPeek(false)}
          className={`${
            headerInFlow ? "sticky" : "fixed inset-x-0 shadow-md"
          } top-0 z-40 hidden items-center gap-1 border-b-2 border-ink/10 bg-paper/95 px-6 py-2 backdrop-blur sm:flex`}
        >
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
            <ChatNavButton />
            {me?.role === "admin" && (
              <Link
                href="/admin"
                className="flex min-h-11 items-center rounded-md bg-brick-yellow/50 px-4 font-bold hover:bg-brick-yellow/80"
              >
                백오피스
              </Link>
            )}
            <span className="text-sm opacity-60">{me?.nickname}</span>
            <button
              type="button"
              onClick={() => persistCollapsed(!collapsed)}
              aria-label={collapsed ? "메뉴 고정 펼치기" : "메뉴 접기"}
              title={collapsed ? "메뉴 고정 펼치기" : "메뉴 접기"}
              className="flex min-h-9 min-w-9 items-center justify-center rounded-md opacity-40 transition hover:bg-ink/10 hover:opacity-100"
            >
              <ChevronUpIcon />
            </button>
          </div>
        </header>
      )}

      {/* 접힘 손잡이 — 테마별 컨셉: 종이 = 책에 꽂힌 책갈피 리본 / 오피스 = 리본 탭 */}
      {collapsed && !peek && (
        <button
          type="button"
          onMouseEnter={tryPeek}
          onFocus={tryPeek}
          onClick={() => persistCollapsed(false)}
          aria-label="메뉴 열기"
          title="메뉴 열기"
          className="fixed top-0 right-10 z-40 hidden sm:block"
        >
          {theme === "excel" ? (
            <span className="flex items-center gap-1 rounded-b-sm border border-t-0 border-[#c9cfd6] bg-[#f6f8f9] px-3 py-1 text-xs text-[#444] shadow-sm hover:bg-[#e2efda]">
              메뉴 <span className="text-[9px]">▾</span>
            </span>
          ) : (
            <span
              aria-hidden
              className="block h-12 w-8 bg-brick-red shadow-md transition-transform hover:translate-y-0.5"
              style={{
                clipPath: "polygon(0 0, 100% 0, 100% 100%, 50% 78%, 0 100%)",
              }}
            />
          )}
        </button>
      )}

      {/* 모바일: 하단 탭바 고정 (채팅 진입은 우하단 ChatWidget 런처) */}
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

function ChevronUpIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" {...stroke} aria-hidden>
      <path d="m18 15-6-6-6 6" />
    </svg>
  );
}

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
