"use client";

import type { Achievement } from "@/lib/study-api";

/** 업적 스티커 그리드 — 달성=컬러 스티커, 미달성=점선+진행 바 (노트 컨셉, P3) */
export function AchievementBadges({ items }: { items: Achievement[] }) {
  return (
    <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5">
      {items.map((a) => (
        <li
          key={a.key}
          title={`${a.title} — ${a.desc}`}
          className={`flex flex-col items-center gap-1.5 rounded-lg border-2 p-3 text-center ${
            a.achieved
              ? "border-brick-yellow bg-highlight/30"
              : "border-dashed border-ink/20 bg-white opacity-70"
          }`}
        >
          <span
            className={`flex h-11 w-11 items-center justify-center rounded-full border-2 ${
              a.achieved
                ? "border-ink bg-brick-yellow text-ink"
                : "border-ink/20 bg-ink/5 text-ink/40"
            }`}
          >
            <BadgeIcon name={a.key} />
          </span>
          <span className="text-xs leading-tight font-bold">{a.title}</span>
          {a.achieved ? (
            <span className="text-[10px] font-bold text-brick-green">
              달성!
            </span>
          ) : (
            <>
              <span className="h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
                <span
                  className="block h-full rounded-full bg-brick-blue"
                  style={{ width: `${Math.round(a.progress * 100)}%` }}
                />
              </span>
              <span className="text-[10px] opacity-60">
                {a.current}/{a.target}
              </span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

/** 업적별 라인 아이콘 (유니코드 이모지 대신 SVG — 테마 일관성) */
function BadgeIcon({ name }: { name: string }) {
  const path = ICON_PATHS[name] ?? ICON_PATHS.first_review;
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-6 w-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {path}
    </svg>
  );
}

const ICON_PATHS: Record<string, React.ReactNode> = {
  // 연필 — 첫 복습
  first_review: <path d="M17 3l4 4L8 20l-5 1 1-5L17 3z" />,
  // 펼친 책 — 100단어
  words_100: (
    <path d="M12 6c-2-1.5-5-2-8-2v14c3 0 6 .5 8 2 2-1.5 5-2 8-2V4c-3 0-6 .5-8 2zm0 0v14" />
  ),
  // 쌓인 층 — 복습 1000회
  reviews_1000: (
    <path d="M12 2l10 5-10 5L2 7l10-5zM2 12l10 5 10-5M2 17l10 5 10-5" />
  ),
  // 불꽃 — 7일 연속
  streak_7: (
    <path d="M12 2c1 4-3 5-3 9a3 3 0 006 0c0-2-1-3-1-3 3 1 5 3.5 5 7a7 7 0 11-14 0c0-6 6-8 7-13z" />
  ),
  // 달력 — 30일 연속
  streak_30: (
    <path d="M5 5h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1zm3-3v4m8-4v4M4 10h16" />
  ),
  // 트로피 — 첫 승리
  first_win: (
    <path d="M8 21h8m-4-4v4m-6-17h12v5a6 6 0 01-12 0V4zM6 5H3a4 4 0 004 4m11-4h3a4 4 0 01-4 4" />
  ),
  // 게임패드 — 10판
  games_10: (
    <path d="M6 9h12a4 4 0 014 4v3a3 3 0 01-5.5 1.7L15 16H9l-1.5 1.7A3 3 0 012 16v-3a4 4 0 014-4zm2 2v4m-2-2h4m6-1h.01M18 14h.01" />
  ),
  // 키보드 — 타자 300
  typing_300: (
    <path d="M3 7h18a1 1 0 011 1v8a1 1 0 01-1 1H3a1 1 0 01-1-1V8a1 1 0 011-1zm3 3h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" />
  ),
  // 두 사람 — 첫 친구
  first_friend: (
    <path d="M9 11a4 4 0 100-8 4 4 0 000 8zm-7 10a7 7 0 0114 0M19 8a3 3 0 11-4-4m7 17a6 6 0 00-4-5.5" />
  ),
};
