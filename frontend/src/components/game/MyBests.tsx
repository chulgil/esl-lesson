"use client";

import { useEffect, useState } from "react";
import { gameApi, type GameBests } from "@/lib/game-api";

/** 게임 허브 — 내 최고 기록 스트립 (기록 깨기 동기, P1 데일리 루프) */
export function MyBests() {
  const [bests, setBests] = useState<GameBests | null>(null);

  useEffect(() => {
    gameApi
      .bests()
      .then(setBests)
      .catch(() => undefined);
  }, []);

  if (
    !bests ||
    (bests.tetris_best_score === 0 &&
      bests.quiz_best_score === 0 &&
      bests.typing_best_cpm === 0)
  ) {
    return null;
  }

  const entries = [
    { label: "테트리스 최고", value: `${bests.tetris_best_score}점` },
    { label: "퀴즈 최고", value: `${bests.quiz_best_score}점` },
    { label: "타자 최고", value: `${bests.typing_best_cpm}타` },
  ].filter((e) => !e.value.startsWith("0"));

  return (
    <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      <span className="font-bold">내 최고 기록</span>
      {entries.map((e) => (
        <span key={e.label} className="rounded-full bg-white px-3 py-1 shadow-sm">
          {e.label} <b>{e.value}</b>
        </span>
      ))}
      <span className="text-xs opacity-50">— 오늘 갱신해볼까요?</span>
    </p>
  );
}
