"use client";

import { useEffect, useState } from "react";
import {
  gameApi,
  type WeeklyLeaderboards,
  type WeeklyRank,
} from "@/lib/game-api";

const BOARDS: {
  key: keyof WeeklyLeaderboards;
  title: string;
  unit: (v: number) => string;
}[] = [
  { key: "tetris", title: "워드 테트리스", unit: (v) => `${v}점` },
  { key: "quiz", title: "스피드 퀴즈", unit: (v) => `${v}점` },
  { key: "typing", title: "타자연습", unit: (v) => `${v}타` },
  { key: "scramble", title: "어순 조립", unit: (v) => `${v}점` },
];

/** 게임별 주간 최고 기록 top5 — 게임 허브 하단 (P3) */
export function WeeklyLeaderboardsCard() {
  const [boards, setBoards] = useState<WeeklyLeaderboards | null>(null);

  useEffect(() => {
    gameApi
      .leaderboards()
      .then(setBoards)
      .catch(() => undefined);
  }, []);

  if (!boards) return null;

  return (
    <section className="mt-6 max-w-4xl rounded-xl border-2 border-brick-yellow/50 bg-white p-5 shadow-sm">
      <h2 className="font-hand text-2xl font-bold">이번 주 명예의 전당</h2>
      <p className="mt-1 text-xs opacity-60">
        최근 7일 게임별 최고 기록 — 매주 새로 시작해요
      </p>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {BOARDS.map((board) => (
          <div key={board.key}>
            <p className="mb-1.5 text-sm font-bold">{board.title}</p>
            <Ranking rows={boards[board.key]} unit={board.unit} />
          </div>
        ))}
      </div>
    </section>
  );
}

function Ranking({
  rows,
  unit,
}: {
  rows: WeeklyRank[];
  unit: (v: number) => string;
}) {
  if (rows.length === 0) {
    return (
      <p className="rounded-md border-2 border-dashed border-ink/15 px-3 py-2 text-xs opacity-60">
        아직 기록이 없어요 — 첫 주인공이 되어보세요!
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-1">
      {rows.map((r, i) => (
        <li
          key={`${r.name}-${i}`}
          className={`flex items-center justify-between rounded-md border-2 px-2.5 py-1.5 text-sm ${
            r.me
              ? "border-brick-yellow bg-highlight/40 font-bold"
              : "border-ink/10"
          }`}
        >
          <span className="truncate">
            {i + 1}위 {r.name}
            {r.me && " (나)"}
          </span>
          <b className="ml-2 shrink-0">{unit(r.value)}</b>
        </li>
      ))}
    </ol>
  );
}
