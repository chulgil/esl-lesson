"use client";

import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { Showcase } from "@/components/landing/Showcase";
import { DailyGoalCard } from "@/components/study/DailyGoalCard";
import { DailyQuestsCard } from "@/components/study/DailyQuestsCard";
import { OnboardingChecklist } from "@/components/study/OnboardingChecklist";
import { StreakCelebration } from "@/components/study/StreakCelebration";
import { fetchMe, type Me } from "@/lib/api";
import { studyApi, type Stats } from "@/lib/study-api";

export default function HomePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe().then((user) => {
      setMe(user);
      setLoading(false);
    });
  }, []);

  if (!loading && !me) {
    // 비로그인: 쇼케이스 랜딩 (타이포그래피 배경)
    return (
      <main className="notebook-lines notebook-margin min-h-screen">
        <Showcase />
      </main>
    );
  }

  return (
    <main className="notebook-lines notebook-margin min-h-screen px-6 py-10 sm:px-16">
      {loading || !me ? (
        <p className="text-sm opacity-60">불러오는 중...</p>
      ) : (
        <Dashboard me={me} />
      )}
    </main>
  );
}

const LEVEL_COLORS = [
  "bg-brick-red",
  "bg-brick-yellow",
  "bg-brick-blue",
  "bg-brick-green",
];

function Dashboard({ me }: { me: Me }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    studyApi
      .stats()
      .then(setStats)
      .catch(() => undefined);
  }, []);

  return (
    <section className="flex flex-col gap-7">
      {/* 인사 = 페이지 제목 — 랜딩용 대형 타이틀은 AppNav 로고와 중복이라 제거 (2026-07-15 UX 검토) */}
      <header>
        <h1 className="font-hand text-3xl font-bold sm:text-4xl">
          <span className="hl">{me.nickname}</span> 님, 오늘도 한 브릭
          쌓아볼까요?
        </h1>
        <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          {stats && (
            <span
              className="rounded bg-brick-blue/10 px-2 py-0.5 font-bold whitespace-nowrap text-brick-blue"
              title={`${stats.xp} XP — 복습·게임으로 쌓여요`}
            >
              Lv.{stats.level}
            </span>
          )}
          {stats && stats.streak_days > 0 && (
            <span className="rounded bg-highlight/60 px-2 py-0.5 whitespace-nowrap">
              {stats.streak_days}일 연속 학습 중
            </span>
          )}
        </p>
      </header>

      <div className="flex flex-wrap gap-4">
        <Brick color="green" href="/study/session">
          {/* 낚싯대: 밀린 전체가 아니라 오늘 목표 잔여만 보여준다 (포기 방지) */}
          {!stats
            ? "오늘의 학습 시작"
            : stats.due_count === 0
              ? "새 카드 만나러 가기"
              : stats.reviews_today >= stats.daily_goal
                ? "이어서 더 학습하기"
                : `오늘의 학습 시작 (${Math.min(
                    stats.due_count,
                    stats.daily_goal - stats.reviews_today,
                  )}개만)`}
        </Brick>
        <Brick color="blue" href="/library">
          콘텐츠 라이브러리
        </Brick>
        {/* "내 콘텐츠" 제거 (2026-07-28) — 유튜브 등록은 관리자 전용 사양 */}
        <Brick color="yellow" href="/chat">
          채팅
        </Brick>
        <Brick color="red" href="/game">
          게임
        </Brick>
      </div>

      {/* 오늘의 목표 — 밀린 전체가 아닌 목표 기준 진행 (포기 방지 기획 2026-07-15) */}
      {stats && <DailyGoalCard stats={stats} />}

      {/* 오늘의 미션 — 매일 다른 3종 도장, 세션 다양화 (retention-plan.md) */}
      <DailyQuestsCard />

      {/* 스트릭 마일스톤 축하 — 7·14·30일... 도달 첫 진입 1회 */}
      {stats && <StreakCelebration streakDays={stats.streak_days} />}

      {/* 시작 체크리스트 — 오늘 할 일보다 아래 (기존 사용자의 첫 시선은 데일리 루프) */}
      {stats && <OnboardingChecklist stats={stats} />}

      {stats && (
        // 누적 컬렉션 지표 — "오늘의 목표"(일일)와 명확히 구분 (2026-07-15 소유자 혼동 리포트)
        <div>
          <p className="text-sm font-bold">내 카드 컬렉션</p>
          <p className="mb-2 text-xs opacity-60">
            지금까지 만난 카드 / 만날 수 있는 전체 — 오늘 학습과는 무관하게
            쌓여요
          </p>
          <div className="flex flex-wrap items-end gap-6">
            {stats.levels.map((lv) => (
              <div
                key={lv.level}
                className="flex flex-col items-center gap-1"
                title={`${TYPE_LABELS[lv.item_type] ?? lv.item_type} 카드 ${lv.available_items}개 중 ${lv.cards}개를 이미 만났어요`}
              >
                <div className="flex flex-col-reverse gap-0.5" aria-hidden>
                  {Array.from({ length: Math.min(8, lv.cards) }, (_, i) => (
                    <span
                      key={i}
                      className={`h-2.5 w-8 rounded-sm ${LEVEL_COLORS[lv.level - 1]}`}
                    />
                  ))}
                  {lv.cards === 0 && (
                    <span className="h-2.5 w-8 rounded-sm bg-ink/10" />
                  )}
                </div>
                <p className="text-xs opacity-60">
                  {TYPE_LABELS[lv.item_type] ?? `레벨 ${lv.level}`} · {lv.cards}
                  /{lv.available_items}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

const TYPE_LABELS: Record<string, string> = {
  word: "단어",
  idiom: "숙어",
  pattern: "패턴",
  sentence: "문장",
};
