"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { friendsApi } from "@/lib/friends-api";
import { pushEnabled } from "@/lib/push";
import { studyApi, type Stats } from "@/lib/study-api";

/** 첫 주 계약 — 이 앱으로 "어떻게" 공부하는지를 3단계로 가르친다
 *  (docs/proposal/effectiveness-audit-2026-08.md 구멍 4).
 *
 *  이전엔 첫 학습·친구 추가 2항목이었다 — 친구 추가는 학습 핵심이 아니라
 *  신규 사용자가 이 앱의 학습법(영상 정복 루틴·리마인더)을 만나지 못했다.
 *  "영상 등록" 단계는 여전히 제외 (2026-07-28: 관리자 전용 사양이라 달성 불가).
 *  친구 추가는 학습 3단계를 끝낸 뒤에만 꺼낸다. */
/** 레벨 확인 1탭 — 라이브러리 기본 필터·게임 추천이 이 값을 따른다
 *  (proposal/level-fit-library-2026-08.md P1). 입문(1)도 초급 밴드로 표시. */
const LEVEL_CHOICES = [
  { label: "초급", studyLevel: 2 },
  { label: "중급", studyLevel: 3 },
  { label: "고급", studyLevel: 4 },
] as const;

function levelBand(studyLevel: number): number {
  if (studyLevel <= 2) return 2;
  return studyLevel === 3 ? 3 : 4;
}

/** 조건부 노출 (ux-redesign #8): 카드 0장(진짜 신규) 또는 가입 3일 이내만.
 *  그 뒤엔 미완료 단계가 남아도 숨긴다 — 평상시 홈은 데일리 루프만. */
const SHOW_DAYS_AFTER_JOIN = 3;

