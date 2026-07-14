"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { friendsApi } from "@/lib/friends-api";
import { studyApi, type Stats, type StudyRank } from "@/lib/study-api";

/** 학습 허브 — 학습 관련 기능을 한눈에 (게임 허브와 동일 패턴, 2026-07-14 IA 정리) */
export default function StudyHubPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [friendSignal, setFriendSignal] = useState<{
    studying: number;
    incoming: number;
  } | null>(null);
  const [ranks, setRanks] = useState<StudyRank[]>([]);

  useEffect(() => {
    studyApi
      .stats()
      .then(setStats)
      .catch(() => undefined);
    studyApi
      .leaderboard()
      .then((res) => setRanks(res.items))
      .catch(() => undefined);
    friendsApi
      .list()
      .then((f) =>
        setFriendSignal({
          studying: f.friends.filter((x) => x.studying).length,
          incoming: f.incoming.length,
        }),
      )
      .catch(() => undefined);
  }, []);

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      <header className="mb-2">
        <h1 className="font-hand text-4xl font-bold">
          <span className="hl">학습</span>
        </h1>
        <p className="mt-2 text-sm opacity-70">
          잊기 전에 다시 만나는 복습 — 오늘 할 일부터 시작해요.
        </p>
      </header>

      {/* 1순위 CTA — 오늘의 학습 */}
      <section className="mt-6 max-w-4xl rounded-xl border-2 border-brick-green/40 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-52 flex-1">
            <h2 className="font-hand text-2xl font-bold">오늘의 학습</h2>
            <p className="mt-1 text-sm opacity-70">
              {stats
                ? stats.due_count > 0
                  ? `복습할 카드 ${stats.due_count}개가 기다리고 있어요`
                  : "지금은 밀린 복습이 없어요 — 새 카드를 만나러 가볼까요?"
                : "복습 큐를 확인하는 중..."}
              {stats && stats.streak_days > 0 && (
                <span className="ml-2 rounded bg-highlight/60 px-1.5 py-0.5 text-xs font-bold">
                  {stats.streak_days}일 연속
                </span>
              )}
            </p>
          </div>
          <Brick color="green" href="/study/session">
            학습 시작{stats ? ` (${stats.due_count})` : ""}
          </Brick>
        </div>
      </section>

      <div className="mt-5 grid max-w-4xl gap-5 lg:grid-cols-2">
        <Link
          href="/study/network"
          className="group flex flex-col rounded-xl border-2 border-brick-blue/40 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
        >
          <h2 className="font-hand text-2xl font-bold group-hover:underline group-hover:decoration-highlight group-hover:decoration-4 group-hover:underline-offset-4">
            어휘망
          </h2>
          <p className="mt-1 text-sm opacity-80">
            내가 배운 단어들이 비슷한 뜻끼리 연결된 지도
          </p>
          <ul className="mt-3 flex flex-col gap-1.5 text-xs leading-relaxed opacity-70">
            <li>· 단어를 탭하면 뜻·뉘앙스·예문 카드가 열려요</li>
            <li>· 점선 단어는 아직 안 배운 추천 — 한 번에 학습에 추가</li>
          </ul>
          <span className="mt-4 text-sm font-bold text-brick-blue">
            열어보기 →
          </span>
        </Link>

        <Link
          href="/friends"
          className="group flex flex-col rounded-xl border-2 border-brick-red/40 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
        >
          <h2 className="flex items-center gap-2 font-hand text-2xl font-bold group-hover:underline group-hover:decoration-highlight group-hover:decoration-4 group-hover:underline-offset-4">
            친구
            {friendSignal && friendSignal.incoming > 0 && (
              <span className="rounded-full bg-brick-red px-2 py-0.5 text-xs font-bold text-brick-label">
                요청 {friendSignal.incoming}
              </span>
            )}
          </h2>
          <p className="mt-1 text-sm opacity-80">
            친구를 추가하고, 학습 중인 친구를 관전해요
          </p>
          <ul className="mt-3 flex flex-col gap-1.5 text-xs leading-relaxed opacity-70">
            <li>· 이메일로 친구 요청 — 상대가 수락하면 연결</li>
            <li>· 친구가 허락하면 학습 화면을 실시간으로 볼 수 있어요</li>
          </ul>
          <span className="mt-4 text-sm font-bold text-brick-red">
            {friendSignal && friendSignal.studying > 0
              ? `지금 ${friendSignal.studying}명 학습 중 →`
              : "친구 보기 →"}
          </span>
        </Link>
      </div>

      {/* 주간 랭킹 — 친구와의 학습량 경쟁 (P1 데일리 루프) */}
      {ranks.length > 0 && (
        <section className="mt-5 max-w-4xl rounded-xl border-2 border-brick-yellow/50 bg-white p-5 shadow-sm">
          <h2 className="font-hand text-2xl font-bold">이번 주 학습 랭킹</h2>
          <p className="mt-1 text-xs opacity-60">
            최근 7일 복습 수 — 친구와 함께 집계돼요
          </p>
          <ol className="mt-3 flex flex-col gap-1.5">
            {ranks.map((r) => (
              <li
                key={r.user_id}
                className={`flex items-center justify-between rounded-md border-2 px-3 py-2 text-sm ${
                  r.me
                    ? "border-brick-yellow bg-highlight/40 font-bold"
                    : "border-ink/10"
                }`}
              >
                <span>
                  {r.rank}위 {r.name}
                  {r.me && " (나)"}
                </span>
                <b>{r.reviews}회</b>
              </li>
            ))}
          </ol>
          {ranks.length === 1 && (
            <p className="mt-3 text-xs opacity-60">
              아직 나 혼자예요 — 친구를 추가하면 함께 순위가 매겨져요!
            </p>
          )}
        </section>
      )}
    </main>
  );
}
