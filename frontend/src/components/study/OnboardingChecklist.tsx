"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { friendsApi } from "@/lib/friends-api";
import { myApi } from "@/lib/my-api";
import type { Stats } from "@/lib/study-api";

/** 시작 체크리스트 — 신규 사용자가 빈 화면에서 길을 잃지 않게 (P2 온보딩) */
export function OnboardingChecklist({ stats }: { stats: Stats }) {
  const [contentCount, setContentCount] = useState<number | null>(null);
  const [friendCount, setFriendCount] = useState<number | null>(null);

  useEffect(() => {
    myApi
      .list()
      .then((res) => setContentCount(res.items.length))
      .catch(() => setContentCount(0));
    friendsApi
      .list()
      .then((res) => setFriendCount(res.friends.length))
      .catch(() => setFriendCount(0));
  }, []);

  if (contentCount === null || friendCount === null) return null;

  const totalCards = stats.levels.reduce((sum, lv) => sum + lv.cards, 0);
  const steps = [
    {
      label: "유튜브 영상 등록하기",
      desc: "보고 싶은 영상 링크만 붙여넣으면 학습 자료가 돼요",
      href: "/my",
      done: contentCount > 0,
    },
    {
      label: "첫 학습 시작하기",
      desc: "추출된 단어·문장이 복습 카드로 나와요",
      href: "/study/session",
      done: totalCards > 0,
    },
    {
      label: "친구 추가하기",
      desc: "주간 랭킹에서 함께 경쟁하고 게임에 초대할 수 있어요",
      href: "/friends",
      done: friendCount > 0,
    },
  ];

  if (steps.every((s) => s.done)) return null;

  const doneCount = steps.filter((s) => s.done).length;

  return (
    <section className="max-w-xl rounded-lg border-2 border-brick-blue/40 bg-white p-4">
      <p className="text-sm font-bold">
        시작 체크리스트
        <span className="ml-2 font-normal opacity-60">{doneCount}/3 완료</span>
      </p>
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
