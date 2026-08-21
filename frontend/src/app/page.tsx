"use client";

import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { Showcase } from "@/components/landing/Showcase";
import { DailyGoalCard } from "@/components/study/DailyGoalCard";
import { DailyQuestsCard } from "@/components/study/DailyQuestsCard";
import { OnboardingChecklist } from "@/components/study/OnboardingChecklist";
import { StreakCelebration } from "@/components/study/StreakCelebration";
import { StreakSaverThanks } from "@/components/study/StreakSaverThanks";
import { StudyingFriendsCard } from "@/components/study/StudyingFriendsCard";
import { WeeklyReportBanner } from "@/components/study/WeeklyReportBanner";
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
    <main className="notebook-lines notebook-margin min-h-screen px-4 py-5 sm:px-16 sm:py-10">
      {loading || !me ? (
        <p className="text-center text-sm opacity-60">불러오는 중...</p>
      ) : (
        <Dashboard me={me} />
      )}
    </main>
  );
}

function Dashboard({ me }: { me: Me }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    studyApi
      .stats()
      .then(setStats)
      .catch(() => undefined);
  }, []);

  // 담은 콘텐츠가 0이면 학습 큐가 만들어질 수 없다 — 신규 사용자 경로 분기
  const noContent = Boolean(
    stats && stats.levels.every((lv) => lv.available_items === 0),
  );

  return (
    // 모바일 한 화면 원칙 (2026-08-21): 홈 전체가 390px 세로에서 스크롤 없이
    // 보이도록 콘텐츠 열을 중앙 정렬 + 카드들을 컴팩트하게 유지한다.
    <section className="mx-auto flex w-full max-w-xl flex-col items-center gap-4 text-center">
      {/* 인사 = 페이지 제목 — 랜딩용 대형 타이틀은 AppNav 로고와 중복이라 제거 (2026-07-15 UX 검토).
          모바일 한 줄에 들어가는 크기로 축소 (2026-08-21 모바일 우선) */}
      <header className="flex flex-col items-center gap-1.5">
        <h1 className="font-hand text-xl font-bold sm:text-2xl">
          <span className="hl">{me.nickname}</span> 님, 오늘도 한 브릭
          쌓아볼까요?
        </h1>
        <p className="flex flex-wrap items-center justify-center gap-2 text-xs">
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

      {/* 라이브러리·채팅·게임 브릭 제거 (2026-08-03) — 전역 5탭에 이미 있어
          홈에서 중복 노출됐다. 홈의 1차 행동은 하나뿐이다 */}
      <div className="flex w-full justify-center">
        {noContent ? (
          // 담은 콘텐츠가 없으면 학습할 카드 자체가 안 생긴다 — 세션이 아니라
          // 라이브러리로 보낸다 (기존엔 "새 카드 만나러 가기"가 빈 세션으로 갔다)
          <Brick color="blue" href="/library" className="w-full max-w-sm">
            라이브러리에서 콘텐츠 담기
          </Brick>
        ) : (
          <Brick
            color="green"
            href="/study/session"
            className="w-full max-w-sm"
          >
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
        )}
      </div>
      {noContent && (
        <p className="-mt-2 text-xs opacity-70">
          아직 담은 콘텐츠가 없어요 — 라이브러리에서 하나 담으면 오늘 학습할
          카드가 만들어져요.
        </p>
      )}

      {/* 지금 학습 중인 친구 — 관전 진입점 (study-spectate.md 진입 경로 재설계) */}
      <StudyingFriendsCard />

      {/* 복귀 감사 — 책갈피가 지켜준 다음 방문에 1회 (user-journey-motivation P1) */}
      {stats && (
        <StreakSaverThanks
          savedDays={stats.streak_saved_days}
          streakDays={stats.streak_days}
        />
      )}

      {/* 주간 성적표 — 새 성적표가 나온 주의 첫 방문에 1회 (weekly-report.md) */}
      <WeeklyReportBanner />

      {/* 오늘의 목표 — 밀린 전체가 아닌 목표 기준 진행 (포기 방지 기획 2026-07-15) */}
      {stats && <DailyGoalCard stats={stats} />}

      {/* 오늘의 미션 — 매일 다른 3종 도장, 세션 다양화 (retention-plan.md) */}
      <DailyQuestsCard />

      {/* 스트릭 마일스톤 축하 — 7·14·30일... 도달 첫 진입 1회 */}
      {stats && <StreakCelebration streakDays={stats.streak_days} />}

      {/* 시작 체크리스트 — 오늘 할 일보다 아래 (기존 사용자의 첫 시선은 데일리 루프).
          조건부 노출: 카드 0장 또는 가입 3일 이내만 (ux-redesign #8) */}
      {stats && <OnboardingChecklist stats={stats} joinedAt={me.created_at} />}

      {/* 누적 지표(카드 컬렉션·업적)는 학습 탭으로 이관 (2026-08-03 IA 정리) —
          홈은 "오늘 뭘 하지?" 한 질문만 답한다 */}
    </section>
  );
}