export function OnboardingChecklist({
  stats,
  joinedAt,
}: {
  stats: Stats;
  joinedAt: string | null;
}) {
  const [friendCount, setFriendCount] = useState<number | null>(null);
  const [routineStarted, setRoutineStarted] = useState<boolean | null>(null);
  // null = 로딩 중. reminderReady=false 면 VAPID 미설정 환경 — 단계 자체를 숨긴다
  const [reminderDone, setReminderDone] = useState<boolean | null>(null);
  const [reminderReady, setReminderReady] = useState<boolean | null>(null);
  const [studyLevel, setStudyLevel] = useState<number | null>(null);

  useEffect(() => {
    friendsApi
      .list()
      .then((res) => setFriendCount(res.friends.length))
      .catch(() => setFriendCount(0));
    studyApi
      .decks()
      .then((res) =>
        setRoutineStarted(res.items.some((d) => d.routine_done > 0)),
      )
      .catch(() => setRoutineStarted(false));
    studyApi
      .getSettings()
      .then((s) => {
        setReminderDone(s.push_subscribed);
        setStudyLevel(s.study_level);
      })
      .catch(() => setReminderDone(false));
    pushEnabled()
      .then(setReminderReady)
      .catch(() => setReminderReady(false));
  }, []);

  async function pickLevel(next: number) {
    if (studyLevel !== null && levelBand(studyLevel) === next) return;
    const prev = studyLevel;
    setStudyLevel(next); // 낙관적 반영 — 실패 시 원복
    try {
      await studyApi.patchSettings({ study_level: next });
    } catch {
      setStudyLevel(prev);
    }
  }

  if (
    friendCount === null ||
    routineStarted === null ||
    reminderDone === null ||
    reminderReady === null
  ) {
    return null;
  }

  const totalCards = stats.levels.reduce((sum, lv) => sum + lv.cards, 0);
  // 조건부 노출 — 카드가 생겼고 가입 3일이 지나면 미완료 단계가 남아도 숨긴다
  const joinedDaysAgo = joinedAt
    ? (Date.now() - new Date(joinedAt).getTime()) / 86_400_000
    : 0; // 가입일 미상(구 응답 캐시)은 신규 취급 — 숨겨서 잃는 쪽보다 안전
  if (totalCards > 0 && joinedDaysAgo > SHOW_DAYS_AFTER_JOIN) return null;

  // 학습 핵심 3단계 — 이 순서가 곧 이 앱의 학습법이다
  const coreSteps = [
    {
      label: "첫 학습 시작하기",
      desc: "라이브러리 영상에서 추출된 단어·문장이 복습 카드로 나와요",
      href: "/study/session",
      done: totalCards > 0,
    },
    {
      label: "영상 한 편 정복 시작하기",
      desc: "한 영상을 듣기→분석→따라 말하기·요약 6단계로 완전히 내 것으로 만들어요",
      href: "/library",
      done: routineStarted,
    },
    ...(reminderReady
      ? [
          {
            label: "복습 리마인더 시각 정하기",
            desc: "언제 할지 미리 정해두면 그 시각에 알림이 와요 — 습관은 결심이 아니라 시각으로 붙어요",
            href: "/settings",
            done: reminderDone,
          },
        ]
      : []),
  ];

  // 친구 추가는 학습 3단계를 끝낸 사람에게만 — 첫 주 계약을 흐리지 않는다
  const steps = coreSteps.every((s) => s.done)
    ? [
        ...coreSteps,
        {
          label: "친구 추가하기",
          desc: "주간 랭킹에서 함께 경쟁하고 게임에 초대할 수 있어요",
          href: "/friends",
          done: friendCount > 0,
        },
      ]
    : coreSteps;

  if (steps.every((s) => s.done)) return null;

  const doneCount = steps.filter((s) => s.done).length;

  return (
    <section className="w-full rounded-lg border-2 border-brick-blue/40 bg-white p-4 text-left">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className="text-sm font-bold">
          시작 체크리스트
          <span className="ml-2 font-normal opacity-60">
            {doneCount}/{steps.length} 완료
          </span>
        </p>
        <Link
          href="/method"
          className="ml-auto text-xs font-bold text-brick-blue underline-offset-2 hover:underline"
        >
          이 앱이 영어를 늘리는 방법 →
        </Link>
      </div>
      {/* 레벨 확인 1탭 — 첫 학습 전에 내 레벨을 정하면 라이브러리·게임이 그 레벨을 따라온다 */}
      {studyLevel !== null && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="opacity-60">내 레벨:</span>
          {LEVEL_CHOICES.map((choice) => (
            <button
              key={choice.studyLevel}
              type="button"
              onClick={() => pickLevel(choice.studyLevel)}
              className={`min-h-11 rounded-full border-2 px-2.5 py-0.5 font-bold transition ${
                levelBand(studyLevel) === choice.studyLevel
                  ? "border-brick-blue bg-brick-blue/10 text-brick-blue"
                  : "border-ink/15 bg-white hover:border-brick-blue/50"
              }`}
            >
              {choice.label}
            </button>
          ))}
          <span className="opacity-50">
            라이브러리가 이 레벨 영상을 먼저 보여줘요
          </span>
        </div>
      )}
      <ul className="mt-2 flex flex-col gap-1.5">
        {steps.map((step) => (
          <li key={step.label}>
            {step.done ? (
              <p className="flex items-center gap-2 text-sm opacity-50">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brick-green text-xs font-bold text-brick-label">
                  v
                </span>
                <s>{step.label}</s>
              </p>
            ) : (
              <Link
                href={step.href}
                className="group flex items-center gap-2 rounded-md p-1 text-sm transition-colors hover:bg-ink/5"
              >
                <span className="h-5 w-5 rounded-full border-2 border-ink/25" />
                <span>
                  <span className="font-bold group-hover:underline">
                    {step.label}
                  </span>
                  <span className="ml-2 text-xs opacity-60">{step.desc}</span>
                </span>
                <span className="ml-auto text-brick-blue">→</span>
              </Link>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
