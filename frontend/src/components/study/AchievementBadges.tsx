"use client";

import { useState } from "react";
import type { Achievement, AchievementTier } from "@/lib/study-api";
import { APP_THEMES } from "@/lib/theme";

/** 업적 스티커 벽 — 패밀리 섹션 + 난이도 티어(초급/중급/고급/마스터) 링 컬러.
 *  달성=컬러 스티커, 미달성=점선+진행 바 (노트 컨셉, P3).
 *  29종 전부 펼치면 벽이 너무 길다 — 섹션당 4개(한 줄)만 보이고 더보기로 확장. */

const FAMILY_LABELS: Record<string, string> = {
  study: "학습",
  streak: "꾸준함",
  game: "게임",
  social: "친구",
  exam: "시험",
};
const FAMILY_ORDER = ["study", "streak", "game", "social", "exam"];

const TIER_LABELS: Record<AchievementTier, string> = {
  beginner: "초급",
  intermediate: "중급",
  advanced: "고급",
  master: "마스터",
};

/** 티어별 링·칩 색 — 달성 시에만 컬러 (미달성은 회색 통일) */
const TIER_RING: Record<AchievementTier, string> = {
  beginner: "border-brick-green bg-brick-green/15",
  intermediate: "border-brick-blue bg-brick-blue/15",
  advanced: "border-brick-yellow bg-brick-yellow/30",
  master: "border-brick-red bg-brick-red/15",
};
const TIER_CHIP: Record<AchievementTier, string> = {
  beginner: "bg-brick-green/25",
  intermediate: "bg-brick-blue/25",
  advanced: "bg-brick-yellow/50",
  master: "bg-brick-red/25 text-brick-red",
};

const THEME_LABELS: Record<string, string> = Object.fromEntries(
  APP_THEMES.map((t) => [t.key, t.label]),
);

/** 섹션당 기본 노출 개수 — 4열 그리드의 정확히 한 줄 */
const VISIBLE_COUNT = 4;

export function AchievementBadges({ items }: { items: Achievement[] }) {
  return (
    <div className="flex flex-col gap-5">
      {FAMILY_ORDER.map((family) => {
        const group = items.filter((a) => a.family === family);
        if (group.length === 0) return null;
        return <FamilySection key={family} family={family} group={group} />;
      })}
    </div>
  );
}

function FamilySection({
  family,
  group,
}: {
  family: string;
  group: Achievement[];
}) {
  const [expanded, setExpanded] = useState(false);
  const achieved = group.filter((a) => a.achieved).length;
  const hidden = group.length - VISIBLE_COUNT;
  const visible = expanded ? group : group.slice(0, VISIBLE_COUNT);
  return (
    <section>
      <h3 className="mb-2 flex items-baseline gap-2 text-sm font-bold">
        {FAMILY_LABELS[family] ?? family}
        <span className="text-[10px] font-normal opacity-50">
          {achieved}/{group.length}
        </span>
      </h3>
      {/* 모바일도 4열(컴팩트 타일) — 기본 노출 4개가 항상 꽉 찬 한 줄이 된다 */}
      <ul className="grid grid-cols-4 gap-2 sm:gap-3">
        {visible.map((a) => (
          <StickerCard key={a.key} a={a} />
        ))}
      </ul>
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-2 min-h-11 w-full rounded-lg border-2 border-dashed border-ink/20 bg-white text-xs font-bold opacity-70 transition hover:border-ink/40 hover:opacity-100"
        >
          {expanded ? "접기" : `더보기 (+${hidden})`}
        </button>
      )}
    </section>
  );
}

