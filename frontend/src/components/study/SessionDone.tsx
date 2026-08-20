"use client";

import { useEffect, useState } from "react";
import { Brick } from "@/components/brick/Brick";
import { studyApi, type Stats } from "@/lib/study-api";
import { useSurfaceSkin } from "@/lib/theme-surfaces";

/** 세션 완료 화면 — 피크엔드: 오늘의 의미(목표·실력 전환·다음 행동)를 요약한다
 *  (user-journey-motivation-2026-08.md P0 ②). 표면 스킨을 따라 테마의
 *  칠판/시험지/사탕판 위에 오늘의 정리를 쓴다. session/page.tsx 에서 분리. */
export function SessionDone({
  weakMode,
  answeredCount,
  correctCount,
  longTermCount,
  onRestart,
  contentId,
}: {
  weakMode: boolean;
  answeredCount: number;
  correctCount: number;
  longTermCount: number;
  onRestart: () => void;
  /** 덱 세션이면 오답 정리도 같은 덱 스코프로 (2026-08-20 리뷰) */
  contentId?: number;
}) {
  const skin = useSurfaceSkin();
  // 완료 순간의 최신 목표 진행·오답 잔여 — 피크엔드 요약 재료
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    studyApi
      .stats()
      .then(setStats)
      .catch(() => undefined);
  }, []);

  return (
    <section
      className={`flex max-w-xl flex-col items-start gap-4 p-6 ${skin.section}`}
    >
      <h2 className="font-hand text-2xl">
        {weakMode ? "오답을 정리했어요!" : "세션 완료!"}
      </h2>
      <p>
        {answeredCount}문항 중{" "}
        <b className="text-brick-green">{correctCount}개</b> 정답 (
        {answeredCount ? Math.round((correctCount / answeredCount) * 100) : 0}
        %)
      </p>

      {longTermCount > 0 && (
        <p className="rounded-md border-2 border-brick-green/40 bg-brick-green/10 px-3 py-2 text-sm">
          이번 세션에서 <b className="text-brick-green">{longTermCount}개</b>가
          장기 기억으로 굳었어요 — 일주일 넘게 안 봐도 기억할 카드예요
        </p>
      )}

      {stats && (
        <div className="w-full rounded-md border-2 border-ink/10 bg-white px-3 py-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold">오늘 목표</span>
            <span>
              {Math.min(stats.reviews_today, stats.daily_goal)}/
              {stats.daily_goal}
            </span>
            {stats.reviews_today >= stats.daily_goal && (
              <span className="rounded bg-highlight/60 px-1.5 py-0.5 text-xs font-bold">
                목표 달성! 오늘 몫은 끝났어요
              </span>
            )}
          </div>
          <div className="mt-1.5 h-2 w-full overflow-hidden rounded bg-ink/10">
            <div
              className="h-full rounded bg-brick-green transition-all"
              style={{
                width: `${Math.min(
                  100,
                  (stats.reviews_today / stats.daily_goal) * 100,
                )}%`,
              }}
            />
          </div>
          {/* 내일 예고 — 예측 가능한 분량은 부담이 아니라 약속이 된다 */}
          {stats.due_tomorrow > 0 && (
            <p className="mt-1.5 text-xs opacity-60">
              내일은 {stats.due_tomorrow}개가 기다려요 — 오늘처럼이면 충분해요
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        {/* 오답이 남았으면 정리로 마무리 — 미완성 잔여를 다음 행동으로 (자이가르닉) */}
        {!weakMode && stats && stats.weak_count > 0 && (
          <Brick
            color="red"
            href={`/study/session?mode=weak${contentId ? `&content=${contentId}` : ""}`}
          >
            오답 {stats.weak_count}개 정리하고 마무리
          </Brick>
        )}
        <Brick color="green" onClick={onRestart}>
          이어서 학습
        </Brick>
        <Brick color="yellow" href="/study/network">
          어휘망 보기
        </Brick>
        <Brick color="blue" href="/">
          홈으로
        </Brick>
      </div>
    </section>
  );
}
