"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { studyApi, type StudyDeck } from "@/lib/study-api";

/** 이어하기 줄 — 진행 중(1~5단계) 정복 루틴을 홈 CTA 아래 얇은 1줄로
 *  (cake-benchmark-2026-08 P1 C6: 복귀 마찰 제거 — 하던 것을 다시 찾게 하지 않는다).
 *  여러 개면 가장 많이 진행된 루틴 하나만. 없으면 렌더하지 않는다. */
export function ResumeRoutineCard() {
  const [deck, setDeck] = useState<StudyDeck | null>(null);

  useEffect(() => {
    studyApi
      .decks()
      .then((res) => {
        const inProgress = [...res.items]
          .filter((d) => d.routine_done > 0 && d.routine_done < 6)
          .sort((a, b) => b.routine_done - a.routine_done)[0];
        setDeck(inProgress ?? null);
      })
      .catch(() => undefined);
  }, []);

  if (!deck) return null;

  return (
    <Link
      href={`/library/${deck.content_id}`}
      className="flex min-h-11 w-full items-center gap-2 rounded-md border-2 border-ink/10 bg-white px-3 py-2 text-left text-sm transition-colors hover:border-brick-blue/50"
    >
      <span className="rounded bg-brick-blue/10 px-1.5 py-0.5 text-xs font-bold whitespace-nowrap text-brick-blue">
        정복 중 {deck.routine_done}/6
      </span>
      <span className="min-w-0 truncate font-bold">{deck.title}</span>
      <span className="ml-auto text-xs font-bold whitespace-nowrap text-brick-blue">
        이어하기 →
      </span>
    </Link>
  );
}
