"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { AchievementBadges } from "@/components/study/AchievementBadges";
import { examApi, type OpenExam } from "@/lib/exam-api";
import { friendsApi } from "@/lib/friends-api";
import {
  type Achievement,
  studyApi,
  type Stats,
  type StudyDeck,
  type StudyRank,
} from "@/lib/study-api";

/** 학습 허브 — 학습 관련 기능을 한눈에 (게임 허브와 동일 패턴, 2026-07-14 IA 정리) */
export default function StudyHubPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [friendSignal, setFriendSignal] = useState<{
    studying: number;
    incoming: number;
  } | null>(null);
  const [ranks, setRanks] = useState<StudyRank[]>([]);
  const [badges, setBadges] = useState<Achievement[]>([]);
  // null = 아직 로딩/실패 (섹션 숨김) — 빈 배열은 "덱 0개" 빈 상태를 렌더링
  const [decks, setDecks] = useState<StudyDeck[] | null>(null);
  const [openExams, setOpenExams] = useState<OpenExam[]>([]);

  useEffect(() => {
    examApi
      .open()
      .then((res) => setOpenExams(res.items))
      .catch(() => undefined);
    studyApi
      .stats()
      .then(setStats)
      .catch(() => undefined);
    studyApi
      .decks()
      .then((res) => setDecks(res.items))
      .catch(() => undefined);
    studyApi
      .leaderboard()
      .then((res) => setRanks(res.items))
      .catch(() => undefined);
    studyApi
      .achievements()
      .then((res) => setBadges(res.items))
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
          {stats && (
            <span className="ml-2 rounded bg-brick-blue/10 px-2 py-0.5 text-xs font-bold text-brick-blue">
              Lv.{stats.level} · {stats.xp} XP
            </span>
          )}
        </p>
      </header>

      {/* 1순위 CTA — 오늘의 학습 */}
      <section className="mt-6 max-w-4xl rounded-xl border-2 border-brick-green/40 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          <div className="min-w-52 flex-1">
            <h2 className="font-hand text-2xl font-bold">오늘의 학습</h2>
            {/* 밀린 전체가 아닌 목표 잔여로 유도 — 홈 카드와 동일 기준 (포기 방지 기획) */}
            <p className="mt-1 text-sm opacity-70">
              {!stats
                ? "복습 큐를 확인하는 중..."
                : stats.due_count === 0
                  ? "지금은 밀린 복습이 없어요 — 새 카드를 만나러 가볼까요?"
                  : stats.reviews_today >= stats.daily_goal
                    ? `오늘 목표 달성! 더 하고 싶으면 이어서 해요 (남은 ${stats.due_count}개는 나눠서 갚아요)`
                    : stats.due_count > stats.daily_goal - stats.reviews_today
                      ? `오늘 목표까지 ${stats.daily_goal - stats.reviews_today}개 — 밀린 ${stats.due_count}개는 나눠서 갚아요`
                      : `오늘 목표까지 ${Math.min(stats.due_count, stats.daily_goal - stats.reviews_today)}개만 하면 성공이에요`}
              {stats && stats.streak_days > 0 && (
                <span className="ml-2 rounded bg-highlight/60 px-1.5 py-0.5 text-xs font-bold">
                  {stats.streak_days}일 연속
                </span>
              )}
            </p>
          </div>
          <Brick color="green" href="/study/session">
            {!stats
              ? "학습 시작"
              : stats.due_count === 0
                ? "새 카드 만나기"
                : stats.reviews_today >= stats.daily_goal
                  ? "이어서 학습"
                  : `학습 시작 (${Math.min(
                      stats.due_count,
                      stats.daily_goal - stats.reviews_today,
                    )}개만)`}
          </Brick>
        </div>
      </section>

      {/* 내 덱 — 담은 콘텐츠 단위 학습 계획 (Anki 덱, docs/specs/study-decks.md) */}
      {decks !== null && (
        <section className="mt-5 max-w-4xl rounded-xl border-2 border-brick-blue/40 bg-white p-5 shadow-sm">
          <h2 className="font-hand text-2xl font-bold">내 덱</h2>
          <p className="mt-1 text-xs opacity-60">
            담은 콘텐츠가 덱이 돼요 — 하나만 골라서 집중 학습할 수 있어요
          </p>
          {decks.length === 0 ? (
            <div className="mt-3 flex flex-col items-start gap-3">
              <p className="text-sm opacity-70">
                아직 덱이 없어요 — 라이브러리에서 콘텐츠를 담아보세요
              </p>
              <Brick color="blue" href="/library">
                라이브러리 둘러보기
              </Brick>
            </div>
          ) : (
            <ul className="mt-3 flex flex-col gap-2">
              {decks.map((deck) => (
                <li
                  key={deck.content_id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border-2 border-ink/10 px-3 py-2"
                >
                  <div className="min-w-40 flex-1">
                    <p className="text-sm font-bold">{deck.title}</p>
                    <p className="mt-0.5 text-xs opacity-60">
                      복습 {deck.due}개 · 새 카드 {deck.new_available}개
                      {deck.total_cards > 0 && (
                        <span className="ml-1.5 opacity-70">
                          (학습 중 {deck.total_cards}장)
                        </span>
                      )}
                    </p>
                  </div>
                  <Link
                    href={`/study/session?content=${deck.content_id}`}
                    className="inline-flex min-h-10 items-center rounded-md border-2 border-brick-green/60 bg-white px-3 text-sm font-bold text-brick-green transition hover:-translate-y-0.5 hover:border-brick-green"
                  >
                    이 콘텐츠만 학습
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* 시험 도전 — 준비된 실력을 확인하고 XP·랭킹·업적으로 보상 (2026-07-31 goal) */}
      {openExams.length > 0 && (
        <section className="mt-5 max-w-4xl rounded-xl border-2 border-brick-red/40 bg-white p-5 shadow-sm">
          <h2 className="font-hand text-2xl font-bold">시험 도전</h2>
          <p className="mt-1 text-xs opacity-60">
            공부한 콘텐츠의 실력을 확인해요 — 제출마다 +20 XP, 점수 10점당 +1
            XP. 최고점으로 전체 랭킹 경쟁!
          </p>
          <ul className="mt-3 flex flex-col gap-2">
            {openExams.map((exam) => (
              <li
                key={exam.exam_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border-2 border-ink/10 px-3 py-2"
              >
                <div className="min-w-40 flex-1">
                  <p className="text-sm font-bold">
                    {exam.content_title}
                    {exam.round > 1 && (
                      <span className="ml-1.5 rounded bg-ink/10 px-1.5 py-0.5 text-[10px]">
                        {exam.round}회차
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs opacity-60">
                    {exam.question_count}문항 · 응시자 {exam.attempt_user_count}
                    명
                    {exam.top_name && (
                      <span className="ml-1.5 font-bold text-brick-yellow">
                        1위 {exam.top_name}
                      </span>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {exam.my_best ? (
                    <span className="rounded bg-highlight/50 px-2 py-0.5 text-xs font-bold">
                      내 최고 {exam.my_best.score}점
                    </span>
                  ) : (
                    <span className="rounded bg-brick-red/10 px-2 py-0.5 text-xs font-bold text-brick-red">
                      미응시
                    </span>
                  )}
                  <Link
                    href={`/exam/${exam.content_id}`}
                    className="inline-flex min-h-10 items-center rounded-md border-2 border-brick-red/60 bg-white px-3 text-sm font-bold text-brick-red transition hover:-translate-y-0.5 hover:border-brick-red"
                  >
                    {exam.my_best ? "다시 도전" : "도전하기"}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

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

      {/* 업적 스티커 — 소급 반영, 진행률 표시 (P3) */}
      {badges.length > 0 && (
        <section className="mt-5 max-w-4xl rounded-xl border-2 border-brick-green/40 bg-white p-5 shadow-sm">
          <h2 className="font-hand text-2xl font-bold">
            업적 스티커
            <span className="ml-2 align-middle text-sm font-normal opacity-60">
              {badges.filter((b) => b.achieved).length}/{badges.length} 달성
            </span>
          </h2>
          <p className="mt-1 mb-3 text-xs opacity-60">
            공부하고 게임하다 보면 하나씩 붙어요
          </p>
          <AchievementBadges items={badges} />
        </section>
      )}
    </main>
  );
}
