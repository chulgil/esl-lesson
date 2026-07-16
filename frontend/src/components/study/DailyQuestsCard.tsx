"use client";

import { useEffect, useState } from "react";
import { studyApi, type QuestBoard } from "@/lib/study-api";

/** 오늘의 미션 — 매일 다른 3종 + 도장, 완료 시 XP 보너스 (retention-plan.md).
 *  복습만 반복되는 단조로움을 깨고 게임·퍼즐로 세션을 다양화하는 장치. */
export function DailyQuestsCard() {
  const [board, setBoard] = useState<QuestBoard | null>(null);

  useEffect(() => {
    studyApi
      .quests()
      .then(setBoard)
      .catch(() => undefined);
  }, []);

  if (!board) return null;

  return (
    <div className="max-w-xl rounded-lg border-2 border-ink/10 bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-bold">오늘의 미션</p>
        <p className="text-xs opacity-60">
          {board.all_done
            ? `모두 완료! 보너스 +${board.all_done_xp} XP`
            : "3개 다 모으면 보너스 XP"}
        </p>
      </div>
      <ul className="mt-3 flex flex-col gap-2">
        {board.items.map((q) => (
          <li key={q.key} className="flex items-center gap-3">
            <Stamp done={q.done} />
            <div className="min-w-0 flex-1">
              <p
                className={`text-sm font-bold ${q.done ? "text-brick-green" : ""}`}
              >
                {q.title}
                <span className="ml-1.5 text-xs font-normal opacity-60">
                  +{q.xp} XP
                </span>
              </p>
              <p className="text-xs opacity-60">{q.desc}</p>
            </div>
            <span
              className={`text-xs font-bold whitespace-nowrap ${
                q.done ? "text-brick-green" : "opacity-50"
              }`}
            >
              {q.current}/{q.target}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 도장 — 완료 시 초록 스탬프 (노트에 찍는 참 잘했어요 도장 컨셉) */
function Stamp({ done }: { done: boolean }) {
  return (
    <span
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 transition ${
        done
          ? "-rotate-6 border-brick-green bg-brick-green/15 text-brick-green"
          : "border-dashed border-ink/20 text-ink/20"
      }`}
      aria-label={done ? "완료" : "미완료"}
    >
      {done ? (
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="m5 13 4 4L19 7" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden>
          <circle
            cx="12"
            cy="12"
            r="9"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray="3 3"
          />
        </svg>
      )}
    </span>
  );
}
