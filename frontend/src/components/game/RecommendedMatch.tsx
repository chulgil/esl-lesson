"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { studyApi, type Stats } from "@/lib/study-api";

/** 오늘의 추천 한 판 — 복습 상태 기반 게임 추천 (ux-redesign #6, P0 격상 2026-08-10).
 *
 * 게임 출제가 due·최근 오답 우선(P0-A)이라, 추천을 따르면 게임이 곧 복습이 된다.
 * 기존 study stats 재사용 — 신규 API 없음. 미로그인/로딩 실패 시 조용히 생략.
 */
export function RecommendedMatch() {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    studyApi
      .stats()
      .then(setStats)
      .catch(() => undefined);
  }, []);
  if (!stats) return null;
  // 카드 0장(신규)은 추천 숨김 — "오늘 복습 완료!" 거짓 카피 방지 + 게임 소재도
  // 아직 부족한 상태 (2026-08-10 기획 감사)
  const totalCards = stats.levels.reduce((sum, lv) => sum + lv.cards, 0);
  if (totalCards === 0) return null;

  const rec =
    stats.weak_count >= 3
      ? {
          href: "/game/tetris",
          name: "워드 테트리스",
          reason: `최근 헷갈린 단어 ${stats.weak_count}개가 우선 출제돼요`,
        }
      : stats.due_count > 0
        ? {
            href: "/game/quiz",
            name: "스피드 퀴즈 로얄",
            reason: `오늘 복습할 단어 ${stats.due_count}개가 문제로 먼저 나와요`,
          }
        : {
            href: "/game/typing",
            name: "영문 타자연습",
            reason: "오늘 복습 완료! 문장 타자로 가볍게 마무리해요",
          };

  return (
    <Link
      href={rec.href}
      className="mt-6 flex max-w-4xl flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border-2 border-brick-yellow bg-highlight/40 p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <span className="rounded-full bg-brick-yellow px-2.5 py-1 text-xs font-bold">
        오늘의 추천 한 판
      </span>
      <span className="font-hand text-xl font-bold">{rec.name}</span>
      <span className="text-sm opacity-70">{rec.reason}</span>
      <span className="ml-auto text-sm font-bold text-brick-blue">
        플레이 →
      </span>
    </Link>
  );
}