function StickerCard({ a }: { a: Achievement }) {
  const ring = a.achieved
    ? a.tier
      ? TIER_RING[a.tier]
      : "border-ink bg-brick-yellow"
    : "border-ink/20 bg-ink/5 text-ink/40";
  return (
    <li
      title={`${a.title} — ${a.desc}`}
      className={`relative flex flex-col items-center gap-1 rounded-lg border-2 p-2 text-center sm:gap-1.5 sm:p-3 ${
        a.achieved
          ? "border-brick-yellow bg-highlight/30"
          : "border-dashed border-ink/20 bg-white opacity-70"
      }`}
    >
      {/* 티어 칩 — 카드 안쪽 모서리 (밖으로 튀어나오면 이웃 카드와 겹쳐 깨져 보임) */}
      {a.tier && (
        <span
          className={`absolute top-1 right-1 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${
            a.achieved ? TIER_CHIP[a.tier] : "bg-ink/10 text-ink/50"
          }`}
        >
          {TIER_LABELS[a.tier]}
        </span>
      )}
      <span
        className={`flex h-9 w-9 items-center justify-center rounded-full border-2 sm:h-11 sm:w-11 ${ring}`}
      >
        <BadgeIcon name={a.key} />
      </span>
      <span className="text-[10px] leading-tight font-bold sm:text-xs">
        {a.title}
      </span>
      {/* 보상 테마 예고 — "이 업적을 깨면 테마가 열린다" 를 스티커에서 광고 */}
      {a.reward_theme && (
        <span
          className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${
            a.achieved
              ? "bg-brick-green/20 text-brick-green"
              : "bg-highlight/70"
          }`}
        >
          {a.achieved
            ? `${THEME_LABELS[a.reward_theme] ?? a.reward_theme} 테마 획득`
            : `보상: ${THEME_LABELS[a.reward_theme] ?? a.reward_theme} 테마`}
        </span>
      )}
      {a.achieved ? (
        <span className="text-[10px] font-bold text-brick-green">달성!</span>
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
  );
}

/** 업적별 라인 아이콘 (유니코드 이모지 대신 SVG — 테마 일관성).
 *  같은 지표의 티어들은 접두어(reviews_/wins_ 등)로 패밀리 아이콘 공유. */
function BadgeIcon({ name }: { name: string }) {
  const prefix = name.split("_")[0];
  const path =
    ICON_PATHS[name] ?? PREFIX_ICON_PATHS[prefix] ?? ICON_PATHS.first_review;
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

// 연필 — 첫 복습 / 불꽃 — 스트릭 / 쌓인 층 — 복습 / 펼친 책 — 단어
// 트로피 — 승리 / 게임패드 — 참여 / 키보드 — 타자 / 두 사람 — 친구
const PENCIL = <path d="M17 3l4 4L8 20l-5 1 1-5L17 3z" />;
const BOOK = (
  <path d="M12 6c-2-1.5-5-2-8-2v14c3 0 6 .5 8 2 2-1.5 5-2 8-2V4c-3 0-6 .5-8 2zm0 0v14" />
);
const LAYERS = (
  <path d="M12 2l10 5-10 5L2 7l10-5zM2 12l10 5 10-5M2 17l10 5 10-5" />
);
const FLAME = (
  <path d="M12 2c1 4-3 5-3 9a3 3 0 006 0c0-2-1-3-1-3 3 1 5 3.5 5 7a7 7 0 11-14 0c0-6 6-8 7-13z" />
);
const TROPHY = (
  <path d="M8 21h8m-4-4v4m-6-17h12v5a6 6 0 01-12 0V4zM6 5H3a4 4 0 004 4m11-4h3a4 4 0 01-4 4" />
);
const GAMEPAD = (
  <path d="M6 9h12a4 4 0 014 4v3a3 3 0 01-5.5 1.7L15 16H9l-1.5 1.7A3 3 0 012 16v-3a4 4 0 014-4zm2 2v4m-2-2h4m6-1h.01M18 14h.01" />
);
const KEYBOARD = (
  <path d="M3 7h18a1 1 0 011 1v8a1 1 0 01-1 1H3a1 1 0 01-1-1V8a1 1 0 011-1zm3 3h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" />
);
const PEOPLE = (
  <path d="M9 11a4 4 0 100-8 4 4 0 000 8zm-7 10a7 7 0 0114 0M19 8a3 3 0 11-4-4m7 17a6 6 0 00-4-5.5" />
);
const CALENDAR = (
  <path d="M5 5h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1zm3-3v4m8-4v4M4 10h16" />
);
const TARGET = (
  <path d="M12 21a9 9 0 100-18 9 9 0 000 18zm0-4a5 5 0 100-10 5 5 0 000 10zm0-4a1 1 0 100-2 1 1 0 000 2z" />
);
// 시험지 — 시험 패밀리 / 왕관 — 1위 등극 / 메달 — 만점
const PAPER = (
  <path d="M7 2h7l5 5v14a1 1 0 01-1 1H7a1 1 0 01-1-1V3a1 1 0 011-1zm7 0v5h5M9 12h6M9 16h6" />
);
const CROWN = <path d="M3 8l4 4 5-6 5 6 4-4-1.5 10h-15L3 8z" />;
const MEDAL = (
  <path d="M12 14a4.5 4.5 0 100-9 4.5 4.5 0 000 9zm-2.5 1.5L8 21l4-2 4 2-1.5-5.5" />
);

const ICON_PATHS: Record<string, React.ReactNode> = {
  first_review: PENCIL,
  first_win: TROPHY,
  first_friend: PEOPLE,
  streak_30: CALENDAR,
  streak_365: CALENDAR,
  first_exam: PAPER,
  exam_perfect: MEDAL,
  exam_champion: CROWN,
};

const PREFIX_ICON_PATHS: Record<string, React.ReactNode> = {
  reviews: LAYERS,
  words: BOOK,
  streak: FLAME,
  wins: TROPHY,
  games: GAMEPAD,
  typing: KEYBOARD,
  friends: PEOPLE,
  goal: TARGET,
  exam: PAPER,
  exams: PAPER,
};
