"use client";

import Link from "next/link";
import { useState } from "react";
import { StreakHeatmap } from "@/components/study/StreakHeatmap";
import type { Stats } from "@/lib/study-api";

/** 오늘의 목표 카드 — 밀린 전체가 아닌 달성 가능한 소량 목표로 유도 (포기 방지 기획).
 *  진행바는 목표 기준 100% 상한: 100개 밀려도 "오늘 20개만"이 목표다.
 *
 *  모바일 한 화면 원칙 (2026-08-21): 잔디 달력·책갈피 설명은 접힌 상태가 기본 —
 *  홈이 한 화면에 들어오도록 카드 기본 높이는 제목+진행바+한 줄 코치로 제한한다. */
function BookmarkIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-brick-yellow-shadow"
      aria-hidden
    >
      <path d="M6 3h12v18l-6-4.5L6 21V3Z" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="transition-transform group-open:rotate-180"
      aria-hidden
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function DailyGoalCard({ stats }: { stats: Stats }) {
  const goal = stats.daily_goal || 20;
  const done = stats.reviews_today;
  const met = done >= goal;
  const todayTarget = Math.min(stats.due_count, Math.max(0, goal - done));
  // 잔디는 열릴 때만 마운트 — StreakHeatmap 의 "오늘로 스크롤" 이펙트가
  // 접힌(폭 0) 상태에서 돌면 무의미해진다
  const [heatmapOpen, setHeatmapOpen] = useState(false);

  return (
    <div className="w-full rounded-lg border-2 border-ink/10 bg-white p-3 text-left">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-bold">
          오늘의 목표
          <span
            className={`ml-2 font-normal ${met ? "font-bold text-brick-green" : "opacity-60"}`}
          >
            {Math.min(done, goal)}/{goal}
            {met && done > goal && ` (+${done - goal})`}
          </span>
        </p>
        <Link
          href="/settings"
          className="text-xs opacity-50 underline-offset-2 hover:underline"
        >
          목표 조정
        </Link>
      </div>
      <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-ink/10">
        <div
          className="h-full rounded-full bg-brick-green transition-[width]"
          style={{
            width: `${Math.min(100, Math.round((done / goal) * 100))}%`,
          }}
        />
      </div>
      <p className="mt-1.5 text-xs opacity-70">
        {met
          ? stats.due_count > 0
            ? `오늘 목표 달성! 더 해도 좋아요 — 남은 ${stats.due_count}개는 나눠서 갚으면 돼요`
            : "오늘 목표 달성! 밀린 복습도 없어요"
          : stats.due_count === 0
            ? done > 0
              ? "지금은 밀린 복습이 없어요 — 새 카드로 채워도 좋아요"
              : "지금은 밀린 복습이 없어요"
            : stats.due_count > todayTarget
              ? `오늘은 ${todayTarget}개만 하면 성공 — 밀린 ${stats.due_count}개는 나눠서 갚아요`
              : `오늘은 ${todayTarget}개만 하면 성공`}
      </p>
      <details
        className="group mt-2 border-t border-ink/10 pt-2"
        onToggle={(e) => setHeatmapOpen(e.currentTarget.open)}
      >
        <summary className="flex min-h-8 cursor-pointer list-none items-center gap-1.5 text-xs font-bold opacity-60 transition-opacity hover:opacity-90 [&::-webkit-details-marker]:hidden">
          <ChevronIcon />
          최근 1년 잔디
          <span className="ml-auto flex items-center gap-1 font-normal">
            <BookmarkIcon />
            책갈피 {stats.streak_savers ?? 0}개
          </span>
        </summary>
        {heatmapOpen && (
          <div className="mt-1">
            <StreakHeatmap
              daily={stats.daily}
              savedDays={stats.streak_saved_days}
            />
            {/* 책갈피 — 하루 놓쳐도 자동으로 연속 학습을 지켜주는 보호 장치 */}
            <p className="mt-2 text-xs opacity-70">
              책갈피는 하루 놓쳐도 연속 학습을 지켜줘요 (주 1회 목표 달성 시
              지급, 최대 2개)
            </p>
          </div>
        )}
      </details>
    </div>
  );
}
