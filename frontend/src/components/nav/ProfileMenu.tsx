"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Me } from "@/lib/api";

/** 우측 상단 프로필 메뉴 — 표준 SaaS 패턴 (2026-07-28 내비 재설계).
 *  아바타(닉네임 이니셜) 클릭 → 닉네임·설정·백오피스(관리자)·로그아웃 드롭다운.
 *  구글 프로필 사진은 실명 노출 위험으로 쓰지 않는다 (chat 아바타와 동일 원칙). */
export function ProfileMenu({ me }: { me: Me }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // 바깥 클릭으로 닫기
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="내 계정 메뉴"
        aria-expanded={open}
        className="flex min-h-11 min-w-11 items-center justify-center"
      >
        <span
          className={`flex h-9 w-9 items-center justify-center rounded-full border-2 font-bold transition ${avatarColor(
            me.nickname,
          )} ${open ? "border-ink" : "border-ink/15 hover:border-ink/40"}`}
        >
          {me.nickname.slice(0, 1) || "?"}
        </span>
      </button>

      {open && (
        <div className="absolute top-full right-0 z-50 mt-2 w-56 max-w-[calc(100vw-1rem)] overflow-hidden rounded-lg border-2 border-ink/15 bg-white shadow-xl">
          <div className="border-b border-ink/10 px-4 py-3">
            <p className="truncate font-bold">{me.nickname}</p>
            <p className="truncate text-xs opacity-50">{me.email}</p>
          </div>
          <Link
            href="/settings"
            onClick={() => setOpen(false)}
            className="flex min-h-11 items-center px-4 text-sm font-bold transition hover:bg-ink/5"
          >
            설정
          </Link>
          {me.role === "admin" && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className="flex min-h-11 items-center px-4 text-sm font-bold transition hover:bg-ink/5"
            >
              백오피스
            </Link>
          )}
          {/* 로그아웃 — 공용 PC 대응. POST 후 303 리다이렉트를 브라우저가 따라감 */}
          <form
            action="/api/auth/logout"
            method="post"
            className="border-t border-ink/10"
          >
            <button
              type="submit"
              className="flex min-h-11 w-full items-center px-4 text-left text-sm font-bold text-brick-red transition hover:bg-brick-red/5"
            >
              로그아웃
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

/** 닉네임 해시 → 고정 색 (chat/page.tsx 아바타와 동일 팔레트) */
const AVATAR_COLORS = [
  "bg-brick-red/15 text-brick-red",
  "bg-brick-blue/15 text-brick-blue",
  "bg-brick-green/15 text-brick-green",
  "bg-brick-yellow/30 text-ink",
  "bg-highlight/50 text-ink",
];

function avatarColor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}
