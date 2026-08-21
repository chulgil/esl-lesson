"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CHANGELOG,
  CHANGELOG_SEEN_KEY,
  LATEST_CHANGELOG_DATE,
} from "@/lib/changelog";

/** 홈 새소식 배너 — 아직 안 본 업데이트가 있을 때 1회 노출
 *  (docs/specs/updates-changelog.md). 성적표·복귀 감사 배너와 같은
 *  조용한 한 줄 패턴 — /updates 방문 또는 닫기로 사라진다. */
export function UpdatesNewsBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!LATEST_CHANGELOG_DATE) return;
    try {
      const seen = localStorage.getItem(CHANGELOG_SEEN_KEY);
      if (seen !== LATEST_CHANGELOG_DATE) setShow(true);
    } catch {
      // 저장소 접근 불가 — 배너 생략 (조르지 않는 쪽이 안전)
    }
  }, []);

  if (!show) return null;
  const latest = CHANGELOG[0];

  function dismiss() {
    try {
      localStorage.setItem(CHANGELOG_SEEN_KEY, LATEST_CHANGELOG_DATE);
    } catch {
      // 무해 — 다음 방문에 한 번 더 보일 뿐
    }
    setShow(false);
  }

  return (
    <div className="flex w-full flex-wrap items-center gap-2 rounded-md border-2 border-brick-blue/40 bg-brick-blue/5 px-4 py-2.5 text-left text-sm">
      <span>
        앱이 새로워졌어요 — <b>{latest.title}</b>
      </span>
      <Link
        href="/updates"
        onClick={dismiss}
        className="font-bold text-brick-blue underline-offset-2 hover:underline"
      >
        무엇이 바뀌었는지 보기 →
      </Link>
      <button
        type="button"
        aria-label="닫기"
        onClick={dismiss}
        className="ml-auto flex min-h-11 min-w-11 items-center justify-center rounded-md text-ink/50 hover:text-ink"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M18 6 6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
